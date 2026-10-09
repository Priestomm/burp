"""Cut-outs for the Zine theme: the object without its background, on paper, photocopied and
cut with scissors (see scissors.py). Used for the dish lifting off the torn sheet and for the
ingredients.

Background removal runs locally with rembg (optional `cutout` extra), so no image leaves the
computer for it.
"""

import os
from typing import Protocol

import numpy as np
from PIL import Image, ImageDraw

from burp.photocopy import INGREDIENT, PAPER, Exposure, colour_print, photocopy
from burp.scissors import scissor_polygon


class BackgroundRemover(Protocol):
    def remove(self, image: Image.Image) -> Image.Image:
        """The same image as RGBA, transparent where the background was."""
        ...


class RembgRemover:
    """rembg with a small model; it downloads on first use (BURP_CUTOUT_MODEL to change)."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("BURP_CUTOUT_MODEL") or "silueta"
        self._session = None

    def remove(self, image: Image.Image) -> Image.Image:
        try:
            import rembg
        except ImportError as error:
            raise RuntimeError("rembg is not installed. Run `uv sync --extra cutout`.") from error
        if self._session is None:
            self._session = rembg.new_session(self.model)
        return rembg.remove(image.convert("RGB"), session=self._session)


def make_cutout(
    image: Image.Image,
    remover: BackgroundRemover,
    width: int = 420,
    exposure: Exposure = INGREDIENT,
    margin: float = 12,
    seed: int = 0,
    colour: bool = False,
) -> Image.Image:
    """The object of `image`, photocopied on paper (or printed in colour) and cut out. RGBA,
    transparent outside."""
    source = image.convert("RGB")
    source.thumbnail((width, width * 2))
    removed = remover.remove(source).convert("RGBA")
    alpha = np.asarray(removed)[..., 3]
    if (alpha > 128).sum() < 0.01 * alpha.size:
        raise ValueError("no object found in the picture")

    # Room for the paper margin around the object.
    pad = int(margin * 2)
    w, h = removed.size
    sheet = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), PAPER + (255,))
    sheet.alpha_composite(removed, (pad, pad))  # the object on paper, its background gone
    mask = np.zeros((h + 2 * pad, w + 2 * pad), dtype=bool)
    mask[pad : pad + h, pad : pad + w] = alpha > 128

    if colour:
        printed = colour_print(sheet, width=sheet.width, seed=seed, torn=False)
    else:
        printed = photocopy(
            sheet, width=sheet.width, exposure=exposure, copier_marks=False, torn=False
        )
    polygon = scissor_polygon(mask, margin=margin, seed=seed)
    cut = Image.new("L", printed.size, 0)
    ImageDraw.Draw(cut).polygon(polygon, fill=255)
    printed.putalpha(cut)
    return printed.crop(cut.getbbox())
