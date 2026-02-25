from typing import List, Tuple


Vec2 = Tuple[float, float]


def _cross(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle(p: Vec2, a: Vec2, b: Vec2, c: Vec2) -> bool:
    c1 = _cross(a, b, p)
    c2 = _cross(b, c, p)
    c3 = _cross(c, a, p)
    has_neg = (c1 < 0.0) or (c2 < 0.0) or (c3 < 0.0)
    has_pos = (c1 > 0.0) or (c2 > 0.0) or (c3 > 0.0)
    return not (has_neg and has_pos)


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


def triangulate_polygon(poly: List[Vec2]) -> List[Tuple[Vec2, Vec2, Vec2]]:
    if len(poly) < 3:
        raise ValueError("polygon expects at least 3 vertices")

    verts = ensure_ccw(poly)
    indices = list(range(len(verts)))
    triangles: List[Tuple[Vec2, Vec2, Vec2]] = []

    guard = 0
    while len(indices) > 3:
        guard += 1
        if guard > len(verts) * len(verts):
            raise ValueError("failed to triangulate polygon")

        ear_found = False
        for i in range(len(indices)):
            ia = indices[(i - 1) % len(indices)]
            ib = indices[i]
            ic = indices[(i + 1) % len(indices)]
            a = verts[ia]
            b = verts[ib]
            c = verts[ic]

            if _cross(a, b, c) <= 0.0:
                continue

            contains_other = False
            for idx in indices:
                if idx in (ia, ib, ic):
                    continue
                if _point_in_triangle(verts[idx], a, b, c):
                    contains_other = True
                    break
            if contains_other:
                continue

            triangles.append((a, b, c))
            del indices[i]
            ear_found = True
            break

        if not ear_found:
            raise ValueError("failed to triangulate polygon")

    a = verts[indices[0]]
    b = verts[indices[1]]
    c = verts[indices[2]]
    triangles.append((a, b, c))
    return triangles
