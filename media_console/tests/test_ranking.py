import json
from pathlib import Path

from tools import parse_ffprobe_video, probe_video, rank_by_quality


def entry(name, height=None, bitrate=None):
    return {"path": Path(name), "height": height, "bitrate": bitrate}


def names(ranked):
    return [Path(e["path"]).name for e in ranked]


def test_higher_resolution_wins_over_container():
    ranked = rank_by_quality([
        entry("show.mkv", height=720, bitrate=5_000_000),
        entry("show.mp4", height=1080, bitrate=3_000_000),
    ])
    assert names(ranked) == ["show.mp4", "show.mkv"]


def test_bitrate_breaks_resolution_tie():
    ranked = rank_by_quality([
        entry("low.mkv", height=1080, bitrate=2_000_000),
        entry("high.mp4", height=1080, bitrate=8_000_000),
    ])
    assert names(ranked) == ["high.mp4", "low.mkv"]


def test_container_breaks_full_tie():
    ranked = rank_by_quality([
        entry("x.avi", height=1080, bitrate=4_000_000),
        entry("x.mkv", height=1080, bitrate=4_000_000),
        entry("x.mp4", height=1080, bitrate=4_000_000),
    ])
    assert names(ranked) == ["x.mkv", "x.mp4", "x.avi"]


def test_unknown_quality_sorts_after_known():
    ranked = rank_by_quality([
        entry("unknown.mkv"),
        entry("known.avi", height=480, bitrate=1_000_000),
    ])
    assert names(ranked) == ["known.avi", "unknown.mkv"]


def test_unknown_bitrate_sorts_after_known_bitrate_at_same_height():
    ranked = rank_by_quality([
        entry("nobitrate.mkv", height=720),
        entry("bitrate.avi", height=720, bitrate=100),
    ])
    assert names(ranked) == ["bitrate.avi", "nobitrate.mkv"]


def test_ranking_is_deterministic_for_identical_entries():
    ranked = rank_by_quality([entry("b.mkv", 720, 1), entry("a.mkv", 720, 1)])
    assert names(ranked) == ["a.mkv", "b.mkv"]


def test_parse_ffprobe_reads_height_and_bitrate():
    text = json.dumps({"streams": [{"height": 1080}], "format": {"bit_rate": "4500000"}})
    assert parse_ffprobe_video(text) == (1080, 4_500_000)


def test_parse_ffprobe_handles_missing_fields():
    assert parse_ffprobe_video(json.dumps({"streams": [], "format": {}})) == (None, None)


def test_parse_ffprobe_handles_bad_json():
    assert parse_ffprobe_video("not json") == (None, None)


def test_parse_ffprobe_handles_non_numeric_values():
    text = json.dumps({"streams": [{"height": "tall"}], "format": {"bit_rate": "fast"}})
    assert parse_ffprobe_video(text) == (None, None)


def test_probe_video_returns_unknown_when_ffprobe_missing(tmp_path):
    assert probe_video(tmp_path / "x.mkv", str(tmp_path / "no-such-ffprobe")) == (None, None)
