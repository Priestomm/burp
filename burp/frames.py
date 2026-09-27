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


def extract_frames(video_path: Path, out_dir: Path, count: int = 6) -> list[Path]:
    """Save `count` evenly spaced frames of a video as JPEGs (needs the `media` extra)."""
    try:
        import av
    except ImportError as error:
        raise RuntimeError("PyAV is not installed. Run `uv sync --extra media`.") from error
    out_dir.mkdir(parents=True, exist_ok=True)
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        duration = float(container.duration or 0) / av.time_base
        frames: list[Path] = []
        for index in range(count):
            container.seek(int(duration * (index + 0.5) / count * av.time_base))
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
