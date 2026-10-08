"""Photocopy print for the Zine theme: 1-bit Atkinson dithering, black toner on paper.

A port of the mockup's `atkinson`, `photocopy` and `tornEdge`. One output pixel is one dot of
toner, so the print is made at about the size it is shown (one CSS pixel per dot). For the
dish: higher contrast, toner specks, the dark shadow the copier lid leaves on the left and top
edges, and a torn bottom edge (transparent below the tear).
"""

import random
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

INK = (0x16, 0x13, 0x11)
PAPER = (0xFB, 0xFA, 0xF5)


@dataclass(frozen=True)
class Exposure:
    gamma: float = 1.0
    contrast: float = 1.3
    bright: float = 0.04


DISH = Exposure(gamma=1.0, contrast=1.4, bright=0.05)
# Ingredients are often pale (flour, tofu): a darker exposure keeps them from vanishing.
INGREDIENT = Exposure(gamma=1.7, contrast=1.2, bright=-0.05)


def luminance(image: Image.Image) -> np.ndarray:
    """0..1 luminance; transparent pixels count as white paper."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255
    lum = 0.299 * rgba[..., 0] + 0.587 * rgba[..., 1] + 0.114 * rgba[..., 2]
    return np.where(rgba[..., 3] < 0.04, 1.0, lum)


def atkinson(lum: np.ndarray, exposure: Exposure) -> np.ndarray:
    """True where toner lands. Atkinson spreads 6/8 of the error and drops the rest, which
    keeps the hard, contrasty look of a copier instead of a smooth grey."""
    level = np.power(np.clip(lum, 0, 1), exposure.gamma)
    level = (level - 0.5) * exposure.contrast + 0.5 + exposure.bright
    height, width = level.shape
    grey = (level * 255).astype(np.float64).tolist()  # plain lists: much faster to index
    ink = np.zeros((height, width), dtype=bool)
    for y in range(height):
        row, below = grey[y], grey[y + 1] if y + 1 < height else None
        below2 = grey[y + 2] if y + 2 < height else None
        for x in range(width):
            old = row[x]
            black = old < 128
            err = (old - (0 if black else 255)) / 8
            if black:
                ink[y, x] = True
            if x + 1 < width:
                row[x + 1] += err
            if x + 2 < width:
                row[x + 2] += err
            if below is not None:
                if x > 0:
                    below[x - 1] += err
                below[x] += err
                if x + 1 < width:
                    below[x + 1] += err
            if below2 is not None:
                below2[x] += err
    return ink


def torn_edge(width: int, height: int, seed: int, depth: float) -> list[tuple[float, float]]:
    """Outline of a sheet whose bottom edge was torn: straight top and sides, ragged bottom."""
    rnd = random.Random(seed)
    points = [(0.0, 0.0), (float(width), 0.0)]
    x = float(width)
    while x > 0:
        wobble = (rnd.random() - 0.5) * depth * 0.9 + np.sin(x / 37) * depth * 0.25
        points.append((x, min(height - 1.0, height - depth + wobble)))
        x -= 5 + rnd.random() * 15
    points.append((0.0, height - depth * 0.55))
    return points


def _copier_marks(lum: np.ndarray, seed: int) -> np.ndarray:
    """Toner specks and the lid shadow, added to the original before it is printed."""
    height, width = lum.shape
    lum = lum.copy()
    rnd = random.Random(seed)
    for _ in range(int(320 * width * height / (1000 * 620))):
        x, y = rnd.randrange(width), rnd.randrange(height)
        size = max(1, round(0.7 + rnd.random() * 2))
        lum[y : y + size, x : x + size] *= 1 - (0.45 + rnd.random() * 0.55)
    left = np.clip(1 - np.arange(width) / (width * 0.07), 0, 1) * 0.5
    top = np.clip(1 - np.arange(height) / (height * 0.07), 0, 1) * 0.35
    lum *= 1 - left[None, :]
    lum *= 1 - top[:, None]
    return lum


def photocopy(
    image: Image.Image,
    width: int,
    exposure: Exposure = DISH,
    seed: int = 4,
    copier_marks: bool = True,
    torn: bool = True,
) -> Image.Image:
    """Print `image` at `width` pixels; returns RGBA (transparent below a torn edge)."""
    source = image.convert("RGBA")
    height = max(1, round(source.height * width / source.width))
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    alpha = np.asarray(source)[..., 3]
    lum = luminance(source)
    if copier_marks:
        lum = _copier_marks(lum, seed)
    ink = atkinson(lum, exposure)

    out = np.empty((height, width, 4), dtype=np.uint8)
    out[..., :3] = PAPER
    out[ink, :3] = INK
    out[..., 3] = np.where(alpha > 10, 255, 0)
    printed = Image.fromarray(out, "RGBA")
    if torn:
        mask = Image.new("L", (width, height), 0)
        depth = max(8, height * 26 / 620)
        ImageDraw.Draw(mask).polygon(torn_edge(width, height, seed, depth), fill=255)
        printed.putalpha(Image.fromarray(np.minimum(np.asarray(mask), out[..., 3])))
    return printed
