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
    # tool paths
    "ffmpeg": (str, None),
    "ffprobe": (str, None),
    "rar_path": (str, None),
    "handbrake_cli": (str, None),
    "plex_scanner": (str, None),
    # library locations
    "tv_dupes_dir": (str, None),
    "report_dir": (str, None),
    # plex
    "plex_sections": (list, None),          # non-empty list of positive ints, checked below
    # tdarr
    "tdarr_url": (str, None),
    "tdarr_api_key_env": (str, None),       # name of an environment variable, not the key itself
    "tdarr_out_ext": (str, None),
    "tdarr_finished_dir": (str, None),
    "tdarr_failed_dir": (str, None),
    "tdarr_min_output_bytes": (int, 0),
    # conversion and reboot behaviour
    "duration_tolerance_seconds": ((int, float), 0),
    "reboot_delay_seconds": (int, 0),
    # remote reboot
    "windows_computers_file": (str, None),
    "winrm_port": (int, 1),
    "winrm_use_https": (bool, None),
}


def _type_name(types) -> str:
    if types == (int, float):
        return "number"
    names = types if isinstance(types, tuple) else (types,)
    return " or ".join(t.__name__ for t in names)


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
        accepts_bool = types is bool or (isinstance(types, tuple) and bool in types)
        # bool is a subclass of int in Python, so reject it unless the key wants a bool.
        if isinstance(value, bool) and not accepts_bool:
            problems.append(f"{key}: expected {_type_name(types)}, got bool")
            continue
        if not isinstance(value, types):
            problems.append(f"{key}: expected {_type_name(types)}, got {type(value).__name__}")
            continue
        if isinstance(value, str) and not value.strip():
            problems.append(f"{key}: must not be empty")
        if key == "plex_sections":
            if not value:
                problems.append(f"{key}: must not be empty")
            elif any(isinstance(s, bool) or not isinstance(s, int) or s < 1 for s in value):
                problems.append(f"{key}: every entry must be a positive whole number")
            continue
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
