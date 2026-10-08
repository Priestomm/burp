from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from burp.photocopy import DISH, INGREDIENT, INK, PAPER, Exposure, atkinson, photocopy, torn_edge

SAMPLE = Path(__file__).parent / "fixtures" / "images" / "piatto.jpg"


@pytest.fixture(scope="module")
def printed() -> np.ndarray:
    return np.asarray(photocopy(Image.open(SAMPLE), width=320))


def test_only_two_colours_where_there_is_paper(printed):
    opaque = printed[printed[..., 3] == 255][:, :3]
    colours = {tuple(c) for c in np.unique(opaque, axis=0)}
    assert colours == {INK, PAPER}


def test_dark_areas_get_more_toner_than_light_ones(printed):
    ink = (printed[..., :3] == INK).all(axis=-1)
    bowl = ink[70:110, 85:95].mean()  # dark bowl rim of the sample
    table = ink[40:60, 260:300].mean()  # pale table, right side
    assert bowl > 0.8
    assert table < 0.25


def test_the_lid_shadow_darkens_the_left_and_top_edges(printed):
    ink = (printed[..., :3] == INK).all(axis=-1)
    left_edge = ink[40:120, 0:8].mean()
    same_table_inside = ink[40:120, 40:48].mean()
    assert left_edge > same_table_inside + 0.2


def test_the_bottom_edge_is_torn_and_transparent(printed):
    alpha = printed[..., 3]
    assert alpha[0].min() == 255  # straight top
    assert alpha[-1].max() == 0  # nothing left at the very bottom
    # The tear is ragged: where the paper ends changes along the edge.
    last_paper_row = [int(np.nonzero(alpha[:, x])[0].max()) for x in range(0, 320, 20)]
    assert len(set(last_paper_row)) > 3


def test_same_seed_same_print():
    a = np.asarray(photocopy(Image.open(SAMPLE), width=120, seed=7))
    b = np.asarray(photocopy(Image.open(SAMPLE), width=120, seed=7))
    assert (a == b).all()


def test_ingredient_exposure_keeps_pale_objects_visible():
    lum = np.full((60, 60), 200 / 255)  # tofu, flour in the shade: light but not white
    default = atkinson(lum, Exposure()).mean()
    ingredient = atkinson(lum, INGREDIENT).mean()
    assert default < 0.15  # with the default exposure it nearly vanishes
    assert ingredient > default + 0.2


def test_exposures_from_the_spec():
    assert (DISH.contrast, DISH.bright) == (1.4, 0.05)
    assert (INGREDIENT.gamma, INGREDIENT.contrast, INGREDIENT.bright) == (1.7, 1.2, -0.05)


def test_torn_edge_spans_the_width():
    points = torn_edge(200, 100, seed=3, depth=10)
    assert points[0] == (0.0, 0.0) and points[1] == (200.0, 0.0)
    assert all(80 <= y <= 99 for _, y in points[2:])


def test_transparent_input_stays_transparent():
    cutout = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    cutout.paste((120, 60, 40, 255), (10, 10, 30, 30))
    out = np.asarray(photocopy(cutout, width=40, copier_marks=False, torn=False))
    assert out[0, 0, 3] == 0 and out[20, 20, 3] == 255
