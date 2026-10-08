import numpy as np
import pytest
from PIL import Image, ImageDraw

from burp.cutout import make_cutout
from burp.scissors import clip_path, convex_hull, scissor_polygon


def ellipse_mask(w=200, h=140, box=(50, 30, 160, 110)) -> np.ndarray:
    image = Image.new("L", (w, h), 0)
    ImageDraw.Draw(image).ellipse(box, fill=255)
    return np.asarray(image) > 128


def distance_inside(polygon, points) -> np.ndarray:
    """Smallest signed distance of each point to the polygon's edges (inside > 0)."""
    xs, ys = points[:, 0], points[:, 1]
    out = np.full(len(points), np.inf)
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        length = np.hypot(x2 - x1, y2 - y1)
        out = np.minimum(out, ((x2 - x1) * (ys - y1) - (y2 - y1) * (xs - x1)) / length)
    return out


def test_convex_hull_of_a_square_with_inner_points():
    points = np.array([[0, 0], [4, 0], [4, 4], [0, 4], [2, 2], [1, 3]])
    assert sorted(convex_hull(points)) == [(0, 0), (0, 4), (4, 0), (4, 4)]


@pytest.mark.parametrize("seed", range(8))
def test_the_cut_has_6_to_10_sides_and_never_touches_the_object(seed):
    mask = ellipse_mask()
    polygon = scissor_polygon(mask, margin=12, seed=seed)
    assert 6 <= len(polygon) <= 10
    ys, xs = np.nonzero(mask)
    margins = distance_inside(polygon, np.column_stack([xs, ys]).astype(float))
    assert margins.min() >= 6  # at least half the margin of paper, everywhere
    assert margins.min() <= 30  # and not a huge sheet either


def test_irregular_objects_too():
    image = Image.new("L", (220, 220), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 100, 180, 130), fill=255)  # a spring onion lying down...
    draw.ellipse((150, 60, 200, 110), fill=255)  # ...with its bulb
    mask = np.asarray(image) > 128
    polygon = scissor_polygon(mask, margin=10, seed=3)
    ys, xs = np.nonzero(mask)
    assert distance_inside(polygon, np.column_stack([xs, ys]).astype(float)).min() >= 5


def test_same_seed_same_cut_different_seed_different_cut():
    mask = ellipse_mask()
    assert scissor_polygon(mask, seed=1) == scissor_polygon(mask, seed=1)
    assert scissor_polygon(mask, seed=1) != scissor_polygon(mask, seed=2)


def test_empty_mask_is_refused():
    with pytest.raises(ValueError, match="empty"):
        scissor_polygon(np.zeros((10, 10), dtype=bool))


def test_clip_path_in_percent():
    assert (
        clip_path([(0, 0), (100, 0), (50, 50)], 100, 50)
        == "polygon(0.0% 0.0%, 100.0% 0.0%, 50.0% 100.0%)"
    )


class ColourRemover:
    """Stands in for rembg: keeps what is darker than the pale table."""

    def remove(self, image):
        rgb = np.asarray(image.convert("RGB")).astype(int)
        alpha = np.where(rgb.sum(axis=-1) < 500, 255, 0).astype(np.uint8)
        return Image.fromarray(np.dstack([rgb.astype(np.uint8), alpha]), "RGBA")


def test_cutout_is_a_photocopy_cut_with_scissors():
    from pathlib import Path

    from burp.photocopy import INK, PAPER

    sample = Image.open(Path(__file__).parent / "fixtures" / "images" / "piatto.jpg")
    out = np.asarray(make_cutout(sample, ColourRemover(), width=300, seed=2))
    alpha = out[..., 3]
    assert alpha[0, 0] == 0 and alpha[-1, -1] == 0  # outside the cut
    opaque = {tuple(c) for c in np.unique(out[alpha == 255][:, :3], axis=0)}
    assert opaque <= {INK, PAPER}  # photocopied: toner on paper only
    assert (out[alpha == 255][:, :3] == INK).all(axis=-1).mean() > 0.3  # the dark bowl


def test_a_picture_with_no_object_is_refused():
    class Nothing:
        def remove(self, image):
            return image.convert("RGBA").point(lambda _: 0)

    with pytest.raises(ValueError, match="no object"):
        make_cutout(Image.new("RGB", (100, 100), "white"), Nothing())
