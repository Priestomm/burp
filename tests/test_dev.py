import io
import sys
from dataclasses import replace
from pathlib import Path

from burp import dev
from burp.config import Settings


def settings(token: str | None) -> Settings:
    base = Settings.from_env()
    return replace(base, telegram_bot_token=token, telegram_allowed_user_ids=frozenset({1}))


def test_the_bot_is_left_out_without_a_token():
    chosen, skipped = dev.services(settings(None))
    assert [s.name for s in chosen] == ["api", "web"]
    assert "TELEGRAM_BOT_TOKEN" in skipped[0]
    chosen, skipped = dev.services(settings("x"), web=False)
    assert [s.name for s in chosen] == ["api", "bot"] and skipped == []


def test_when_one_service_stops_the_others_are_stopped_too(tmp_path: Path):
    long = dev.Service(
        "api", [sys.executable, "-c", "import time; print('su'); time.sleep(60)"], tmp_path
    )
    short = dev.Service("bot", [sys.executable, "-c", "print('ciao')"], tmp_path)
    out = io.StringIO()
    assert dev.run([long, short], out=out) == 1
    lines = out.getvalue().splitlines()
    assert "[bot] ciao" in lines and "[api] su" in lines
