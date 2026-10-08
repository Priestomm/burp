from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from burp.frames import tail_weighted
from burp.library import Library
from burp.models import ImportedRecipe
from burp.photo import ClaudeFramePicker, Pick, make_photo, stash_inputs, user_media
from burp.worker import PHOTO, run_once
from tests.test_structure import valid_recipe

DISH = Path(__file__).parent / "fixtures" / "images" / "piatto.jpg"


class FakePicker:
    def __init__(self, pick: Pick) -> None:
        self.choice, self.seen = pick, []

    def pick(self, images):
        self.seen.append(list(images))
        return self.choice


def good(best=1, confidence=0.9) -> Pick:
    return Pick(
        best=best,
        confidence=confidence,
        alt="Gnocchi glassati in una ciotola scura",
        reason="nitida",
    )


@pytest.fixture
def text_screenshot(tmp_path) -> Path:
    path = tmp_path / "caption.png"
    image = Image.new("RGB", (300, 500), "white")
    draw = ImageDraw.Draw(image)
    for y in range(40, 460, 24):
        draw.line((20, y, 280, y), fill="black", width=3)
    image.save(path)
    return path


def test_most_frames_come_from_the_last_third():
    positions = tail_weighted(10)
    assert len(positions) == 10
    assert positions == sorted(positions)
    assert sum(p >= 2 / 3 for p in positions) == 7
    assert all(0 < p < 1 for p in positions)


def test_the_chosen_picture_is_saved_with_its_halftone(tmp_path, text_screenshot):
    picker = FakePicker(good(best=2))
    url = "https://www.instagram.com/reel/abc/"
    media_dir = tmp_path / "media"
    outcome = make_photo(
        7, [text_screenshot, DISH], picker, media_dir, creator="giuliapisco", source_url=url
    )
    assert len(picker.seen[0]) == 2
    media = outcome.media
    assert media.source == "screenshot" and media.confidence == 0.9
    assert media.alt.startswith("Gnocchi") and media.creator == "giuliapisco"
    assert media.source_url == url
    with Image.open(media_dir / media.halftone) as printed:
        assert printed.width == 1200
    with Image.open(media_dir / media.original) as original:
        assert original.size == (640, 360)


def test_no_photo_when_the_model_is_not_sure(tmp_path):
    outcome = make_photo(7, [DISH], FakePicker(good(confidence=0.3)), tmp_path)
    assert outcome.media is None
    assert "confidenza 0.30" in outcome.note
    assert not (tmp_path / "7" / "halftone.png").exists()


def test_no_photo_when_nothing_shows_the_finished_dish(tmp_path, text_screenshot):
    outcome = make_photo(7, [text_screenshot], FakePicker(good(best=0)), tmp_path)
    assert outcome.media is None and "nessuna" in outcome.note


def test_no_photo_without_pictures(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    picker = FakePicker(good())
    assert make_photo(7, [notes], picker, tmp_path).media is None
    assert picker.seen == []  # the model is not even asked


def test_frames_are_taken_from_a_video(tmp_path):
    av = pytest.importorskip("av")
    import numpy as np

    video = tmp_path / "clip.mp4"
    with av.open(str(video), "w") as out:
        stream = out.add_stream("mpeg4", rate=10)
        stream.width = stream.height = 64
        for i in range(60):
            frame = np.full((64, 64, 3), i * 4, np.uint8)
            for packet in stream.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    picker = FakePicker(good(best=10))
    outcome = make_photo(3, [video], picker, tmp_path / "media")
    assert len(picker.seen[0]) == 10
    assert outcome.media.source == "frame"


def test_user_media_and_stash(tmp_path):
    files = [DISH, tmp_path / "clip.MOV", tmp_path / "notes.txt"]
    assert user_media(files) == files[:2]
    stored = stash_inputs(4, [DISH], tmp_path)
    assert len(stored) == 1 and stored[0].startswith("4/inputs/") and stored[0].endswith("/0.jpg")
    assert (tmp_path / stored[0]).read_bytes() == DISH.read_bytes()
    # One folder per job: a second job does not overwrite the first one's files.
    assert stash_inputs(4, [DISH], tmp_path)[0] != stored[0]


def test_claude_picker_sends_numbered_small_images(tmp_path):
    big = tmp_path / "big.png"
    Image.new("RGB", (3000, 2000), "orange").save(big)
    calls = []

    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(parsed_output=good(), stop_reason="end_turn")

    client = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    assert ClaudeFramePicker(client, "claude-haiku-4-5").pick([big, DISH]).best == 1
    content = calls[0]["messages"][0]["content"]
    assert [b["text"] for b in content if b["type"] == "text"][:2] == ["Immagine 1:", "Immagine 2:"]
    assert sum(b["type"] == "image" for b in content) == 2
    assert calls[0]["output_format"] is Pick and calls[0]["model"] == "claude-haiku-4-5"


@pytest.fixture
def saved(library):
    recipe = valid_recipe(author_handle="giuliapisco", source_url="https://www.instagram.com/p/x/")
    saved, _ = library.add(ImportedRecipe(recipe=recipe, content_source="caption"))
    return saved


def test_worker_makes_the_photo_in_the_background(library, saved, tmp_path):
    inputs = stash_inputs(saved.id, [DISH], tmp_path)
    job_id = library.enqueue(PHOTO, saved.id, inputs)
    assert library.jobs(saved.id)[0].status == "queued"

    assert run_once(library, FakePicker(good()), tmp_path) is True
    [job] = library.jobs(saved.id)
    assert (job.id, job.status) == (job_id, "done")
    media = library.media(saved.id)
    assert media.creator == "giuliapisco" and (tmp_path / media.halftone).exists()
    assert run_once(library, FakePicker(good()), tmp_path) is False  # queue empty


def test_a_failing_job_is_recorded_and_the_queue_goes_on(library, saved, tmp_path):
    class Broken:
        def pick(self, images):
            raise RuntimeError("API down")

    library.enqueue(PHOTO, saved.id, stash_inputs(saved.id, [DISH], tmp_path))
    library.enqueue(PHOTO, saved.id, stash_inputs(saved.id, [DISH], tmp_path))
    run_once(library, Broken(), tmp_path)
    run_once(library, FakePicker(good()), tmp_path)
    assert [(j.status, j.note) for j in library.jobs(saved.id)][0] == (
        "failed",
        "RuntimeError: API down",
    )
    assert library.jobs(saved.id)[1].status == "done"
    assert library.media(saved.id) is not None


def test_media_goes_with_the_recipe(library, saved, tmp_path):
    library.enqueue(PHOTO, saved.id, stash_inputs(saved.id, [DISH], tmp_path))
    run_once(library, FakePicker(good()), tmp_path)
    library.delete(saved.id)
    assert library.media(saved.id) is None and library.jobs(saved.id) == []


def test_new_libraries_get_the_media_tables(tmp_path, catalog):
    with Library(tmp_path / "x.db", catalog) as lib:
        assert lib.conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_inputs_are_deleted_after_the_job(library, saved, tmp_path):
    inputs = stash_inputs(saved.id, [DISH], tmp_path)
    library.enqueue(PHOTO, saved.id, inputs)
    run_once(library, FakePicker(good()), tmp_path)
    assert not (tmp_path / inputs[0]).exists()
    assert not (tmp_path / inputs[0]).parent.exists()
    assert (tmp_path / library.media(saved.id).halftone).exists()  # the photo stays


def test_inputs_are_deleted_even_when_the_job_fails(library, saved, tmp_path):
    class Broken:
        def pick(self, images):
            raise RuntimeError("API down")

    inputs = stash_inputs(saved.id, [DISH], tmp_path)
    library.enqueue(PHOTO, saved.id, inputs)
    run_once(library, Broken(), tmp_path)
    assert not (tmp_path / inputs[0]).exists()


def test_a_downloaded_reel_is_stashed_as_reel(tmp_path):
    clip = tmp_path / "post.mp4"
    clip.write_bytes(b"video")
    stored = stash_inputs(5, [DISH], tmp_path, reel=clip)
    assert [Path(p).name for p in stored] == ["0.jpg", "reel.mp4"]


def test_frames_of_the_reel_are_marked_as_reel(tmp_path):
    av = pytest.importorskip("av")
    import numpy as np

    video = tmp_path / "reel.mp4"
    with av.open(str(video), "w") as out:
        stream = out.add_stream("mpeg4", rate=10)
        stream.width = stream.height = 64
        for i in range(30):
            frame = np.full((64, 64, 3), i * 8, np.uint8)
            for packet in stream.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    outcome = make_photo(3, [video], FakePicker(good(best=4)), tmp_path / "media")
    assert outcome.media.source == "reel"
