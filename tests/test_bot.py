import json
from pathlib import Path

import httpx

from burp.bot import TelegramApi, handle_update, parse_update
from burp.catalog import SynonymIndex, load_ingredients
from burp.ingest import IngestionError
from burp.pipeline import import_post
from tests.test_structure import FakeClient, valid_recipe

CAPTIONS = Path(__file__).parent / "fixtures" / "captions"
ALLOWED = frozenset({42})


def make_api(sent: list[dict], files: dict[str, bytes] | None = None) -> TelegramApi:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sendMessage"):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True, "result": {}})
        if request.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "photos/a.jpg"}})
        if "/file/bot" in request.url.path:
            return httpx.Response(200, content=(files or {}).get("a", b"jpeg-bytes"))
        raise AssertionError(request.url)

    return TelegramApi("TOKEN", httpx.Client(transport=httpx.MockTransport(handler)))


def message(text="", user_id=42, photo=None) -> dict:
    body = {"chat": {"id": 7}, "from": {"id": user_id}}
    if text:
        body["text" if not photo else "caption"] = text
    if photo:
        body["photo"] = [{"file_id": "small"}, {"file_id": photo}]
    return {"update_id": 1, "message": body}


def importer(client=None):
    client = client or FakeClient(valid_recipe())
    catalog = SynonymIndex(load_ingredients())
    return lambda post: import_post(post, catalog, client, "m")


def test_parse_update_takes_the_largest_photo():
    incoming = parse_update(message("hi", photo="large"))
    assert incoming.photo_file_id == "large" and incoming.text == "hi"


def test_parse_update_ignores_non_messages():
    assert parse_update({"update_id": 1, "edited_message": {}}) is None


def test_pasted_caption_is_imported_and_saved(library):
    sent: list[dict] = []
    text = (CAPTIONS / "completa.txt").read_text()
    handle_update(message(text), make_api(sent), ALLOWED, importer(), library)
    [saved] = library.search()
    assert saved.recipe.title == "Dal tadka"
    assert sent[0]["chat_id"] == 7
    assert "Dal tadka" in sent[0]["text"] and "completa" in sent[0]["text"]
    assert f"Salvata come #{saved.id}" in sent[0]["text"]


def test_unauthorized_user_gets_no_answer_and_nothing_runs(library):
    sent: list[dict] = []

    def boom(post):
        raise AssertionError("must not run")

    handle_update(message("ciao", user_id=999), make_api(sent), ALLOWED, boom, library)
    assert sent == []


def test_empty_message_gets_help(library):
    sent: list[dict] = []
    update = message()
    update["message"]["sticker"] = {}
    handle_update(update, make_api(sent), ALLOWED, importer(), library)
    assert "Inoltrami" in sent[0]["text"]


def test_link_that_cannot_be_fetched_asks_for_the_manual_fallback(library, monkeypatch):
    sent: list[dict] = []

    def failing_fetch(url, cookies_file=None):
        raise IngestionError("login required; paste the caption or send a screenshot")

    monkeypatch.setattr("burp.bot.fetch_instagram", failing_fetch)
    link = "https://www.instagram.com/reel/abc/?igsh=xyz"
    handle_update(message(link), make_api(sent), ALLOWED, importer(), library)
    assert "screenshot" in sent[0]["text"]
    assert library.search() == []


def test_screenshot_is_downloaded_and_sent_to_frame_analysis(library):
    sent: list[dict] = []
    seen = {}

    class Describer:
        def describe(self, images):
            seen["images"] = images
            return "Dal tadka: 150 g di lenticchie rosse, 1 cipolla, 2 cucchiai di olio."

    catalog = SynonymIndex(load_ingredients())
    client = FakeClient(valid_recipe())

    def run_import(post):
        return import_post(post, catalog, client, "m", describer=Describer())

    handle_update(message(photo="large"), make_api(sent), ALLOWED, run_import, library)
    assert seen["images"][0].read_bytes() == b"jpeg-bytes"
    assert library.search()[0].imported.content_source == "frames"
    assert "fonte: frames" in sent[0]["text"]


def test_missing_media_extra_is_reported_to_the_user(library):
    sent: list[dict] = []

    def no_extra(post):
        raise RuntimeError("faster-whisper is not installed. Run `uv sync --extra media`.")

    handle_update(message("ciao"), make_api(sent), ALLOWED, no_extra, library)
    assert "uv sync --extra media" in sent[0]["text"]


def test_a_link_already_in_the_library_is_not_imported_again(library, monkeypatch):
    sent: list[dict] = []
    text = (CAPTIONS / "completa.txt").read_text() + "\nhttps://www.instagram.com/p/abc/"
    handle_update(message(text), make_api(sent), ALLOWED, importer(), library)

    def must_not_run(*args, **kwargs):
        raise AssertionError("must not download or import")

    monkeypatch.setattr("burp.bot.fetch_instagram", must_not_run)
    link = "https://www.instagram.com/reel/abc/?igsh=xyz"
    handle_update(message(link), make_api(sent), ALLOWED, must_not_run, library)
    assert "già nella tua libreria (#1)" in sent[1]["text"]
    assert len(library.search()) == 1
