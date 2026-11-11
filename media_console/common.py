"""Shared helpers for the media console tools."""

import json
import shutil
import subprocess
from pathlib import Path

GREEN = "\033[38;2;44;255;87m"
AMBER = "\033[38;2;255;178;0m"
RED = "\033[38;2;255;51;51m"
RESET = "\033[0m"

BASE_DIR = Path(__file__).resolve().parent


def say(msg: str = "", color: str = GREEN) -> None:
    print(f"{color}{msg}{RESET}")


def warn(msg: str) -> None:
    say(msg, AMBER)


def error(msg: str) -> None:
    say(msg, RED)


def load_config() -> dict:
    with open(BASE_DIR / "config.json", encoding="utf-8") as f:
        return json.load(f)


def have_command(cmd: str) -> bool:
    return Path(cmd).exists() or shutil.which(cmd) is not None


def confirm(summary: str, word: str) -> bool:
    warn(summary)
    answer = input(f"{AMBER}Type {word} to apply, anything else to cancel: {RESET}").strip()
    return answer == word


def ask_dir(prompt: str):
    raw = input(f"{AMBER}{prompt}{RESET}").strip().strip('"')
    if not raw:
        return None
    path = Path(raw)
    if not path.is_dir():
        error(f"Not a directory: {raw}")
        return None
    return path


def probe_duration(path: Path, ffprobe: str):
    """Return media duration in seconds, or None if it cannot be read."""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def pause() -> None:
    input(f"\n{AMBER}Press Enter to return to the menu...{RESET}")
