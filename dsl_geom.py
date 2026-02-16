from typing import List, Tuple


Vec2 = Tuple[float, float]


def seg_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> bool:
    def orient(p: Vec2, q: Vec2, r: Vec2) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: Vec2, q: Vec2, r: Vec2) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)

    if o1 == 0 and on_segment(a, c, b):
        return True
    if o2 == 0 and on_segment(a, d, b):
        return True
    if o3 == 0 and on_segment(c, a, d):
        return True
    if o4 == 0 and on_segment(c, b, d):
        return True

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def check_polygon_simple(poly: List[Vec2]) -> None:
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            c = poly[j]
            d = poly[(j + 1) % n]
            if seg_intersect(a, b, c, d):
                raise ValueError("polygon is self-intersecting")


def is_convex(poly: List[Vec2]) -> bool:
    n = len(poly)
    sign = 0
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        c = poly[(i + 2) % n]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cross == 0:
            continue
        cur = 1 if cross > 0 else -1
        if sign == 0:
            sign = cur
        elif sign != cur:
            return False
    return True


def ensure_ccw(poly: List[Vec2]) -> List[Vec2]:
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        area += x1 * y2 - x2 * y1
    if area < 0:
        return list(reversed(poly))
    return poly
