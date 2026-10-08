"""Telegram bot: forward it an Instagram link (or paste a caption, or send a screenshot).

    uv run burp bot

Long polling over the Bot API with httpx. Only the user ids in TELEGRAM_ALLOWED_USER_IDS are
served, and only what they send explicitly is processed.
"""

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from burp.catalog import SynonymIndex, load_ingredients
from burp.config import Settings, anthropic_client, load_env, setup_logging
from burp.extract import InsufficientContentError, is_sufficient
from burp.frames import ClaudeFrameDescriber
from burp.ingest import (
    IngestionError,
    SourcePost,
    fetch_instagram,
    find_instagram_url,
    from_caption,
    from_screenshots,
    from_video,
)
from burp.ingredient_images import build_finder
from burp.library import Library
from burp.models import ImportedRecipe
from burp.photo import ClaudeFramePicker
from burp.pipeline import import_post
from burp.render import full_text, one_line, summarize
from burp.structure import StructuringError
from burp.transcribe import FasterWhisperTranscriber
from burp.worker import INGREDIENTS, default_remover, queue_photo, start_in_background

log = logging.getLogger("bot")

HELP = (
    "Inoltrami il link di un post o reel Instagram, oppure incolla la caption, "
    "oppure mandami uno screenshot o un video della ricetta: se si vede il piatto finito, "
    "diventa la foto della ricetta.\n\n"
    "Per consultare la libreria:\n"
    "/cerca parole – ricette con quelle parole nel titolo, nei tag o negli ingredienti "
    "(es. /cerca vegana ceci); senza parole, le ultime salvate\n"
    "/ricetta numero – la ricetta completa (es. /ricetta 3)\n"
    "/foto numero – mandalo come didascalia di un'immagine o di un video per dare una foto "
    "a una ricetta già salvata"
)
COMMANDS = [
    ("cerca", "cerca per titolo, tag o ingrediente"),
    ("ricetta", "mostra una ricetta dal suo numero"),
    ("foto", "come didascalia di un'immagine: la foto di una ricetta"),
    ("aiuto", "cosa posso fare"),
]
MAX_RESULTS = 20
MAX_MESSAGE = 4000  # Telegram's limit is 4096 characters
MAX_DOWNLOAD = 20 * 1024 * 1024  # bots cannot download bigger files from Telegram


@dataclass
class Incoming:
    chat_id: int
    user_id: int
    text: str
    photo_file_id: str | None
    video_file_id: str | None = None
    video_size: int = 0


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
        for chunk in split_message(text):
            self._call("sendMessage", chat_id=chat_id, text=chunk)

    def set_commands(self, commands: list[tuple[str, str]]) -> None:
        """The command menu Telegram shows next to the text field."""
        self._call(
            "setMyCommands",
            commands=[{"command": name, "description": text} for name, text in commands],
        )

    def download_file(self, file_id: str, dest: Path) -> Path:
        file_path = self._call("getFile", file_id=file_id)["file_path"]
        response = self.client.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}")
        response.raise_for_status()
        dest.write_bytes(response.content)
        return dest


def split_message(text: str, limit: int = MAX_MESSAGE) -> list[str]:
    """Split on line breaks so that every chunk fits in one Telegram message."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        for start in range(0, len(line), limit):  # an overlong line is cut
            piece = line[start : start + limit]
            if len(current) + len(piece) > limit:
                chunks.append(current)
                current = ""
            current += piece
    chunks.append(current)
    return [chunk.rstrip("\n") for chunk in chunks if chunk.strip()]


def parse_update(update: dict) -> Incoming | None:
    message = update.get("message")
    if not message or "from" not in message:
        return None
    photos = message.get("photo") or []
    document = message.get("document") or {}
    video = message.get("video") or (
        document if str(document.get("mime_type", "")).startswith("video/") else {}
    )
    return Incoming(
        chat_id=message["chat"]["id"],
        user_id=message["from"]["id"],
        text=message.get("text") or message.get("caption") or "",
        photo_file_id=photos[-1]["file_id"] if photos else None,  # last = largest size
        video_file_id=video.get("file_id"),
        video_size=video.get("file_size") or 0,
    )


def download_media(message: Incoming, api: TelegramApi) -> Path | None:
    """The photo or video attached to a message, saved to a temporary file."""
    folder = Path(tempfile.mkdtemp(prefix="burp-tg-"))
    if message.video_file_id:
        if message.video_size > MAX_DOWNLOAD:
            raise IngestionError(
                "il video supera i 20 MB che un bot può scaricare: mandane uno più corto "
                "o uno screenshot del piatto"
            )
        return api.download_file(message.video_file_id, folder / "clip.mp4")
    if message.photo_file_id:
        return api.download_file(message.photo_file_id, folder / "shot.jpg")
    return None


def build_post(message: Incoming, api: TelegramApi, cookies_file: Path | None) -> SourcePost:
    url = find_instagram_url(message.text)
    if message.video_file_id:
        return from_video(download_media(message, api), url=url, caption=message.text)
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
    library: Library,
    cookies_file: Path | None = None,
    media_dir: Path | None = None,
    photo_from_reel: bool = False,
) -> None:
    message = parse_update(update)
    if message is None:
        return
    if message.user_id not in allowed_user_ids:
        log.warning("ignoring message from unauthorized user %s", message.user_id)
        return
    has_media = bool(message.photo_file_id or message.video_file_id)
    if not message.text.strip() and not has_media:
        api.send_message(message.chat_id, HELP)
        return
    if message.text.strip().partition(" ")[0].split("@")[0].lower() == "/foto":
        api.send_message(message.chat_id, attach_photo(message, api, library, media_dir))
        return
    if message.text.startswith("/") and not has_media:
        api.send_message(message.chat_id, run_command(message.text, library))
        return
    url = find_instagram_url(message.text)
    # Checked before downloading anything or calling the model: a duplicate costs nothing.
    if url and (existing := library.find_by_url(url)):
        reply = f"Questa ricetta è già nella tua libreria (#{existing.id}).\n\n"
        api.send_message(message.chat_id, reply + summarize(existing.imported))
        return
    try:
        post = build_post(message, api, cookies_file)
        imported = run_import(post)
    except IngestionError as error:
        reply = f"Non sono riuscito a leggere il link: {error}"
    except InsufficientContentError as error:
        reply = f"Contenuto insufficiente: {error}"
    except StructuringError as error:
        reply = f"Non sono riuscito a strutturare la ricetta: {error}"
    except RuntimeError as error:  # e.g. the optional `media` extra is not installed
        reply = f"Errore: {error}"
    except Exception as error:  # a bug: say so instead of leaving the chat silent
        log.exception("import failed")
        reply = (
            f"Errore imprevisto ({type(error).__name__}: {error}). "
            "Riprova, oppure incolla la caption o mandami uno screenshot."
        )
    else:
        saved, created = library.add(imported)
        status = f"Salvata come #{saved.id}." if created else f"Già in libreria (#{saved.id})."
        reel = post.downloaded_video if photo_from_reel else None
        if created:
            library.enqueue(INGREDIENTS, saved.id, [])
        if (
            created
            and media_dir
            and queue_photo(library, saved.id, post.photo_inputs, media_dir, reel=reel)
        ):
            status += " Preparo la foto del piatto."
        reply = f"{summarize(imported)}\n\n{status}"
    api.send_message(message.chat_id, reply)


def attach_photo(
    message: Incoming, api: TelegramApi, library: Library, media_dir: Path | None
) -> str:
    """ "/foto 3" as the caption of a picture or a video: the dish photo for recipe #3."""
    _, _, argument = message.text.strip().partition(" ")
    number = argument.strip().lstrip("#")
    if not number.isdigit():
        return "Scrivi /foto e il numero della ricetta come didascalia, es. /foto 3."
    if not (message.photo_file_id or message.video_file_id):
        return f"Allega un'immagine o un video del piatto, con didascalia /foto {number}."
    if library.get(int(number)) is None:
        return f"Non c'è nessuna ricetta #{number}."
    if media_dir is None:
        return "Le foto non sono attive su questo bot."
    try:
        media = download_media(message, api)
    except IngestionError as error:
        return f"Non posso usarlo: {error}"
    queue_photo(library, int(number), [media], media_dir)
    return f"Preparo la foto per la ricetta #{number}: guardala nella dashboard tra poco."


def run_command(text: str, library: Library) -> str:
    """Answer /cerca, /ricetta and /aiuto (or /start, the first message Telegram sends)."""
    command, _, argument = text.strip().partition(" ")
    command = command[1:].split("@")[0].lower()  # "/cerca@burp_bot" in group chats
    argument = argument.strip()
    if command == "cerca":
        results = library.search(text=argument)
        if not results:
            return f"Nessuna ricetta trovata per «{argument}»." if argument else "Libreria vuota."
        lines = [one_line(saved, pad=False) for saved in results[:MAX_RESULTS]]
        if len(results) > MAX_RESULTS:
            lines.append(f"… e altre {len(results) - MAX_RESULTS}: aggiungi qualche parola.")
        return "\n".join([*lines, "", "Apri una ricetta con /ricetta numero."])
    if command == "ricetta":
        number = argument.lstrip("#")
        if not number.isdigit():
            return "Scrivi il numero della ricetta, es. /ricetta 3 (lo trovi con /cerca)."
        saved = library.get(int(number))
        return full_text(saved) if saved else f"Non c'è nessuna ricetta #{number}."
    return HELP


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
    setup_logging("%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.telegram_bot_token or not settings.anthropic_api_key:
        log.error("TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY are required (see .env.example)")
        return 2
    if not settings.telegram_allowed_user_ids:
        log.error("TELEGRAM_ALLOWED_USER_IDS is empty: nobody would be allowed to use the bot")
        return 2

    client = anthropic_client(settings)
    catalog = SynonymIndex(load_ingredients())
    library = Library(settings.db_path, catalog)
    # Dish photos are made in the background, so a reply never waits for them.
    picker = ClaudeFramePicker(client, settings.fast_model)
    finder = build_finder(settings, client, default_remover())
    start_in_background(
        lambda: Library(settings.db_path, catalog), picker, settings.media_dir, finder
    )
    transcriber = FasterWhisperTranscriber(settings.whisper_model)
    describer = ClaudeFrameDescriber(client, settings.model)

    def run_import(post: SourcePost) -> ImportedRecipe:
        return import_post(post, catalog, client, settings.model, transcriber, describer)

    api = TelegramApi(settings.telegram_bot_token)
    api.set_commands(COMMANDS)
    log.info("bot started, waiting for messages")
    try:
        poll(
            api,
            lambda update: handle_update(
                update,
                api,
                settings.telegram_allowed_user_ids,
                run_import,
                library,
                settings.instagram_cookies_file,
                settings.media_dir,
                settings.photo_from_reel,
            ),
        )
    except KeyboardInterrupt:
        log.info("bot stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
