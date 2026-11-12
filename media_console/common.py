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


class ConfigError(Exception):
    """Raised when config.json is missing, unreadable, or has invalid values."""


# key -> (expected type(s), minimum value or None)
REQUIRED_CONFIG = {
    "ffmpeg": (str, None),
    "ffprobe": (str, None),
    "rar_path": (str, None),
    "tv_dupes_dir": (str, None),
    "report_dir": (str, None),
    "duration_tolerance_seconds": ((int, float), 0),
    "reboot_delay_seconds": (int, 0),
}


def validate_config(cfg) -> list:
    """Return a list of human-readable problems. An empty list means the config is valid."""
    if not isinstance(cfg, dict):
        return ["config must be a JSON object"]
    problems = []
    for key, (types, minimum) in REQUIRED_CONFIG.items():
        if key not in cfg:
            problems.append(f"missing key: {key}")
            continue
        value = cfg[key]
        # bool is a subclass of int in Python; reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, types):
            problems.append(f"{key}: expected {types.__name__ if isinstance(types, type) else 'number'}, got {type(value).__name__}")
            continue
        if isinstance(value, str) and not value.strip():
            problems.append(f"{key}: must not be empty")
        if minimum is not None and value < minimum:
            problems.append(f"{key}: must be at least {minimum}, got {value}")
    unknown = sorted(set(cfg) - set(REQUIRED_CONFIG))
    if unknown:
        problems.append(f"unknown key(s), check for typos: {', '.join(unknown)}")
    return problems


def load_config(path=None) -> dict:
    """Load and validate config.json. Raises ConfigError listing every problem found."""
    path = Path(path) if path else BASE_DIR / "config.json"
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"config is not valid JSON ({path}): {e}") from None
    problems = validate_config(cfg)
    if problems:
        raise ConfigError("config.json has problems:\n  - " + "\n  - ".join(problems))
    return cfg


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
