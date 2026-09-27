"""Audio transcription of a reel (stage 2b). Local faster-whisper, from the `media` extra."""

from pathlib import Path
from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, media_path: Path) -> str: ...


class FasterWhisperTranscriber:
    """Runs a Whisper model locally: no extra API key. The model downloads on first use."""

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model = None

    def transcribe(self, media_path: Path) -> str:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise RuntimeError(
                    "faster-whisper is not installed. Run `uv sync --extra media`."
                ) from error
            self._model = WhisperModel(self.model_size, compute_type="int8")
        segments, _ = self._model.transcribe(str(media_path), vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
