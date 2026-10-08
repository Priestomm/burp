"""Runtime configuration read from environment variables (and an optional .env file)."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DEFAULT_MODEL = "claude-opus-5-5"
# Small, cheap jobs: splitting a title, picking the best video frame.
DEFAULT_FAST_MODEL = "claude-haiku-5-5"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "burp.db"
DEFAULT_MEDIA_DIR = ROOT_DIR / "data" / "media"


def load_env(path: Path = ROOT_DIR / ".env") -> None:
    """Load KEY=VALUE lines from `path` into os.environ, never overriding existing variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def setup_logging(fmt: str = "%(levelname)s %(message)s") -> None:
    logging.basicConfig(level=logging.INFO, format=fmt)
    # HTTP clients log every request URL, and Telegram's URLs contain the bot token.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    fast_model: str
    telegram_bot_token: str | None
    telegram_allowed_user_ids: frozenset[int]
    whisper_model: str
    instagram_cookies_file: Path | None
    db_path: Path
    media_dir: Path
    # Opt-in, personal use only: take the dish photo from the reel downloaded with the link.
    photo_from_reel: bool
    pexels_api_key: str | None
    contact_email: str | None  # sent in the User-Agent to Open Food Facts

    @classmethod
    def from_env(cls) -> "Settings":
        cookies = os.environ.get("INSTAGRAM_COOKIES_FILE")
        db_path = os.environ.get("BURP_DB_PATH")
        media_dir = os.environ.get("BURP_MEDIA_DIR")
        allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            model=os.environ.get("BURP_MODEL") or DEFAULT_MODEL,
            fast_model=os.environ.get("BURP_FAST_MODEL") or DEFAULT_FAST_MODEL,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_allowed_user_ids=frozenset(
                int(part) for part in allowed.split(",") if part.strip()
            ),
            whisper_model=os.environ.get("WHISPER_MODEL") or "base",
            instagram_cookies_file=Path(cookies) if cookies else None,
            db_path=Path(db_path) if db_path else DEFAULT_DB_PATH,
            media_dir=Path(media_dir) if media_dir else DEFAULT_MEDIA_DIR,
            pexels_api_key=os.environ.get("PEXELS_API_KEY") or None,
            contact_email=os.environ.get("BURP_CONTACT_EMAIL") or None,
            photo_from_reel=os.environ.get("BURP_PHOTO_FROM_REEL", "").strip().lower()
            in ("1", "true", "yes", "si", "sì"),
        )


def anthropic_client(settings: "Settings"):
    """The API client. A request that hangs fails after 3 minutes and is retried, instead of
    blocking the bot or the worker for the SDK's default 10 minutes per attempt."""
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=180, max_retries=2)
