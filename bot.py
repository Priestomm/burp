"""Telegram bot: forward it an Instagram link (or paste a caption, or send a screenshot).

    uv run python bot.py

Long polling over the Bot API with httpx. Only the user ids in TELEGRAM_ALLOWED_USER_IDS are
served, and only what they send explicitly is processed.
"""

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import anthropic
import httpx

from burp.config import Settings, load_env
from burp.extract import InsufficientContentError, is_sufficient
from burp.frames import ClaudeFrameDescriber
from burp.ingest import (
    IngestionError,
    SourcePost,
    fetch_instagram,
    find_instagram_url,
    from_caption,
    from_screenshots,
)
from burp.loader import load_ingredients
from burp.pipeline import import_post, summarize
from burp.store import IMPORTED_DIR, ImportedRecipe, save
from burp.structure import StructuringError
from burp.transcribe import FasterWhisperTranscriber

log = logging.getLogger("bot")

HELP = (
    "Inoltrami il link di un post o reel Instagram, oppure incolla la caption, "
    "oppure mandami uno screenshot della ricetta."
)


@dataclass
class Incoming:
    chat_id: int
    user_id: int
    text: str
    photo_file_id: str | None


class TelegramApi:
    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self.token = token
        self.client = client or httpx.Client(timeout=45)

    def _call(self, method: str, **params):
        response = self.client.post(
            f"https://api.telegram.org/bot{self.token}/{method}", json=params
        )
        response.raise_for_status()
        return response.json()["result"]

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        return self._call("getUpdates", offset=offset, timeout=timeout)

    def send_message(self, chat_id: int, text: str) -> None:
        self._call("sendMessage", chat_id=chat_id, text=text)

    def download_file(self, file_id: str, dest: Path) -> Path:
        file_path = self._call("getFile", file_id=file_id)["file_path"]
        response = self.client.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}")
        response.raise_for_status()
        dest.write_bytes(response.content)
        return dest


def parse_update(update: dict) -> Incoming | None:
    message = update.get("message")
    if not message or "from" not in message:
        return None
    photos = message.get("photo") or []
    return Incoming(
        chat_id=message["chat"]["id"],
        user_id=message["from"]["id"],
        text=message.get("text") or message.get("caption") or "",
        photo_file_id=photos[-1]["file_id"] if photos else None,  # last = largest size
    )


def build_post(message: Incoming, api: TelegramApi, cookies_file: Path | None) -> SourcePost:
    url = find_instagram_url(message.text)
    if message.photo_file_id:
        image = api.download_file(message.photo_file_id, Path(tempfile.mkdtemp()) / "shot.jpg")
        return from_screenshots([image], url=url, caption=message.text)
    if url and not is_sufficient(message.text)[0]:  # a shared link, not a pasted recipe
        return fetch_instagram(url, cookies_file=cookies_file)
    return from_caption(message.text, url=url)


def handle_update(
    update: dict,
    api: TelegramApi,
    allowed_user_ids: frozenset[int],
    run_import: Callable[[SourcePost], ImportedRecipe],
    cookies_file: Path | None = None,
    output_dir: Path = IMPORTED_DIR,
) -> None:
    message = parse_update(update)
    if message is None:
        return
    if message.user_id not in allowed_user_ids:
        log.warning("ignoring message from unauthorized user %s", message.user_id)
        return
    if not message.text.strip() and not message.photo_file_id:
        api.send_message(message.chat_id, HELP)
        return
    try:
        recipe = run_import(build_post(message, api, cookies_file))
    except IngestionError as error:
        reply = f"Non sono riuscito a leggere il link: {error}"
    except InsufficientContentError as error:
        reply = f"Contenuto insufficiente: {error}"
    except StructuringError as error:
        reply = f"Non sono riuscito a strutturare la ricetta: {error}"
    except RuntimeError as error:  # e.g. the optional `media` extra is not installed
        reply = f"Errore: {error}"
    else:
        save(recipe, output_dir)
        reply = summarize(recipe)
    api.send_message(message.chat_id, reply)


def poll(api: TelegramApi, handler: Callable[[dict], None]) -> None:
    offset = None
    while True:
        for update in api.get_updates(offset):
            offset = update["update_id"] + 1
            try:
                handler(update)
            except Exception:  # keep the bot alive; the failure is in the log
                log.exception("failed to handle update %s", update.get("update_id"))


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.telegram_bot_token or not settings.anthropic_api_key:
        log.error("TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY are required (see .env.example)")
        return 2
    if not settings.telegram_allowed_user_ids:
        log.error("TELEGRAM_ALLOWED_USER_IDS is empty: nobody would be allowed to use the bot")
        return 2

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    ingredients = load_ingredients()
    transcriber = FasterWhisperTranscriber(settings.whisper_model)
    describer = ClaudeFrameDescriber(client, settings.model)

    def run_import(post: SourcePost) -> ImportedRecipe:
        return import_post(post, ingredients, client, settings.model, transcriber, describer)

    api = TelegramApi(settings.telegram_bot_token)
    log.info("bot started, waiting for messages")
    try:
        poll(
            api,
            lambda update: handle_update(
                update,
                api,
                settings.telegram_allowed_user_ids,
                run_import,
                settings.instagram_cookies_file,
            ),
        )
    except KeyboardInterrupt:
        log.info("bot stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
