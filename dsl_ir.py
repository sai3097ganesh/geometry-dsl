from dataclasses import dataclass
from typing import List

from dsl_ast import Call, Expr, Number, Vec3


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


def replace_var(node: IR, name: str, repl: IR) -> IR:
    if node.op == "var":
        return repl
    return IR(node.op, [replace_var(a, name, repl) for a in node.args], node.type, node.value)


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
