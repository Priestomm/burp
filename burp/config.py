"""Runtime configuration read from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "burp.db"


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


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    telegram_bot_token: str | None
    telegram_allowed_user_ids: frozenset[int]
    whisper_model: str
    instagram_cookies_file: Path | None
    db_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        cookies = os.environ.get("INSTAGRAM_COOKIES_FILE")
        db_path = os.environ.get("BURP_DB_PATH")
        allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            model=os.environ.get("BURP_MODEL") or DEFAULT_MODEL,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_allowed_user_ids=frozenset(
                int(part) for part in allowed.split(",") if part.strip()
            ),
            whisper_model=os.environ.get("WHISPER_MODEL") or "base",
            instagram_cookies_file=Path(cookies) if cookies else None,
            db_path=Path(db_path) if db_path else DEFAULT_DB_PATH,
        )
