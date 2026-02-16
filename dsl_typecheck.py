from dataclasses import dataclass
from typing import Dict, List, Tuple

from dsl_ast import Call, Expr, Number, Vec2, Vec3


class TypeError(Exception):
    pass


@dataclass(frozen=True)
class Type:
    name: str


F32 = Type("f32")
VEC3 = Type("vec3")
VEC2 = Type("vec2")
FIELD = Type("field")
POLY2D = Type("poly2d")
CIRCLE2D = Type("circle2d")
PATH = Type("path")


SIGS: Dict[str, Tuple[List[Type], Type]] = {
    "sphere": ([F32], FIELD),
    "cylinder": ([F32, F32], FIELD),
    "box": ([VEC3], FIELD),
    "hex_nut": ([F32, F32, F32], FIELD),
    "difference": ([FIELD, FIELD], FIELD),
    "rotate": ([FIELD, VEC3], FIELD),
    "translate": ([FIELD, VEC3], FIELD),
    "offset": ([FIELD, F32], FIELD),
    "vec2": ([F32, F32], VEC2),
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
    if isinstance(expr, Vec2):
        for comp in (expr.x, expr.y):
            if type_of(comp) != F32:
                raise TypeError("vec2 components must be f32")
        return VEC2
    if isinstance(expr, Call):
        if expr.name == "union":
            if len(expr.args) < 2:
                raise TypeError("union expects at least 2 args")
            for idx, arg in enumerate(expr.args):
                got = type_of(arg)
                if got != FIELD:
                    raise TypeError(f"union arg {idx} expects field, got {got.name}")
            return FIELD
        if expr.name == "circle":
            if len(expr.args) != 1:
                raise TypeError("circle expects 1 arg")
            if type_of(expr.args[0]) != F32:
                raise TypeError("circle arg 0 expects f32")
            return CIRCLE2D
        if expr.name == "polygon":
            if len(expr.args) < 3:
                raise TypeError("polygon expects at least 3 args")
            for idx, arg in enumerate(expr.args):
                got = type_of(arg)
                if got != VEC2:
                    raise TypeError(f"polygon arg {idx} expects vec2, got {got.name}")
            return POLY2D
        if expr.name == "line":
            if len(expr.args) != 2:
                raise TypeError("line expects 2 args")
            for idx, arg in enumerate(expr.args):
                got = type_of(arg)
                if got != VEC3:
                    raise TypeError(f"line arg {idx} expects vec3, got {got.name}")
            return PATH
        if expr.name == "polyline":
            if len(expr.args) < 2:
                raise TypeError("polyline expects at least 2 args")
            for idx, arg in enumerate(expr.args):
                got = type_of(arg)
                if got != VEC3:
                    raise TypeError(f"polyline arg {idx} expects vec3, got {got.name}")
            return PATH
        if expr.name == "extrude":
            if len(expr.args) != 2:
                raise TypeError("extrude expects 2 args")
            shape_type = type_of(expr.args[0])
            if shape_type not in (POLY2D, CIRCLE2D):
                raise TypeError(
                    f"extrude arg 0 expects poly2d or circle2d, got {shape_type.name}"
                )
            if type_of(expr.args[1]) != F32:
                raise TypeError("extrude arg 1 expects f32")
            return FIELD
        if expr.name == "sweep":
            if len(expr.args) != 2:
                raise TypeError("sweep expects 2 args")
            profile_type = type_of(expr.args[0])
            if profile_type not in (POLY2D, CIRCLE2D):
                raise TypeError(
                    f"sweep arg 0 expects poly2d or circle2d, got {profile_type.name}"
                )
            if type_of(expr.args[1]) != PATH:
                raise TypeError("sweep arg 1 expects path")
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
