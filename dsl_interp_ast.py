from typing import Callable, Tuple, Union

from dsl_ast import Call, Expr, Number, Vec3


Vec = Tuple[float, float, float]
Field = Callable[[Vec], float]
Value = Union[float, Vec, Field]


class EvalError(Exception):
    pass


def v_add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_abs(a: Vec) -> Vec:
    return (abs(a[0]), abs(a[1]), abs(a[2]))


def v_max(a: Vec, b: Vec) -> Vec:
    return (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))


def v_len(a: Vec) -> float:
    return (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5


def sdf_sphere(r: float) -> Field:
    return lambda p: v_len(p) - r


def sdf_box(size: Vec) -> Field:
    def field(p: Vec) -> float:
        q = v_sub(v_abs(p), size)
        qmax = v_max(q, (0.0, 0.0, 0.0))
        d1 = v_len(qmax)
        d2 = min(max(q[0], max(q[1], q[2])), 0.0)
        return d1 + d2

    return field


def sdf_cylinder(r: float, h: float) -> Field:
    def field(p: Vec) -> float:
        x, y, z = p
        dx = (x * x + z * z) ** 0.5 - r
        dy = abs(y) - h
        inside = min(max(dx, dy), 0.0)
        out = (max(dx, 0.0) ** 2 + max(dy, 0.0) ** 2) ** 0.5
        return inside + out

    return field


def eval_expr(expr: Expr) -> Value:
    if isinstance(expr, Number):
        return expr.value
    if isinstance(expr, Vec3):
        x = eval_expr(expr.x)
        y = eval_expr(expr.y)
        z = eval_expr(expr.z)
        if not isinstance(x, float) or not isinstance(y, float) or not isinstance(z, float):
            raise EvalError("vec3 components must be numbers")
        return (x, y, z)
    if isinstance(expr, Call):
        name = expr.name
        args = [eval_expr(a) for a in expr.args]
        if name == "sphere":
            return sdf_sphere(args[0])  # type: ignore[index]
        if name == "cylinder":
            return sdf_cylinder(args[0], args[1])  # type: ignore[index]
        if name == "box":
            return sdf_box(args[0])  # type: ignore[index]
        if name == "union":
            if len(args) < 2:
                raise EvalError("union expects at least 2 args")
            fields = args  # type: ignore[assignment]
            return lambda p: min(f(p) for f in fields)
        if name == "difference":
            a, b = args  # type: ignore[misc]
            return lambda p: max(a(p), -b(p))
        if name == "translate":
            g, v = args  # type: ignore[misc]
            return lambda p: g(v_sub(p, v))
        if name == "offset":
            g, d = args  # type: ignore[misc]
            return lambda p: g(p) - d
        raise EvalError(f"Unknown function {name}")
    raise EvalError("Unknown expression")
