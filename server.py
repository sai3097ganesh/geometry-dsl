from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dsl_interp_ir import eval_ir
from dsl_ir import lower
from dsl_parser import Parser
from dsl_glsl_ir import emit_glsl


class CompileRequest(BaseModel):
    code: str


class EvalRequest(BaseModel):
    code: str
    p: list[float]


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


@app.post("/eval")
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
