import copy
import json

import pytest

from common import ConfigError, load_config, validate_config

VALID = {
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffprobe",
    "rar_path": "C:\\Program Files\\WinRAR\\Rar.exe",
    "tv_dupes_dir": "N:\\TV Shows\\D",
    "report_dir": "N:\\",
    "duration_tolerance_seconds": 1.0,
    "reboot_delay_seconds": 30,
}


def test_valid_config_has_no_problems():
    assert validate_config(VALID) == []


def test_shipped_config_is_valid():
    # The config.json in the repo must always pass validation.
    load_config()


def test_missing_key_is_reported():
    cfg = copy.deepcopy(VALID)
    del cfg["rar_path"]
    assert "missing key: rar_path" in validate_config(cfg)


def test_wrong_type_is_reported():
    cfg = copy.deepcopy(VALID)
    cfg["reboot_delay_seconds"] = "30"
    problems = validate_config(cfg)
    assert any(p.startswith("reboot_delay_seconds: expected int") for p in problems)


def test_bool_is_not_accepted_as_number():
    cfg = copy.deepcopy(VALID)
    cfg["reboot_delay_seconds"] = True
    assert any("reboot_delay_seconds" in p for p in validate_config(cfg))


def test_empty_string_is_reported():
    cfg = copy.deepcopy(VALID)
    cfg["ffmpeg"] = "   "
    assert "ffmpeg: must not be empty" in validate_config(cfg)


def test_negative_minimum_is_reported():
    cfg = copy.deepcopy(VALID)
    cfg["duration_tolerance_seconds"] = -1
    assert any("must be at least 0" in p for p in validate_config(cfg))


def test_unknown_key_is_reported_as_possible_typo():
    cfg = copy.deepcopy(VALID)
    cfg["ffmepg"] = "ffmpeg"
    assert any("unknown key(s)" in p and "ffmepg" in p for p in validate_config(cfg))


def test_non_object_is_rejected():
    assert validate_config(["not", "an", "object"]) == ["config must be a JSON object"]


def test_all_problems_reported_together():
    problems = validate_config({"ffmpeg": 1, "extra": True})
    assert len(problems) > 3


def test_load_config_raises_with_all_problems(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"ffmpeg": 1}), encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "missing key: ffprobe" in str(exc.value)


def test_load_config_reports_bad_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config(path)


def test_load_config_reports_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.json")
