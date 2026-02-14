from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openrouter_client import chat
from dsl_prompt import dsl_system_prompt

from dsl_interp_ir import eval_ir
from dsl_ir import lower
from dsl_parser import Parser
from dsl_glsl_ir import emit_glsl


class CompileRequest(BaseModel):
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
