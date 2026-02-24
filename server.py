from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import math
from openrouter_client import chat
from dsl_prompt import dsl_system_prompt

from dsl_interp_ir import eval_ir
from dsl_ir import lower
from dsl_parser import Parser
from dsl_glsl_ir import emit_glsl
from dsl_ast import Call, Expr, Number, Vec2, Vec3


class CompileRequest(BaseModel):
    code: str


class FitRequest(BaseModel):
    code: str


class EvalRequest(BaseModel):
    code: str
    p: list[float]


class GenerateDSLRequest(BaseModel):
    prompt: str
    model: str | None = None


class GenerateAndCompileRequest(BaseModel):
    prompt: str
    model: str | None = None


def _num(expr: Expr) -> float:
    if isinstance(expr, Number):
        return float(expr.value)
    raise ValueError("Expected numeric literal")


def _vec2(expr: Expr) -> tuple[float, float]:
    if isinstance(expr, Vec2):
        return (_num(expr.x), _num(expr.y))
    raise ValueError("Expected vec2 literal")


def _vec3(expr: Expr) -> tuple[float, float, float]:
    if isinstance(expr, Vec3):
        return (_num(expr.x), _num(expr.y), _num(expr.z))
    raise ValueError("Expected vec3 literal")


def _bbox_union(
    a: tuple[list[float], list[float]], b: tuple[list[float], list[float]]
) -> tuple[list[float], list[float]]:
    return (
        [min(a[0][0], b[0][0]), min(a[0][1], b[0][1]), min(a[0][2], b[0][2])],
        [max(a[1][0], b[1][0]), max(a[1][1], b[1][1]), max(a[1][2], b[1][2])],
    )


def _bbox_expand(box: tuple[list[float], list[float]], d: float) -> tuple[list[float], list[float]]:
    e = abs(d)
    return (
        [box[0][0] - e, box[0][1] - e, box[0][2] - e],
        [box[1][0] + e, box[1][1] + e, box[1][2] + e],
    )


def _rotate_point_xyz(
    p: tuple[float, float, float], angles_deg: tuple[float, float, float]
) -> tuple[float, float, float]:
    x, y, z = p
    ax = math.radians(angles_deg[0])
    ay = math.radians(angles_deg[1])
    az = math.radians(angles_deg[2])

    cx, sx = math.cos(ax), math.sin(ax)
    y, z = y * cx - z * sx, y * sx + z * cx

    cy, sy = math.cos(ay), math.sin(ay)
    x, z = x * cy + z * sy, -x * sy + z * cy

    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz

    return (x, y, z)


def _bbox_rotate(
    box: tuple[list[float], list[float]], angles_deg: tuple[float, float, float]
) -> tuple[list[float], list[float]]:
    (xmin, ymin, zmin), (xmax, ymax, zmax) = box
    corners = [
        (x, y, z)
        for x in (xmin, xmax)
        for y in (ymin, ymax)
        for z in (zmin, zmax)
    ]
    rotated = [_rotate_point_xyz(c, angles_deg) for c in corners]
    xs = [p[0] for p in rotated]
    ys = [p[1] for p in rotated]
    zs = [p[2] for p in rotated]
    return ([min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])


def _path_points(path_expr: Expr) -> list[tuple[float, float, float]]:
    if not isinstance(path_expr, Call):
        raise ValueError("Path must be a call")
    if path_expr.name == "line":
        if len(path_expr.args) != 2:
            raise ValueError("line expects 2 args")
        return [_vec3(path_expr.args[0]), _vec3(path_expr.args[1])]
    if path_expr.name == "polyline":
        if len(path_expr.args) < 2:
            raise ValueError("polyline expects at least 2 args")
        return [_vec3(a) for a in path_expr.args]
    if path_expr.name == "helix":
        if len(path_expr.args) != 3:
            raise ValueError("helix expects 3 args")
        r = abs(_num(path_expr.args[0]))
        pitch = _num(path_expr.args[1])
        turns = max(0.0, _num(path_expr.args[2]))
        h = pitch * turns
        return [(-r, 0.0, -r), (r, h, r)]
    raise ValueError("Unsupported path call")


def _profile_extent(profile: Expr) -> float:
    if isinstance(profile, Call) and profile.name == "circle" and len(profile.args) == 1:
        return abs(_num(profile.args[0]))
    if isinstance(profile, Call) and profile.name == "polygon" and len(profile.args) >= 3:
        pts = [_vec2(a) for a in profile.args]
        max_comp = 0.0
        for x, y in pts:
            max_comp = max(max_comp, abs(x), abs(y))
        return max_comp
    return 1.0


def _bbox_of(expr: Expr) -> tuple[list[float], list[float]]:
    if isinstance(expr, Number):
        v = float(expr.value)
        return ([v, v, v], [v, v, v])
    if isinstance(expr, Vec3):
        x, y, z = _vec3(expr)
        return ([x, y, z], [x, y, z])
    if isinstance(expr, Vec2):
        x, y = _vec2(expr)
        return ([x, y, 0.0], [x, y, 0.0])
    if not isinstance(expr, Call):
        return ([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])

    n = expr.name
    a = expr.args

    if n == "sphere" and len(a) == 1:
        r = abs(_num(a[0]))
        return ([-r, -r, -r], [r, r, r])
    if n == "cylinder" and len(a) == 2:
        r = abs(_num(a[0]))
        h = abs(_num(a[1]))
        return ([-r, -h, -r], [r, h, r])
    if n == "box" and len(a) == 1:
        hx, hy, hz = _vec3(a[0])
        return ([-abs(hx), -abs(hy), -abs(hz)], [abs(hx), abs(hy), abs(hz)])
    if n == "hex_nut" and len(a) == 3:
        ro = abs(_num(a[0]))
        h = abs(_num(a[2]))
        s = max(ro, h)
        return ([-s, -s, -s], [s, s, s])
    if n == "union" and len(a) >= 1:
        cur = _bbox_of(a[0])
        for part in a[1:]:
            cur = _bbox_union(cur, _bbox_of(part))
        return cur
    if n == "difference" and len(a) == 2:
        return _bbox_of(a[0])
    if n == "translate" and len(a) == 2:
        box = _bbox_of(a[0])
        tx, ty, tz = _vec3(a[1])
        return (
            [box[0][0] + tx, box[0][1] + ty, box[0][2] + tz],
            [box[1][0] + tx, box[1][1] + ty, box[1][2] + tz],
        )
    if n == "rotate" and len(a) == 2:
        return _bbox_rotate(_bbox_of(a[0]), _vec3(a[1]))
    if n == "offset" and len(a) == 2:
        return _bbox_expand(_bbox_of(a[0]), _num(a[1]))
    if n == "extrude" and len(a) == 2:
        profile = a[0]
        h = abs(_num(a[1]))
        if isinstance(profile, Call) and profile.name == "circle" and len(profile.args) == 1:
            r = abs(_num(profile.args[0]))
            return ([-r, -r, -h], [r, r, h])
        if isinstance(profile, Call) and profile.name == "polygon" and len(profile.args) >= 3:
            pts = [_vec2(p) for p in profile.args]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return ([min(xs), min(ys), -h], [max(xs), max(ys), h])
    if n == "sweep" and len(a) == 2:
        extent = _profile_extent(a[0])
        pts = _path_points(a[1])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return (
            [min(xs) - extent, min(ys) - extent, min(zs) - extent],
            [max(xs) + extent, max(ys) + extent, max(zs) + extent],
        )
    if n == "blend2D" and len(a) == 3:
        extent = max(_profile_extent(a[0]), _profile_extent(a[1]))
        pts = _path_points(a[2])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return (
            [min(xs) - extent, min(ys) - extent, min(zs) - extent],
            [max(xs) + extent, max(ys) + extent, max(zs) + extent],
        )

    return ([-1.0, -1.0, -1.0], [1.0, 1.0, 1.0])


def _fit_camera_from_expr(expr: Expr) -> dict:
    bb_min, bb_max = _bbox_of(expr)
    cx = (bb_min[0] + bb_max[0]) * 0.5
    cy = (bb_min[1] + bb_max[1]) * 0.5
    cz = (bb_min[2] + bb_max[2]) * 0.5
    sx = bb_max[0] - bb_min[0]
    sy = bb_max[1] - bb_min[1]
    sz = bb_max[2] - bb_min[2]
    radius = max(0.5, max(sx, sy, sz) * 0.5)
    dist = max(2.0, min(200.0, radius * 2.4))
    return {
        "target": [cx, cy, cz],
        "distance": dist,
        "bbox": {"min": bb_min, "max": bb_max},
    }


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _compile(code: str) -> str:
    ast = Parser.from_source(code).parse()
    ir = lower(ast)
    return emit_glsl(ir)


@app.post("/compile")
def compile_endpoint(req: CompileRequest) -> dict:
    try:
        glsl = _compile(req.code)
        return {"glsl": glsl}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/fit")
def fit_endpoint(req: FitRequest) -> dict:
    try:
        ast = Parser.from_source(req.code).parse()
        return _fit_camera_from_expr(ast)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/eval")


async def _generate_dsl_internal(prompt: str, model: str | None = None) -> dict:
    """
    Generate DSL from English prompt using OpenRouter.
    Includes retry logic for invalid code.
    Returns { "code": "...", "error": "..." (if failed) }.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")
    
    default_model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    model = model or default_model
    
    messages = [
        {"role": "system", "content": dsl_system_prompt()},
        {"role": "user", "content": prompt}
    ]
    
    max_retries = 2
    dsl_code = ""
    for retry in range(max_retries + 1):
        try:
            dsl_code = await chat(
                model=model,
                messages=messages,
                api_key=api_key,
                referer="https://geometry-dsl.local",
                title="Geometry DSL",
            )
            
            # Strip markdown code blocks if present
            dsl_code = dsl_code.strip()
            if dsl_code.startswith("```"):
                dsl_code = "\n".join(dsl_code.split("\n")[1:])
            if dsl_code.endswith("```"):
                dsl_code = dsl_code[:-3]
            dsl_code = dsl_code.strip()
            
            # Validate by attempting parse + lower
            ast = Parser.from_source(dsl_code).parse()
            ir = lower(ast)
            
            return {"code": dsl_code}
        
        except Exception as exc:
            error_msg = str(exc)
            if retry < max_retries:
                # Retry with error feedback
                messages.append({"role": "assistant", "content": dsl_code})
                messages.append({
                    "role": "user",
                    "content": f"The DSL failed to compile with this error: {error_msg}. Fix it. Output ONLY corrected DSL."
                })
            else:
                # Final failure
                return {
                    "error": error_msg,
                    "last_code": dsl_code
                }
    
    return {"error": "Unknown error"}


@app.post("/generate_dsl")
async def generate_dsl_endpoint(req: GenerateDSLRequest) -> dict:
    """
    Generate DSL from English prompt.
    Returns { "code": "<dsl>" } or { "error": "...", "last_code": "..." }.
    """
    try:
        result = await _generate_dsl_internal(req.prompt, req.model)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/generate_and_compile")
async def generate_and_compile_endpoint(req: GenerateAndCompileRequest) -> dict:
    """
    Generate DSL from English prompt, then compile to GLSL.
    Returns { "code": "<dsl>", "glsl": "..." } or error.
    """
    try:
        gen_result = await _generate_dsl_internal(req.prompt, req.model)
        if "error" in gen_result:
            raise HTTPException(status_code=400, detail=gen_result)
        
        dsl_code = gen_result["code"]
        glsl = _compile(dsl_code)
        return {"code": dsl_code, "glsl": glsl}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
def eval_endpoint(req: EvalRequest) -> dict:
    if len(req.p) != 3:
        raise HTTPException(status_code=400, detail="p must be [x,y,z]")
    try:
        ast = Parser.from_source(req.code).parse()
        ir = lower(ast)
        val = eval_ir(ir, {"p": (float(req.p[0]), float(req.p[1]), float(req.p[2]))})
        return {"value": float(val)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
