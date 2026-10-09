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


def test_a_taken_port_is_reported_before_anything_starts(tmp_path: Path):
    import os
    import socket

    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        service = dev.Service("api", [sys.executable, "-c", "pass"], tmp_path, port=port)
        [problem] = dev.busy_ports([service])
        assert f"porta {port} è già occupata" in problem
        assert f"PID {os.getpid()}" in problem  # lsof names this test as the holder
    assert dev.busy_ports([service]) == []


def test_closing_the_terminal_stops_the_children_too(tmp_path: Path):
    import os
    import signal
    import subprocess
    import time

    pid_file = tmp_path / "child.pid"
    sleeper = (
        f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); time.sleep(60)"
    )
    script = f"""
import sys
from pathlib import Path
from burp import dev
child = [sys.executable, "-c", {sleeper!r}]
sys.exit(dev.run([dev.Service("api", child, Path({str(tmp_path)!r}))]))
"""
    parent = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.DEVNULL)
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text():
            break
        time.sleep(0.05)
    child = int(pid_file.read_text())
    parent.send_signal(signal.SIGHUP)
    assert parent.wait(10) == 0
    time.sleep(0.2)
    try:
        os.kill(child, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive
