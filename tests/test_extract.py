import logging
from pathlib import Path

import pytest

from burp import extract
from burp.extract import (
    InsufficientContentError,
    extract_content,
    is_sufficient,
)
from burp.ingest import SourcePost

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"
FULL_RECIPE = "Ingredienti: " + " ".join(f"{n} g di farina bianca" for n in range(10, 20))


def caption(name: str) -> str:
    return (CAPTIONS / f"{name}.txt").read_text()


class FakeTranscriber:
    def __init__(self, text: str) -> None:
        self.text, self.calls = text, 0

    def transcribe(self, media_path):
        self.calls += 1
        return self.text


class FakeDescriber:
    def __init__(self) -> None:
        self.calls: list[list[Path]] = []

    def describe(self, images):
        self.calls.append(images)
        return "Pasta e ceci: 200 g di ceci, 80 g di pasta."


@pytest.mark.parametrize("name", ["completa", "quantita_mancanti", "inglese"])
def test_realistic_captions_are_sufficient(name):
    assert is_sufficient(caption(name)) == (True, "")


def test_emoji_only_caption_is_rejected_with_a_reason():
    ok, reason = is_sufficient(caption("vuota"))
    assert not ok
    assert "words" in reason


def test_long_text_without_quantities_is_rejected():
    ok, reason = is_sufficient("Che bella giornata per cucinare qualcosa " * 10)
    assert not ok
    assert "quantities" in reason


def test_sufficient_caption_never_pays_for_transcription(caplog):
    transcriber, describer = FakeTranscriber("x"), FakeDescriber()
    post = SourcePost(caption=caption("completa"), video_path=Path("v.mp4"))
    with caplog.at_level(logging.INFO):
        result = extract_content(post, transcriber, describer)
    assert (result.source, result.reason) == ("caption", "")
    assert transcriber.calls == 0 and describer.calls == []
    assert "content source: caption" in caplog.text


def test_insufficient_caption_falls_back_to_transcript():
    post = SourcePost(caption=caption("vuota"), video_path=Path("v.mp4"))
    describer = FakeDescriber()
    result = extract_content(post, FakeTranscriber(FULL_RECIPE), describer)
    assert result.source == "transcript"
    assert "caption:" in result.reason
    assert describer.calls == []


def test_insufficient_transcript_falls_back_to_frames(monkeypatch, tmp_path):
    frame = tmp_path / "frame_0.jpg"
    monkeypatch.setattr(extract, "extract_frames", lambda video, out, count: [frame])
    post = SourcePost(caption=caption("vuota"), video_path=Path("v.mp4"))
    describer = FakeDescriber()
    result = extract_content(post, FakeTranscriber("musica"), describer)
    assert result.source == "frames"
    assert describer.calls == [[frame]]
    assert "caption:" in result.reason and "transcript:" in result.reason
    assert "200 g di ceci" in result.text


def test_screenshot_only_post_goes_straight_to_frames(tmp_path):
    shot = tmp_path / "s.png"
    describer = FakeDescriber()
    post = SourcePost(screenshot_paths=[shot])
    result = extract_content(post, FakeTranscriber("unused"), describer)
    assert result.source == "frames"
    assert describer.calls == [[shot]]


def test_nothing_usable_asks_the_user_for_the_manual_fallback():
    with pytest.raises(InsufficientContentError, match="Paste the full caption"):
        extract_content(SourcePost(caption=caption("vuota")))


def test_empty_caption_falls_back_and_logs_source_and_reason(caplog):
    post = SourcePost(caption="", video_path=Path("v.mp4"))
    with caplog.at_level(logging.INFO):
        result = extract_content(post, FakeTranscriber(FULL_RECIPE), FakeDescriber())
    assert result.source == "transcript"
    assert "caption: only 0 words" in result.reason
    assert "content source: transcript (caption: only 0 words" in caplog.text


def test_failing_transcription_moves_on_to_frames(monkeypatch, tmp_path):
    class BrokenTranscriber:
        def transcribe(self, media_path):
            raise RuntimeError("faster-whisper is not installed")

    frame = tmp_path / "frame_0.jpg"
    monkeypatch.setattr(extract, "extract_frames", lambda video, out, count: [frame])
    post = SourcePost(caption=caption("vuota"), video_path=Path("v.mp4"))
    result = extract_content(post, BrokenTranscriber(), FakeDescriber())
    assert result.source == "frames"
    assert "transcript: failed (faster-whisper is not installed)" in result.reason


def test_missing_frame_extractor_still_uses_the_screenshots(monkeypatch, tmp_path):
    def no_pyav(video, out, count):
        raise RuntimeError("PyAV is not installed")

    monkeypatch.setattr(extract, "extract_frames", no_pyav)
    shot = tmp_path / "s.png"
    post = SourcePost(video_path=Path("v.mp4"), screenshot_paths=[shot])
    describer = FakeDescriber()
    result = extract_content(post, FakeTranscriber("musica"), describer)
    assert describer.calls == [[shot]]
    assert "could not extract video frames" in result.reason
