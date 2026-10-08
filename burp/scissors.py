"""The scissor cut around a cut-out: a few straight snips, with a little paper left around
the object, as if cut by hand from a photocopy.

From the object's mask: the convex hull, grown by a margin of paper, then reduced to 6-10
straight sides without ever cutting into the object, with a little irregularity.
"""

import math
import random

import numpy as np

Point = tuple[float, float]


def convex_hull(points: np.ndarray) -> list[Point]:
    """Andrew's monotone chain; points as an (n, 2) array of x, y. Counter-clockwise."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _edge_points(mask: np.ndarray) -> np.ndarray:
    """Mask pixels on the object's border: all a hull needs, far fewer than the whole mask."""
    padded = np.pad(mask, 1)
    inner = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    ys, xs = np.nonzero(mask & ~inner)
    return np.column_stack([xs, ys]).astype(float)


def _area(a: Point, b: Point, c: Point) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2


def _inside(polygon: list[Point], points: np.ndarray, slack: float) -> bool:
    """All points inside the convex polygon (counter-clockwise), with `slack` pixels to spare."""
    xs, ys = points[:, 0], points[:, 1]
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        length = math.hypot(x2 - x1, y2 - y1) or 1
        # Signed distance to the edge's line; positive inside a counter-clockwise polygon.
        distance = ((x2 - x1) * (ys - y1) - (y2 - y1) * (xs - x1)) / length
        if (distance < slack).any():
            return False
    return True


def scissor_polygon(
    mask: np.ndarray,
    margin: float = 12,
    sides: tuple[int, int] = (6, 10),
    seed: int = 0,
) -> list[Point]:
    """A 6-10 sided cut around the True pixels of `mask`, `margin` pixels of paper away."""
    if not mask.any():
        raise ValueError("empty mask: nothing to cut out")
    rnd = random.Random(seed)
    edge = _edge_points(mask)
    hull = np.array(convex_hull(edge))
    # Grow the hull by the paper margin: the hull of the hull's points moved out in 16
    # directions is the hull with rounded corners, `margin` pixels larger.
    angles = np.linspace(0, 2 * math.pi, 16, endpoint=False)
    ring = np.column_stack([np.cos(angles), np.sin(angles)]) * margin
    grown = convex_hull((hull[:, None, :] + ring[None, :, :]).reshape(-1, 2))

    # Snip off the corners that matter least until few sides are left, never closer to the
    # object than half the margin.
    target = rnd.randint(*sides)
    polygon = list(grown)
    while len(polygon) > target:
        areas = [
            _area(polygon[i - 1], polygon[i], polygon[(i + 1) % len(polygon)])
            for i in range(len(polygon))
        ]
        for i in np.argsort(areas):
            candidate = polygon[:i] + polygon[i + 1 :]
            if _inside(candidate, hull, margin / 2):
                polygon = candidate
                break
        else:
            break  # every cut would reach the object: keep the extra sides

    # A hand is not a ruler: push each corner out a little, at random.
    cx, cy = np.mean(polygon, axis=0)
    jittered = []
    for x, y in polygon:
        push = rnd.uniform(0, margin * 0.35)
        d = math.hypot(x - cx, y - cy) or 1
        jittered.append((x + (x - cx) / d * push, y + (y - cy) / d * push))
    return jittered


def clip_path(polygon: list[Point], width: int, height: int) -> str:
    """The polygon as a CSS clip-path, in percent of the image size."""
    corners = ", ".join(f"{x / width * 100:.1f}% {y / height * 100:.1f}%" for x, y in polygon)
    return f"polygon({corners})"
