from dsl_interp_ast import eval_expr
from dsl_interp_ir import eval_ir
from dsl_ir import lower
from dsl_parser import Parser
from dsl_typecheck import FIELD, type_of
from dsl_glsl import emit_glsl


def test_lexer_and_parser() -> None:
    src = "sphere(1)"
    ast = Parser.from_source(src).parse()
    assert ast is not None


def test_typecheck() -> None:
    src = "union(sphere(1), sphere(2), sphere(3))"
    ast = Parser.from_source(src).parse()
    assert type_of(ast) == FIELD


def test_ast_eval() -> None:
    src = "translate(sphere(1), vec3(1, 0, 0))"
    ast = Parser.from_source(src).parse()
    field = eval_expr(ast)
    v = field((1.0, 0.0, 0.0))
    assert abs(v - (-1.0)) < 1e-6


def test_ir_eval() -> None:
    src = "difference(sphere(1), sphere(0.5))"
    ast = Parser.from_source(src).parse()
    ir = lower(ast)
    v = eval_ir(ir, {"p": (0.0, 0.0, 0.0)})
    assert abs(v - 0.5) < 1e-6


def test_glsl_emit() -> None:
    src = "union(sphere(1), cylinder(0.5, 1), box(vec3(1,1,1)))"
    ast = Parser.from_source(src).parse()
    ir = lower(ast)
    code = emit_glsl(ir)
    assert "float field" in code


def run_all() -> None:
    test_lexer_and_parser()
    test_typecheck()
    test_ast_eval()
    test_ir_eval()
    test_glsl_emit()
    print("ok")


if __name__ == "__main__":
    run_all()
