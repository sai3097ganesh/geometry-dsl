import math
from dataclasses import dataclass
from typing import List, Tuple

from dsl_ast import Call, Expr, Number, Vec2, Vec3
from dsl_geom import check_polygon_simple, ensure_ccw, is_convex

Vec2T = Tuple[float, float]
Vec3T = Tuple[float, float, float]


@dataclass
class IR:
    op: str
    args: List["IR"]
    type: str
    value: float | None = None


def ir_const(v: float) -> IR:
    return IR("const", [], "f32", v)


def ir_vec3(x: IR, y: IR, z: IR) -> IR:
    return IR("vec3", [x, y, z], "vec3")


def ir_var(name: str) -> IR:
    return IR("var", [], "vec3", None)


def ir_unary(op: str, a: IR, out_type: str) -> IR:
    return IR(op, [a], out_type)


def ir_binary(op: str, a: IR, b: IR, out_type: str) -> IR:
    return IR(op, [a, b], out_type)


def ir_vec_op(op: str, a: IR, b: IR) -> IR:
    return IR(op, [a, b], "vec3")


def ir_mul(a: IR, b: IR) -> IR:
    return ir_binary("mul", a, b, "f32")


def replace_var(node: IR, name: str, repl: IR) -> IR:
    if node.op == "var":
        return repl
    return IR(node.op, [replace_var(a, name, repl) for a in node.args], node.type, node.value)


def _extract_vec2(expr: Expr) -> Vec2T:
    if isinstance(expr, Vec2):
        if not isinstance(expr.x, Number) or not isinstance(expr.y, Number):
            raise ValueError("vec2 components must be numeric constants")
        return (float(expr.x.value), float(expr.y.value))
    raise ValueError("polygon vertices must be vec2 constants")


def _extract_vec3(expr: Expr) -> Vec3T:
    if isinstance(expr, Vec3):
        if (
            not isinstance(expr.x, Number)
            or not isinstance(expr.y, Number)
            or not isinstance(expr.z, Number)
        ):
            raise ValueError("vec3 components must be numeric constants")
        return (float(expr.x.value), float(expr.y.value), float(expr.z.value))
    raise ValueError("path points must be vec3 constants")


def _extract_number(expr: Expr, label: str) -> float:
    if not isinstance(expr, Number):
        raise ValueError(f"{label} must be a numeric constant")
    return float(expr.value)


def _extract_polygon(expr: Expr) -> List[Vec2T]:
    if not isinstance(expr, Call) or expr.name != "polygon":
        raise ValueError("extrude expects polygon(...) as first arg")
    if len(expr.args) < 3:
        raise ValueError("polygon expects at least 3 args")
    poly = [_extract_vec2(a) for a in expr.args]
    check_polygon_simple(poly)
    if not is_convex(poly):
        raise ValueError("polygon must be convex")
    return ensure_ccw(poly)


def _extract_path(expr: Expr) -> List[Vec3T]:
    if not isinstance(expr, Call):
        raise ValueError("sweep expects line(...), polyline(...), or helix(...) as second arg")
    if expr.name == "line":
        if len(expr.args) != 2:
            raise ValueError("line expects 2 args")
        return [_extract_vec3(expr.args[0]), _extract_vec3(expr.args[1])]
    if expr.name == "polyline":
        if len(expr.args) < 2:
            raise ValueError("polyline expects at least 2 args")
        return [_extract_vec3(a) for a in expr.args]
    if expr.name == "helix":
        return _extract_helix_polyline(expr)
    raise ValueError("sweep expects line(...), polyline(...), or helix(...) as second arg")


def _extract_helix_params(expr: Call) -> tuple[float, float, float]:
    if len(expr.args) != 3:
        raise ValueError("helix expects 3 args")
    radius = _extract_number(expr.args[0], "helix arg 0")
    pitch = _extract_number(expr.args[1], "helix arg 1")
    turns = _extract_number(expr.args[2], "helix arg 2")
    return radius, pitch, turns


def _extract_helix_polyline(expr: Call) -> List[Vec3T]:
    radius, pitch, turns = _extract_helix_params(expr)
    segments_per_turn = 24
    steps = max(1, int(math.ceil(segments_per_turn * max(turns, 0.0))))
    total_angle = 6.283185307179586 * turns
    angle_step = total_angle / steps if steps > 0 else 0.0
    points: List[Vec3T] = []
    for i in range(steps + 1):
        angle = angle_step * i
        y = pitch * angle / 6.283185307179586
        x = radius * math.cos(angle)
        z = radius * math.sin(angle)
        points.append((x, y, z))
    return points


def _hexagon_vertices(radius: float) -> List[Vec2T]:
    c = 0.8660254037844386
    return [
        (radius, 0.0),
        (radius * 0.5, radius * c),
        (-radius * 0.5, radius * c),
        (-radius, 0.0),
        (-radius * 0.5, -radius * c),
        (radius * 0.5, -radius * c),
    ]


def _ir_polygon_sdf(poly: List[Vec2T], px: IR, py: IR) -> IR:
    max_d = None
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        ex, ey = x2 - x1, y2 - y1
        nx, ny = ey, -ex
        nlen = (nx * nx + ny * ny) ** 0.5
        if nlen == 0:
            continue
        nx /= nlen
        ny /= nlen

        dx = ir_binary("sub", px, ir_const(x1), "f32")
        dy = ir_binary("sub", py, ir_const(y1), "f32")
        dot = ir_binary(
            "add",
            ir_mul(ir_const(nx), dx),
            ir_mul(ir_const(ny), dy),
            "f32",
        )
        max_d = dot if max_d is None else ir_binary("max", max_d, dot, "f32")
    if max_d is None:
        raise ValueError("polygon has invalid edges")
    return max_d


def _ir_prism_sdf(poly: List[Vec2T], h: IR, px: IR, py: IR, axis: IR) -> IR:
    max_d = _ir_polygon_sdf(poly, px, py)
    d_axis = ir_binary("sub", ir_unary("abs", axis, "f32"), h, "f32")
    return ir_binary("max", max_d, d_axis, "f32")


def _ir_dot3_const(vec: IR, cx: float, cy: float, cz: float) -> IR:
    vx = ir_unary("vec_x", vec, "f32")
    vy = ir_unary("vec_y", vec, "f32")
    vz = ir_unary("vec_z", vec, "f32")
    dx = ir_mul(ir_const(cx), vx)
    dy = ir_mul(ir_const(cy), vy)
    dz = ir_mul(ir_const(cz), vz)
    return ir_binary("add", ir_binary("add", dx, dy, "f32"), dz, "f32")


def _ir_dot3(a: IR, b: IR, c: IR, x: IR, y: IR, z: IR) -> IR:
    dx = ir_mul(a, x)
    dy = ir_mul(b, y)
    dz = ir_mul(c, z)
    return ir_binary("add", ir_binary("add", dx, dy, "f32"), dz, "f32")


def _ir_clamp01(val: IR) -> IR:
    return ir_binary("min", ir_binary("max", val, ir_const(0.0), "f32"), ir_const(1.0), "f32")


def _ir_blend_sdf(sdf1: IR, sdf2: IR, t: IR) -> IR:
    """Linearly interpolate between two SDFs: (1-t)*sdf1 + t*sdf2."""
    one_minus_t = ir_binary("sub", ir_const(1.0), t, "f32")
    term1 = ir_mul(one_minus_t, sdf1)
    term2 = ir_mul(t, sdf2)
    return ir_binary("add", term1, term2, "f32")


def _ir_circle_sdf(radius: float, px: IR, py: IR) -> IR:
    """Compute 2D circle SDF given local 2D coordinates."""
    radial = ir_unary("length", ir_vec3(px, py, ir_const(0.0)), "f32")
    return ir_binary("sub", radial, ir_const(radius), "f32")


def _ir_smin(a: IR, b: IR, k: float) -> IR:
    if k <= 0.0:
        return ir_binary("min", a, b, "f32")
    inv_k = 1.0 / k
    diff = ir_binary("sub", a, b, "f32")
    adiff = ir_unary("abs", diff, "f32")
    h_raw = ir_binary("sub", ir_const(k), adiff, "f32")
    h = ir_mul(ir_binary("max", h_raw, ir_const(0.0), "f32"), ir_const(inv_k))
    h2 = ir_mul(h, h)
    h3 = ir_mul(h2, h)
    smooth = ir_mul(ir_const(k * (1.0 / 6.0)), h3)
    return ir_binary("sub", ir_binary("min", a, b, "f32"), smooth, "f32")


def lower(expr: Expr) -> IR:
    if isinstance(expr, Number):
        return ir_const(expr.value)
    if isinstance(expr, Vec3):
        return ir_vec3(lower(expr.x), lower(expr.y), lower(expr.z))
    if isinstance(expr, Call):
        name = expr.name
        if name == "sphere":
            r = lower(expr.args[0])
            p = ir_var("p")
            return ir_binary("sub", ir_unary("length", p, "f32"), r, "f32")
        if name == "circle":
            raise ValueError("circle must be used with sweep or extrude")
        if name == "cylinder":
            r = lower(expr.args[0])
            h = lower(expr.args[1])
            p = ir_var("p")
            p_abs = ir_unary("vec_abs", p, "vec3")
            y = ir_unary("vec_y", p_abs, "f32")
            neg_y = ir_unary("neg", y, "f32")
            abs_y = ir_binary("max", y, neg_y, "f32")
            dy = ir_binary("sub", abs_y, h, "f32")

            x = ir_unary("vec_x", p, "f32")
            z = ir_unary("vec_z", p, "f32")
            radial_vec = ir_vec3(x, ir_const(0.0), z)
            radial = ir_unary("length", radial_vec, "f32")
            dx = ir_binary("sub", radial, r, "f32")

            inside = ir_binary("min", ir_binary("max", dx, dy, "f32"), ir_const(0.0), "f32")
            max_dx = ir_binary("max", dx, ir_const(0.0), "f32")
            max_dy = ir_binary("max", dy, ir_const(0.0), "f32")
            out = ir_unary("length", ir_vec3(max_dx, max_dy, ir_const(0.0)), "f32")
            return ir_binary("add", inside, out, "f32")
        if name == "box":
            size = lower(expr.args[0])
            p = ir_var("p")
            q = ir_vec_op("vec_sub", ir_unary("vec_abs", p, "vec3"), size)
            qmax = ir_vec_op("vec_max", q, ir_vec3(ir_const(0.0), ir_const(0.0), ir_const(0.0)))
            d1 = ir_unary("length", qmax, "f32")
            qx = ir_unary("vec_x", q, "f32")
            qy = ir_unary("vec_y", q, "f32")
            qz = ir_unary("vec_z", q, "f32")
            max1 = ir_binary("max", qx, qy, "f32")
            max2 = ir_binary("max", max1, qz, "f32")
            d2 = ir_binary("min", max2, ir_const(0.0), "f32")
            return ir_binary("add", d1, d2, "f32")
        if name == "union":
            if len(expr.args) < 2:
                raise ValueError("union expects at least 2 args")
            cur = lower(expr.args[0])
            for arg in expr.args[1:]:
                cur = ir_binary("min", cur, lower(arg), "f32")
            return cur
        if name == "difference":
            a = lower(expr.args[0])
            b = lower(expr.args[1])
            return ir_binary("max", a, ir_unary("neg", b, "f32"), "f32")
        if name == "polygon":
            raise ValueError("polygon must be used with extrude")
        if name == "line" or name == "polyline":
            raise ValueError("path must be used with sweep")
        if name == "extrude":
            profile = expr.args[0]
            h = lower(expr.args[1])
            p = ir_var("p")
            px = ir_unary("vec_x", p, "f32")
            py = ir_unary("vec_y", p, "f32")
            pz = ir_unary("vec_z", p, "f32")
            if isinstance(profile, Call) and profile.name == "polygon":
                poly = _extract_polygon(profile)
                return _ir_prism_sdf(poly, h, px, py, pz)
            if isinstance(profile, Call) and profile.name == "circle":
                if len(profile.args) != 1:
                    raise ValueError("circle expects 1 arg")
                r = ir_const(_extract_number(profile.args[0], "circle arg 0"))
                radial = ir_unary("length", ir_vec3(px, py, ir_const(0.0)), "f32")
                dx = ir_binary("sub", radial, r, "f32")
                dz = ir_binary("sub", ir_unary("abs", pz, "f32"), h, "f32")
                inside = ir_binary("min", ir_binary("max", dx, dz, "f32"), ir_const(0.0), "f32")
                max_dx = ir_binary("max", dx, ir_const(0.0), "f32")
                max_dz = ir_binary("max", dz, ir_const(0.0), "f32")
                out = ir_unary("length", ir_vec3(max_dx, max_dz, ir_const(0.0)), "f32")
                return ir_binary("add", inside, out, "f32")
            raise ValueError("extrude expects polygon(...) or circle(...) as first arg")
        if name == "hex_nut":
            if len(expr.args) != 3:
                raise ValueError("hex_nut expects 3 args")
            outer_r = _extract_number(expr.args[0], "hex_nut arg 0")
            inner_r = _extract_number(expr.args[1], "hex_nut arg 1")
            half_h = _extract_number(expr.args[2], "hex_nut arg 2")

            poly = _hexagon_vertices(outer_r)
            poly_args = [Vec2(Number(x), Number(y)) for x, y in poly]
            prism = Call(
                "rotate",
                [
                    Call("extrude", [Call("polygon", poly_args), Number(half_h)]),
                    Vec3(Number(90.0), Number(0.0), Number(0.0)),
                ],
            )
            hole_half_h = half_h + 0.01
            hole = Call("cylinder", [Number(inner_r), Number(hole_half_h)])
            return lower(Call("difference", [prism, hole]))
        if name == "blend2D":
            if len(expr.args) != 3:
                raise ValueError("blend2D expects 3 args: profile1, profile2, path")
            
            profile1 = expr.args[0]
            profile2 = expr.args[1]
            path_expr = expr.args[2]
            
            # Extract both profiles
            def get_profile_data(profile: Expr) -> tuple[str, List[Vec2T] | float]:
                if isinstance(profile, Call):
                    if profile.name == "polygon":
                        return ("polygon", _extract_polygon(profile))
                    elif profile.name == "circle":
                        if len(profile.args) != 1:
                            raise ValueError("circle expects 1 arg")
                        return ("circle", _extract_number(profile.args[0], "circle radius"))
                raise ValueError("blend2D expects polygon(...) or circle(...) profiles")
            
            profile1_kind, profile1_data = get_profile_data(profile1)
            profile2_kind, profile2_data = get_profile_data(profile2)
            
            # Extract path
            path = _extract_path(path_expr)
            if len(path) < 2:
                raise ValueError("blend2D path must have at least 2 points")
            
            # Compute total path length for global t parameter
            segments = []
            total_length = 0.0
            for i in range(len(path) - 1):
                ax, ay, az = path[i]
                bx, by, bz = path[i + 1]
                abx = bx - ax
                aby = by - ay
                abz = bz - az
                seg_len = math.sqrt(abx * abx + aby * aby + abz * abz)
                if seg_len == 0.0:
                    continue
                segments.append((ax, ay, az, bx, by, bz, abx, aby, abz, seg_len, total_length))
                total_length += seg_len
            
            if not segments:
                raise ValueError("blend2D path has no valid segments")
            
            if total_length == 0.0:
                raise ValueError("blend2D path has zero length")
            
            inv_total_length = 1.0 / total_length
            
            p = ir_var("p")
            cur = None
            
            for seg_data in segments:
                ax, ay, az, bx, by, bz, abx, aby, abz, seg_len, cum_len = seg_data
                
                # Tangent vector
                tx = abx / seg_len
                ty = aby / seg_len
                tz = abz / seg_len
                
                # Compute normal and binormal for local frame
                upx, upy, upz = 0.0, 1.0, 0.0
                if abs(tx * upx + ty * upy + tz * upz) > 0.999:
                    upx, upy, upz = 1.0, 0.0, 0.0
                
                nx = upy * tz - upz * ty
                ny = upz * tx - upx * tz
                nz = upx * ty - upy * tx
                nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
                if nlen == 0.0:
                    continue
                nx /= nlen
                ny /= nlen
                nz /= nlen
                
                bxv = ty * nz - tz * ny
                byv = tz * nx - tx * nz
                bzv = tx * ny - ty * nx
                
                # Project point onto segment
                a_vec = ir_vec3(ir_const(ax), ir_const(ay), ir_const(az))
                pa = ir_vec_op("vec_sub", p, a_vec)
                dot_pa_ab = _ir_dot3_const(pa, abx, aby, abz)
                seg_len_sq = seg_len * seg_len
                t_seg = ir_mul(dot_pa_ab, ir_const(1.0 / seg_len_sq))
                t_seg_clamped = _ir_clamp01(t_seg)
                
                # Closest point on segment
                ab_scaled = ir_vec3(
                    ir_mul(ir_const(abx), t_seg_clamped),
                    ir_mul(ir_const(aby), t_seg_clamped),
                    ir_mul(ir_const(abz), t_seg_clamped),
                )
                c = ir_vec_op("vec_add", a_vec, ab_scaled)
                q = ir_vec_op("vec_sub", p, c)
                
                # Local 2D coordinates in profile plane
                px = _ir_dot3_const(q, nx, ny, nz)
                py = _ir_dot3_const(q, bxv, byv, bzv)
                qt = _ir_dot3_const(q, tx, ty, tz)
                
                # Global t parameter (0 at start, 1 at end of path)
                # t_global = (cum_len + t_seg * seg_len) / total_length
                t_offset = ir_mul(t_seg_clamped, ir_const(seg_len))
                t_global = ir_mul(
                    ir_binary("add", ir_const(cum_len), t_offset, "f32"),
                    ir_const(inv_total_length)
                )
                
                # Compute SDF for profile1
                if profile1_kind == "circle":
                    sdf1 = _ir_circle_sdf(profile1_data, px, py)
                else:
                    sdf1 = _ir_polygon_sdf(profile1_data, px, py)
                
                # Compute SDF for profile2
                if profile2_kind == "circle":
                    sdf2 = _ir_circle_sdf(profile2_data, px, py)
                else:
                    sdf2 = _ir_polygon_sdf(profile2_data, px, py)
                
                # Blend profiles based on global t
                profile_blend = _ir_blend_sdf(sdf1, sdf2, t_global)
                
                # Combine with tangential distance (cap ends)
                seg = ir_binary("max", profile_blend, ir_unary("abs", qt, "f32"), "f32")
                
                # Accumulate segments with min
                if cur is None:
                    cur = seg
                else:
                    cur = ir_binary("min", cur, seg, "f32")
            
            return cur
        if name == "sweep":
            if len(expr.args) != 2:
                raise ValueError("sweep expects 2 args")
            profile = expr.args[0]
            path_expr = expr.args[1]

            profile_kind = ""
            profile_poly: List[Vec2T] = []
            profile_radius = 0.0
            if isinstance(profile, Call) and profile.name == "polygon":
                profile_kind = "polygon"
                profile_poly = _extract_polygon(profile)
            elif isinstance(profile, Call) and profile.name == "circle":
                if len(profile.args) != 1:
                    raise ValueError("circle expects 1 arg")
                profile_kind = "circle"
                profile_radius = _extract_number(profile.args[0], "circle arg 0")
            else:
                raise ValueError("sweep expects polygon(...) or circle(...) as first arg")

            if isinstance(path_expr, Call) and path_expr.name == "helix":
                radius, pitch, turns = _extract_helix_params(path_expr)
                two_pi = 6.283185307179586
                h = pitch / two_pi
                total_angle = two_pi * max(turns, 0.0)

                p = ir_var("p")
                p_x = ir_unary("vec_x", p, "f32")
                p_y = ir_unary("vec_y", p, "f32")
                p_z = ir_unary("vec_z", p, "f32")

                angle = ir_binary("atan2", p_z, p_x, "f32")
                angle_div = ir_mul(angle, ir_const(1.0 / two_pi))
                angle_mod = ir_binary(
                    "sub",
                    angle,
                    ir_mul(ir_const(two_pi), ir_unary("floor", angle_div, "f32")),
                    "f32",
                )

                y_over_h = ir_mul(p_y, ir_const(1.0 / h)) if h != 0.0 else ir_const(0.0)
                k_num = ir_binary("sub", y_over_h, angle_mod, "f32")
                k_div = ir_mul(k_num, ir_const(1.0 / two_pi))
                k = ir_unary("floor", ir_binary("add", k_div, ir_const(0.5), "f32"), "f32")

                t = ir_binary("add", angle_mod, ir_mul(ir_const(two_pi), k), "f32")
                if total_angle > 0.0:
                    t = ir_binary(
                        "min",
                        ir_binary("max", t, ir_const(0.0), "f32"),
                        ir_const(total_angle),
                        "f32",
                    )

                sin_t = ir_unary("sin", t, "f32")
                cos_t = ir_unary("cos", t, "f32")

                hx = ir_mul(ir_const(radius), cos_t)
                hz = ir_mul(ir_const(radius), sin_t)
                hy = ir_mul(ir_const(h), t)
                helix_pos = ir_vec3(hx, hy, hz)
                q = ir_vec_op("vec_sub", p, helix_pos)

                if profile_kind == "circle":
                    d = ir_binary(
                        "sub",
                        ir_unary("length", q, "f32"),
                        ir_const(profile_radius),
                        "f32",
                    )
                else:
                    inv_tlen = 0.0
                    tlen = (radius * radius + h * h) ** 0.5
                    if tlen > 0.0:
                        inv_tlen = 1.0 / tlen

                    nx = cos_t
                    ny = ir_const(0.0)
                    nz = sin_t

                    tx = ir_mul(ir_const(-radius * inv_tlen), sin_t)
                    ty = ir_const(h * inv_tlen)
                    tz = ir_mul(ir_const(radius * inv_tlen), cos_t)

                    bx = ir_mul(ty, nz)
                    by = ir_binary("sub", ir_mul(tz, nx), ir_mul(tx, nz), "f32")
                    bz = ir_mul(ir_unary("neg", ty, "f32"), nx)

                    qx = ir_unary("vec_x", q, "f32")
                    qy = ir_unary("vec_y", q, "f32")
                    qz = ir_unary("vec_z", q, "f32")

                    px = _ir_dot3(qx, qy, qz, nx, ny, nz)
                    py = _ir_dot3(qx, qy, qz, bx, by, bz)
                    qt = _ir_dot3(qx, qy, qz, tx, ty, tz)

                    profile_d = _ir_polygon_sdf(profile_poly, px, py)
                    d = ir_binary("max", profile_d, ir_unary("abs", qt, "f32"), "f32")

                if total_angle > 0.0:
                    d_cap = ir_binary(
                        "max",
                        ir_unary("neg", p_y, "f32"),
                        ir_binary("sub", p_y, ir_const(h * total_angle), "f32"),
                        "f32",
                    )
                    d = ir_binary("max", d, d_cap, "f32")
                return d

            path = _extract_path(path_expr)
            if len(path) < 2:
                raise ValueError("sweep path must have at least 2 points")

            segments = []
            for i in range(len(path) - 1):
                ax, ay, az = path[i]
                bx, by, bz = path[i + 1]
                abx = bx - ax
                aby = by - ay
                abz = bz - az
                len2 = abx * abx + aby * aby + abz * abz
                if len2 == 0.0:
                    continue
                tlen = math.sqrt(len2)
                tx = abx / tlen
                ty = aby / tlen
                tz = abz / tlen
                segments.append((ax, ay, az, bx, by, bz, abx, aby, abz, len2, tx, ty, tz))

            if not segments:
                raise ValueError("sweep path has no valid segments")

            use_round_segments = profile_kind == "circle"
            join_smooth: List[float] = []
            if use_round_segments:
                for i in range(1, len(segments)):
                    _, _, _, _, _, _, _, _, _, _, ptx, pty, ptz = segments[i - 1]
                    _, _, _, _, _, _, _, _, _, _, ctx, cty, ctz = segments[i]
                    dot = ptx * ctx + pty * cty + ptz * ctz
                    dot = max(-1.0, min(1.0, dot))
                    k = profile_radius * max(0.0, (1.0 - dot) * 0.5)
                    join_smooth.append(k)

            p = ir_var("p")
            cur = None
            last_idx = len(segments) - 1
            for idx, seg_data in enumerate(segments):
                ax, ay, az, bx, by, bz, abx, aby, abz, len2, tx, ty, tz = seg_data
                inv_len2 = 1.0 / len2

                upx, upy, upz = 0.0, 1.0, 0.0
                if abs(tx * upx + ty * upy + tz * upz) > 0.999:
                    upx, upy, upz = 1.0, 0.0, 0.0

                nx = upy * tz - upz * ty
                ny = upz * tx - upx * tz
                nz = upx * ty - upy * tx
                nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
                if nlen == 0.0:
                    continue
                nx /= nlen
                ny /= nlen
                nz /= nlen

                bxv = ty * nz - tz * ny
                byv = tz * nx - tx * nz
                bzv = tx * ny - ty * nx

                a_vec = ir_vec3(ir_const(ax), ir_const(ay), ir_const(az))
                ab_vec = ir_vec3(ir_const(abx), ir_const(aby), ir_const(abz))
                pa = ir_vec_op("vec_sub", p, a_vec)
                dot_pa_ab = _ir_dot3_const(pa, abx, aby, abz)
                t_raw = ir_mul(dot_pa_ab, ir_const(inv_len2))
                t_clamped = _ir_clamp01(t_raw)

                ab_scaled = ir_vec3(
                    ir_mul(ir_const(abx), t_clamped),
                    ir_mul(ir_const(aby), t_clamped),
                    ir_mul(ir_const(abz), t_clamped),
                )
                c = ir_vec_op("vec_add", a_vec, ab_scaled)
                q = ir_vec_op("vec_sub", p, c)

                px = _ir_dot3_const(q, nx, ny, nz)
                py = _ir_dot3_const(q, bxv, byv, bzv)
                qt = _ir_dot3_const(q, tx, ty, tz)

                if profile_kind == "circle":
                    if use_round_segments and idx not in (0, last_idx):
                        qlen = ir_unary("length", ir_vec3(px, py, qt), "f32")
                        seg = ir_binary("sub", qlen, ir_const(profile_radius), "f32")
                    else:
                        radial = ir_unary("length", ir_vec3(px, py, ir_const(0.0)), "f32")
                        profile_d = ir_binary("sub", radial, ir_const(profile_radius), "f32")
                        seg = ir_binary("max", profile_d, ir_unary("abs", qt, "f32"), "f32")
                else:
                    profile_d = _ir_polygon_sdf(profile_poly, px, py)
                    seg = ir_binary("max", profile_d, ir_unary("abs", qt, "f32"), "f32")

                if cur is None:
                    cur = seg
                else:
                    if use_round_segments:
                        k = join_smooth[idx - 1] if idx - 1 < len(join_smooth) else 0.0
                        cur = _ir_smin(cur, seg, k) if k > 0.0 else ir_binary("min", cur, seg, "f32")
                    else:
                        cur = ir_binary("min", cur, seg, "f32")

            return cur
        if name == "rotate":
            g = lower(expr.args[0])
            angles = lower(expr.args[1])
            p = ir_var("p")

            deg_to_rad = ir_const(0.017453292519943295)
            ax = ir_mul(ir_unary("neg", ir_unary("vec_x", angles, "f32"), "f32"), deg_to_rad)
            ay = ir_mul(ir_unary("neg", ir_unary("vec_y", angles, "f32"), "f32"), deg_to_rad)
            az = ir_mul(ir_unary("neg", ir_unary("vec_z", angles, "f32"), "f32"), deg_to_rad)

            cx = ir_unary("cos", ax, "f32")
            sx = ir_unary("sin", ax, "f32")
            cy = ir_unary("cos", ay, "f32")
            sy = ir_unary("sin", ay, "f32")
            cz = ir_unary("cos", az, "f32")
            sz = ir_unary("sin", az, "f32")

            x0 = ir_unary("vec_x", p, "f32")
            y0 = ir_unary("vec_y", p, "f32")
            z0 = ir_unary("vec_z", p, "f32")

            y1 = ir_binary("sub", ir_mul(y0, cx), ir_mul(z0, sx), "f32")
            z1 = ir_binary("add", ir_mul(y0, sx), ir_mul(z0, cx), "f32")
            x1 = x0

            x2 = ir_binary("add", ir_mul(x1, cy), ir_mul(z1, sy), "f32")
            z2 = ir_binary("add", ir_mul(ir_unary("neg", x1, "f32"), sy), ir_mul(z1, cy), "f32")
            y2 = y1

            x3 = ir_binary("sub", ir_mul(x2, cz), ir_mul(y2, sz), "f32")
            y3 = ir_binary("add", ir_mul(x2, sz), ir_mul(y2, cz), "f32")
            z3 = z2

            rotated = ir_vec3(x3, y3, z3)
            return replace_var(g, "p", rotated)
        if name == "translate":
            g = lower(expr.args[0])
            v = lower(expr.args[1])
            p = ir_var("p")
            shifted = ir_vec_op("vec_sub", p, v)
            return replace_var(g, "p", shifted)
        if name == "offset":
            g = lower(expr.args[0])
            d = lower(expr.args[1])
            return ir_binary("sub", g, d, "f32")
        if name == "vec3":
            return ir_vec3(lower(expr.args[0]), lower(expr.args[1]), lower(expr.args[2]))
    raise ValueError("Unknown expression")


def pretty_ir(node: IR, indent: str = "") -> str:
    lines: List[str] = []
    head = node.op
    if node.op == "const":
        head += f"({node.value})"
    elif node.op == "var":
        head += "(p)"
    head += f" : {node.type}"
    lines.append(indent + head)
    for arg in node.args:
        lines.append(pretty_ir(arg, indent + "  "))
    return "\n".join(lines)
