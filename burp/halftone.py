"""Two-ink halftone print of a dish photo: red at 15°, black at 45°, on warm paper.

A port of the mockup's canvas `halftone()`: one rotated dot screen per ink, each dot sized by
how much of that ink the photo needs at that point, the inks multiplied over the paper like
real overprinting. Black follows the dark areas; red follows the warm ones, where red is
stronger than the average of green and blue. Any frame, even a blurry one from a reel, comes
out with the same printed character.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

PAPER = "#F7F2E8"
RED = "#E5432C"
BLACK = "#1B1714"

Coverage = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def _lum(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _warm(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (r - (g + b) / 2) / 255


def red_coverage(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (_warm(r, g, b) - 0.12) * 1.7 + (1 - _lum(r, g, b)) * 0.06


def black_coverage(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    # The mockup took 0.45 of the warmth away; on a real red sauce that left it nearly black,
    # so warm tones now give up twice as much black to the red ink.
    dark = (1 - _lum(r, g, b)) ** 1.35 * 1.5
    return dark - np.maximum(0, _warm(r, g, b)) * 0.9 - 0.05


@dataclass(frozen=True)
class Ink:
    color: str
    angle: float  # screen angle, degrees
    coverage: Coverage  # 0..1 of this ink for an RGB colour (arrays of 0..255)


INKS = (Ink(RED, 15, red_coverage), Ink(BLACK, 45, black_coverage))


def halftone(
    image: Image.Image,
    width: int = 1200,
    cell: float = 5.0,
    inks: tuple[Ink, ...] = INKS,
    paper: str = PAPER,
    supersample: int = 3,
) -> Image.Image:
    """Print `image` at `width` pixels with dot cells of `cell` pixels."""
    source = image.convert("RGB")
    height = max(1, round(source.height * width / source.width))
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    # Each dot stands for the colour around it, not for one noisy pixel.
    colours = np.asarray(source.filter(ImageFilter.BoxBlur(cell / 2)), dtype=np.float32)

    size = (width * supersample, height * supersample)
    printed = Image.new("RGB", size, paper)
    for ink in inks:
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        for x, y, radius in _dots(colours, ink, cell):
            box = [(x - radius) * supersample, (y - radius) * supersample]
            box += [(x + radius) * supersample, (y + radius) * supersample]
            draw.ellipse(box, fill=255)
        plate = Image.composite(
            Image.new("RGB", size, ink.color), Image.new("RGB", size, "white"), mask
        )
        printed = ImageChops.multiply(printed, plate)  # overprint, as on paper
    return printed.resize((width, height), Image.Resampling.LANCZOS)


def _dots(colours: np.ndarray, ink: Ink, cell: float) -> list[tuple[float, float, float]]:
    """Centre and radius of every dot of one ink's rotated screen."""
    height, width = colours.shape[:2]
    angle = math.radians(ink.angle)
    cos, sin = math.cos(angle), math.sin(angle)
    n = math.ceil(math.hypot(width, height) / cell / 2) + 2
    i, j = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    u, v = i.ravel() * cell, j.ravel() * cell
    x = width / 2 + u * cos - v * sin
    y = height / 2 + u * sin + v * cos
    inside = (x > -cell) & (y > -cell) & (x < width + cell) & (y < height + cell)
    x, y = x[inside], y[inside]
    sx = np.clip(np.round(x).astype(int), 0, width - 1)
    sy = np.clip(np.round(y).astype(int), 0, height - 1)
    r, g, b = (colours[sy, sx, k] for k in range(3))
    coverage = np.clip(ink.coverage(r, g, b), 0, 1)
    visible = coverage > 0.03
    radius = cell * 0.71 * np.sqrt(coverage[visible])
    return list(zip(x[visible], y[visible], radius, strict=True))
