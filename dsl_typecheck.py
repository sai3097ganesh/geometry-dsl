from dataclasses import dataclass
from typing import Dict, List, Tuple

from dsl_ast import Call, Expr, Number, Vec3


class TypeError(Exception):
    pass


@dataclass(frozen=True)
class Type:
    name: str


F32 = Type("f32")
VEC3 = Type("vec3")
FIELD = Type("field")


SIGS: Dict[str, Tuple[List[Type], Type]] = {
    "sphere": ([F32], FIELD),
    "cylinder": ([F32, F32], FIELD),
    "box": ([VEC3], FIELD),
    "difference": ([FIELD, FIELD], FIELD),
    "rotate": ([FIELD, VEC3], FIELD),
    "translate": ([FIELD, VEC3], FIELD),
    "offset": ([FIELD, F32], FIELD),
    "vec3": ([F32, F32, F32], VEC3),
}


def type_of(expr: Expr) -> Type:
    if isinstance(expr, Number):
        return F32
    if isinstance(expr, Vec3):
        for comp in (expr.x, expr.y, expr.z):
            if type_of(comp) != F32:
                raise TypeError("vec3 components must be f32")
        return VEC3
    if isinstance(expr, Call):
        if expr.name == "union":
            if len(expr.args) < 2:
                raise TypeError("union expects at least 2 args")
            for idx, arg in enumerate(expr.args):
                got = type_of(arg)
                if got != FIELD:
                    raise TypeError(f"union arg {idx} expects field, got {got.name}")
            return FIELD
        if expr.name not in SIGS:
            raise TypeError(f"Unknown function {expr.name}")
        expected_args, ret = SIGS[expr.name]
        if len(expr.args) != len(expected_args):
            raise TypeError(f"{expr.name} expects {len(expected_args)} args")
        for idx, (arg, exp) in enumerate(zip(expr.args, expected_args)):
            got = type_of(arg)
            if got != exp:
                raise TypeError(f"{expr.name} arg {idx} expects {exp.name}, got {got.name}")
        return ret
    raise TypeError("Unknown expression")
