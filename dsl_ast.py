from dataclasses import dataclass
from typing import List, Union


@dataclass
class Number:
    value: float


@dataclass
class Vec3:
    x: "Expr"
    y: "Expr"
    z: "Expr"


@dataclass
class Vec2:
    x: "Expr"
    y: "Expr"


@dataclass
class Call:
    name: str
    args: List["Expr"]


Expr = Union[Number, Vec3, Vec2, Call]
