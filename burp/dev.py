"""`burp dev`: the API, the bot and the web app in one terminal, stopped together with Ctrl+C."""

import os
import signal
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from burp.config import ROOT_DIR, Settings

COLOURS = {"api": "\033[36m", "bot": "\033[35m", "web": "\033[33m", "mcp": "\033[32m"}
RESET = "\033[0m"


@dataclass(frozen=True)
class Service:
    name: str
    command: list[str]
    cwd: Path
    port: int | None = None  # where it listens, checked before anything starts


def services(
    settings: Settings, bot: bool = True, web: bool = True
) -> tuple[list[Service], list[str]]:
    """What to start, and why anything asked for is left out."""
    python = [sys.executable, "-m", "burp"]
    chosen = [Service("api", [*python, "serve"], ROOT_DIR, port=8000)]
    skipped = []
    if bot:
        if settings.telegram_bot_token and settings.telegram_allowed_user_ids:
            chosen.append(Service("bot", [*python, "bot"], ROOT_DIR))
        else:
            skipped.append("bot: TELEGRAM_BOT_TOKEN o TELEGRAM_ALLOWED_USER_IDS mancanti nel .env")
    if web:
        chosen.append(Service("web", ["pnpm", "dev"], ROOT_DIR / "web", port=3000))
    if settings.mcp_url and settings.mcp_password:  # for Claude: see README
        chosen.append(Service("mcp", [*python, "mcp"], ROOT_DIR, port=8001))
    return chosen, skipped


def busy_ports(chosen: list[Service]) -> list[str]:
    """One line for each port already taken, saying by whom when lsof can tell."""
    problems = []
    for service in chosen:
        if service.port is None:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", service.port))
                continue
            except OSError:
                pass
        holder = _holder(service.port)
        problems.append(
            f"[{service.name}] la porta {service.port} è già occupata"
            + (
                f" da {holder[1]} (PID {holder[0]}): fermalo con `kill {holder[0]}`"
                if holder
                else ""
            )
        )
    return problems


def _holder(port: int) -> tuple[str, str] | None:
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    fields = {line[0]: line[1:] for line in out.splitlines() if line}
    return (fields["p"], fields.get("c", "?")) if "p" in fields else None


def _relay(name: str, stream, out, lock: threading.Lock) -> None:
    colour = COLOURS.get(name, "") if out.isatty() else ""
    reset = RESET if colour else ""
    for line in iter(stream.readline, ""):
        with lock:
            out.write(f"{colour}[{name}]{reset} {line}")
            out.flush()


def run(chosen: list[Service], out=sys.stdout) -> int:
    """Start every service; when one exits or Ctrl+C is pressed, stop all of them."""
    lock = threading.Lock()
    stopped = threading.Event()
    first_exit: list[str] = []
    processes: dict[str, subprocess.Popen] = {}

    def watch(name: str, process: subprocess.Popen) -> None:
        process.wait()
        if not stopped.is_set():
            first_exit.append(name)
            stopped.set()

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    # `kill`, or the terminal closed: same as Ctrl+C. The children are in their own session
    # (so that Ctrl+C reaches only us), so without this they would outlive us.
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "FORCE_COLOR": "1"}
    for service in chosen:
        try:
            process = subprocess.Popen(
                service.command,
                cwd=service.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,  # Ctrl+C reaches us only; we stop the children in order
            )
        except FileNotFoundError:
            print(f"[{service.name}] comando non trovato: {service.command[0]}", file=sys.stderr)
            _stop(processes)
            return 1
        processes[service.name] = process
        threading.Thread(
            target=_relay, args=(service.name, process.stdout, out, lock), daemon=True
        ).start()
        threading.Thread(target=watch, args=(service.name, process), daemon=True).start()

    try:
        while not stopped.wait(0.5):
            pass
    except KeyboardInterrupt:
        stopped.set()
    _stop(processes)
    if first_exit:
        name = first_exit[0]
        code = processes[name].returncode
        print(
            f"\n[{name}] si è fermato (codice {code}): ho chiuso anche gli altri", file=sys.stderr
        )
        return 1
    print("\ntutto fermato", file=sys.stderr)
    return 0


def _stop(processes: dict[str, subprocess.Popen], grace: float = 5.0) -> None:
    for process in processes.values():
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
    for process in processes.values():
        try:
            process.wait(grace)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
