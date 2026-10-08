"""Frame analysis (stage 2c): the most expensive fallback, a multimodal model reads the images."""

import base64
import mimetypes
from pathlib import Path
from typing import Protocol

import anthropic

FRAME_PROMPT = (
    "These images come from a cooking video or are screenshots of a recipe post. "
    "Transcribe every visible ingredient with its quantity, and every recipe step, "
    "including any on-screen text. Also note the dish name and its cuisine if it is clear."
    " Answer with plain text only; do not invent what is not visible."
)


class FrameDescriber(Protocol):
    def describe(self, images: list[Path]) -> str: ...


def tail_weighted(count: int = 10, tail_share: float = 0.7) -> list[float]:
    """Positions (0..1) for `count` frames, most of them in the last third of the video:
    that is where a cooking reel shows the finished dish."""
    tail = round(count * tail_share)
    head = count - tail
    early = [(i + 0.5) / head * (2 / 3) for i in range(head)]
    late = [2 / 3 + (i + 0.5) / tail / 3 for i in range(tail)]
    return early + late


def extract_frames(
    video_path: Path, out_dir: Path, count: int = 6, positions: list[float] | None = None
) -> list[Path]:
    """Save frames of a video as JPEGs (needs the `media` extra): `count` evenly spaced, or
    one at each of `positions` (0..1 of the duration)."""
    try:
        import av
        import PIL  # noqa: F401  (PyAV needs Pillow to save frames as images)
    except ImportError as error:
        raise RuntimeError(
            f"{error.name} is not installed. Run `uv sync --extra media`."
        ) from error
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        spots = positions or [(i + 0.5) / count for i in range(count)]
        return _save_frames(av, video_path, out_dir, spots)
    except av.error.FFmpegError as error:  # unreadable or truncated video
        raise RuntimeError(f"could not read the video: {error}") from error


def _save_frames(av, video_path: Path, out_dir: Path, positions: list[float]) -> list[Path]:
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        duration = float(container.duration or 0) / av.time_base
        frames: list[Path] = []
        for index, position in enumerate(positions):
            container.seek(int(duration * position * av.time_base))
            for frame in container.decode(stream):
                path = out_dir / f"frame_{index}.jpg"
                frame.to_image().save(path, quality=85)
                frames.append(path)
                break
    return frames


class ClaudeFrameDescriber:
    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model

    def describe(self, images: list[Path]) -> str:
        content: list[dict] = [_image_block(path) for path in images]
        content.append({"type": "text", "text": FRAME_PROMPT})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()


def _image_block(path: Path) -> dict:
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
