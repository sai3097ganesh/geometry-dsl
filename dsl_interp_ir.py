from typing import Dict, Tuple

from dsl_ir import IR


Vec = Tuple[float, float, float]


class IREvalError(Exception):
    pass


def eval_ir(node: IR, env: Dict[str, Vec]) -> float | Vec:
    op = node.op
    if op == "const":
        return float(node.value or 0.0)
    if op == "vec3":
        x, y, z = (eval_ir(a, env) for a in node.args)
        return (float(x), float(y), float(z))
    if op == "var":
        return env["p"]
    if op == "add":
        return float(eval_ir(node.args[0], env)) + float(eval_ir(node.args[1], env))
    if op == "sub":
        return float(eval_ir(node.args[0], env)) - float(eval_ir(node.args[1], env))
    if op == "neg":
        return -float(eval_ir(node.args[0], env))
    if op == "min":
        return min(float(eval_ir(node.args[0], env)), float(eval_ir(node.args[1], env)))
    if op == "max":
        return max(float(eval_ir(node.args[0], env)), float(eval_ir(node.args[1], env)))
    if op == "abs":
        return abs(float(eval_ir(node.args[0], env)))
    if op == "length":
        v = eval_ir(node.args[0], env)
        return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    if op == "vec_add":
        a = eval_ir(node.args[0], env)
        b = eval_ir(node.args[1], env)
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
    if op == "vec_sub":
        a = eval_ir(node.args[0], env)
        b = eval_ir(node.args[1], env)
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    if op == "vec_abs":
        a = eval_ir(node.args[0], env)
        return (abs(a[0]), abs(a[1]), abs(a[2]))
    if op == "vec_max":
        a = eval_ir(node.args[0], env)
        b = eval_ir(node.args[1], env)
        return (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))
    if op == "vec_x":
        a = eval_ir(node.args[0], env)
        return float(a[0])
    if op == "vec_y":
        a = eval_ir(node.args[0], env)
        return float(a[1])
    if op == "vec_z":
        a = eval_ir(node.args[0], env)
        return float(a[2])
    raise IREvalError(f"Unknown op {op}")
