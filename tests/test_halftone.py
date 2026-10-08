from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from burp.halftone import BLACK, INKS, PAPER, RED, black_coverage, halftone, red_coverage

SAMPLE = Path(__file__).parent / "fixtures" / "images" / "piatto.jpg"


def hex_rgb(colour: str) -> np.ndarray:
    return np.array([int(colour[i : i + 2], 16) for i in (1, 3, 5)], dtype=float)


@pytest.fixture(scope="module")
def printed() -> np.ndarray:
    return np.asarray(halftone(Image.open(SAMPLE), width=640), dtype=float)


def share_near(region: np.ndarray, colour: str, tolerance: float = 60) -> float:
    """How much of a region is (close to) one colour."""
    distance = np.linalg.norm(region - hex_rgb(colour), axis=-1)
    return float((distance < tolerance).mean())


def test_keeps_the_aspect_ratio_and_the_requested_width():
    out = halftone(Image.open(SAMPLE), width=320)
    assert out.size == (320, 180)
    assert out.mode == "RGB"


def test_the_two_inks_are_red_at_15_and_black_at_45_degrees():
    assert [(ink.color, ink.angle) for ink in INKS] == [(RED, 15), (BLACK, 45)]


def test_light_areas_stay_paper(printed):
    table = printed[5:30, 5:120]  # top left corner of the sample: the pale table
    assert share_near(table, PAPER, 25) > 0.9


def test_black_follows_the_dark_areas(printed):
    bowl_rim = printed[160:200, 160:185]  # dark bowl, left of the sauce
    table = printed[5:30, 5:120]
    assert share_near(bowl_rim, BLACK, 70) > 0.4
    assert share_near(table, BLACK, 70) < 0.02


def red_share(region: np.ndarray) -> float:
    """Share of clearly red pixels. Inks overprint, so the exact ink colour rarely shows."""
    r, g, b = region[..., 0], region[..., 1], region[..., 2]
    return float(((r > 150) & (r - np.maximum(g, b) > 80)).mean())


def test_red_follows_the_warm_areas(printed):
    sauce = printed[255:285, 300:330]  # red sauce below the dumplings
    bowl_rim = printed[160:200, 160:185]
    table = printed[5:30, 5:120]
    assert red_share(sauce) > 0.3
    assert red_share(bowl_rim) < 0.02 and red_share(table) < 0.02


def test_a_warm_mid_tone_stays_mostly_red_not_black(printed):
    sauce = printed[255:285, 300:330]
    assert share_near(sauce, BLACK, 70) < 0.5


def test_coverage_functions():
    white, dark, warm = (np.array([v], dtype=float) for v in (255, 30, 0))
    # Dark grey: black ink, no red.
    assert black_coverage(dark, dark, dark)[0] > 0.9
    assert red_coverage(dark, dark, dark)[0] < 0.1
    # Warm red: red ink, little black.
    r, g, b = np.array([210.0]), np.array([60.0]), np.array([40.0])
    assert red_coverage(r, g, b)[0] > 0.8
    assert black_coverage(r, g, b)[0] < red_coverage(r, g, b)[0]
    # White: nothing.
    assert black_coverage(white, white, white)[0] < 0
    assert red_coverage(white, white, white)[0] < 0
    assert warm.size == 1
