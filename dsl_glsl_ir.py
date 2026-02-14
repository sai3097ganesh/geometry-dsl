from dsl_ir import IR


def _fmt_f(v: float) -> str:
    if float(v).is_integer():
        return f"{int(v)}.0"
    return f"{v}"


def emit_expr(node: IR) -> str:
    op = node.op
    if op == "const":
        return _fmt_f(float(node.value or 0.0))
    if op == "vec3":
        x, y, z = (emit_expr(a) for a in node.args)
        return f"vec3({x}, {y}, {z})"
    if op == "var":
        return "p"
    if op == "add":
        return f"({emit_expr(node.args[0])} + {emit_expr(node.args[1])})"
    if op == "sub":
        return f"({emit_expr(node.args[0])} - {emit_expr(node.args[1])})"
    if op == "neg":
        return f"(-{emit_expr(node.args[0])})"
    if op == "min":
        return f"min({emit_expr(node.args[0])}, {emit_expr(node.args[1])})"
    if op == "max":
        return f"max({emit_expr(node.args[0])}, {emit_expr(node.args[1])})"
    if op == "length":
        return f"length({emit_expr(node.args[0])})"
    if op == "vec_add":
        return f"({emit_expr(node.args[0])} + {emit_expr(node.args[1])})"
    if op == "vec_sub":
        return f"({emit_expr(node.args[0])} - {emit_expr(node.args[1])})"
    if op == "vec_abs":
        return f"abs({emit_expr(node.args[0])})"
    if op == "vec_max":
        return f"max({emit_expr(node.args[0])}, {emit_expr(node.args[1])})"
    if op == "vec_x":
        return f"{emit_expr(node.args[0])}.x"
    if op == "vec_y":
        return f"{emit_expr(node.args[0])}.y"
    if op == "vec_z":
        return f"{emit_expr(node.args[0])}.z"
    raise ValueError(f"Unknown op {op}")


def emit_glsl(node: IR) -> str:
    expr = emit_expr(node)
    return "float sdf(vec3 p) {\n    return " + expr + ";\n}\n"
