"""The dish photo of a recipe, made in the background after the import.

By default only media the user hands over is used: screenshots, or a video they send (a
screen recording, a clip). The reel downloaded with the link is used too only when the user
turns on BURP_PHOTO_FROM_REEL, for personal use. Never an AI-generated image: with no good
picture, the recipe page shows paper and stickers only.

1. Collect candidates: the images, plus 10 frames of each video, most from its last third.
2. A small vision model picks the one where the finished dish is most visible and sharp,
   with a confidence; below MIN_CONFIDENCE nothing is used.
3. Save the original and its two-ink halftone print.
"""

import base64
import io
import logging
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anthropic
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from burp.frames import extract_frames, tail_weighted
from burp.halftone import halftone
from burp.library import Media

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.5
FRAMES_PER_VIDEO = 10
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}  # what Pillow opens without plugins


class Pick(BaseModel):
    model_config = ConfigDict(extra="forbid")

    best: int = Field(description="Numero dell'immagine scelta (da 1), 0 se nessuna va bene")
    confidence: float = Field(ge=0, le=1, description="Quanto sei sicuro che sia il piatto finito")
    alt: str = Field(description="Testo alternativo in italiano, max 120 caratteri")
    reason: str = Field(description="Perché questa, in breve")


class FramePicker(Protocol):
    def pick(self, images: list[Path]) -> Pick: ...


PICK_PROMPT = """\
Queste immagini vengono da un video di cucina o da screenshot di un post. Scegli quella in cui \
il piatto finito si vede meglio: intero, nitido, ben illuminato, senza mani o testo sopra. \
Scarta ingredienti crudi, passaggi a metà, schermate di solo testo e volti. Se nessuna mostra \
il piatto finito, rispondi best = 0. confidence: quanto sei sicuro che la scelta mostri davvero \
il piatto finito (0-1). alt: descrivi in italiano cosa si vede nell'immagine scelta, in una \
frase, per chi non vede la foto."""


class ClaudeFramePicker:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def pick(self, images: list[Path]) -> Pick:
        content: list[dict] = []
        for number, path in enumerate(images, start=1):
            content.append({"type": "text", "text": f"Immagine {number}:"})
            content.append(_small_jpeg_block(path))
        content.append({"type": "text", "text": PICK_PROMPT})
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": content}],
            output_format=Pick,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"no frame choice ({response.stop_reason})")
        return response.parsed_output


def _small_jpeg_block(path: Path, longest: int = 768) -> dict:
    """Downscaled: enough to judge the dish, at a fraction of the image tokens."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((longest, longest))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=85)
    data = base64.standard_b64encode(buffer.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


REEL = "reel"  # file name of a video downloaded from the post's link


def stash_inputs(
    recipe_id: int, paths: list[Path], media_dir: Path, reel: Path | None = None
) -> list[str]:
    """Copy the job's inputs next to the recipe's media (temporary files from the bot would be
    gone by then), one folder per job. A video downloaded from the link is named `reel`, so
    the photo can say where it comes from. Returns paths relative to `media_dir`."""
    folder = media_dir / str(recipe_id) / "inputs" / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=True)
    named = [(path, str(index)) for index, path in enumerate(paths)]
    if reel is not None:
        named.append((reel, REEL))
    stored = []
    for path, name in named:
        target = folder / f"{name}{path.suffix.lower()}"
        shutil.copyfile(path, target)
        stored.append(str(target.relative_to(media_dir)))
    return stored


def user_media(paths: list[Path]) -> list[Path]:
    """The files that can become the dish photo: images and videos."""
    return [p for p in paths if p.suffix.lower() in IMAGE_SUFFIXES | VIDEO_SUFFIXES]


@dataclass
class PhotoOutcome:
    media: Media | None
    note: str  # why there is no photo, or which candidate was chosen


def make_photo(
    recipe_id: int,
    inputs: list[Path],
    picker: FramePicker,
    media_dir: Path,
    creator: str | None = None,
    source_url: str | None = None,
) -> PhotoOutcome:
    candidates: list[tuple[Path, str]] = []
    with tempfile.TemporaryDirectory(prefix="burp-photo-") as tmp:
        for index, path in enumerate(inputs):
            if path.suffix.lower() in VIDEO_SUFFIXES:
                try:
                    frames = extract_frames(
                        path, Path(tmp) / str(index), positions=tail_weighted(FRAMES_PER_VIDEO)
                    )
                except RuntimeError as error:  # unreadable video, or no PyAV
                    log.warning("photo: skipping video %s: %s", path.name, error)
                    continue
                source = REEL if path.stem == REEL else "frame"
                candidates += [(frame, source) for frame in frames]
            elif path.suffix.lower() in IMAGE_SUFFIXES:
                candidates.append((path, "screenshot"))
        if not candidates:
            return PhotoOutcome(None, "nessuna immagine o video utilizzabile")

        choice = picker.pick([path for path, _ in candidates])
        if not 1 <= choice.best <= len(candidates):
            return PhotoOutcome(None, f"nessuna immagine mostra il piatto finito ({choice.reason})")
        if choice.confidence < MIN_CONFIDENCE:
            return PhotoOutcome(
                None, f"confidenza {choice.confidence:.2f} sotto {MIN_CONFIDENCE} ({choice.reason})"
            )

        chosen, source = candidates[choice.best - 1]
        folder = media_dir / str(recipe_id)
        folder.mkdir(parents=True, exist_ok=True)
        with Image.open(chosen) as image:
            original = image.convert("RGB")
        original.save(folder / "original.jpg", quality=90)
        halftone(original).save(folder / "halftone.png", optimize=True)

    count = len(candidates)
    log.info("photo: recipe %s, %s %d of %d", recipe_id, source, choice.best, count)
    media = Media(
        original=f"{recipe_id}/original.jpg",
        halftone=f"{recipe_id}/halftone.png",
        source=source,
        confidence=choice.confidence,
        alt=choice.alt[:200],
        creator=creator,
        source_url=source_url,
    )
    return PhotoOutcome(media, f"{source} {choice.best} di {count}: {choice.reason}")
