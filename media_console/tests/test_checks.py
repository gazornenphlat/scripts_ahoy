import shutil
import subprocess

import pytest

from tools import count_streams, decodes_cleanly

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_count_streams_is_zero_when_ffprobe_missing(tmp_path):
    assert count_streams(tmp_path / "x.mp3", str(tmp_path / "no-ffprobe"), "a") == 0


def test_decodes_cleanly_is_false_when_ffmpeg_missing(tmp_path):
    assert decodes_cleanly(tmp_path / "x.mp3", str(tmp_path / "no-ffmpeg")) is False


def test_decodes_cleanly_is_false_for_placeholder_file(tmp_path):
    # Placeholder files, as made by make_sample_library.py, must never pass the check.
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg not installed")
    fake = tmp_path / "fake.mp3"
    fake.write_text("not audio", encoding="utf-8")
    assert decodes_cleanly(fake, "ffmpeg") is False


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg and ffprobe")
def test_real_audio_passes_decode_and_stream_checks(tmp_path):
    wav = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", str(wav)], check=True)
    assert count_streams(wav, "ffprobe", "a") == 1
    assert decodes_cleanly(wav, "ffmpeg") is True


@pytest.mark.skipif(not HAVE_FFMPEG, reason="needs ffmpeg and ffprobe")
def test_truncated_audio_fails_decode_check(tmp_path):
    wav = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", str(wav)], check=True)
    data = wav.read_bytes()
    cut = tmp_path / "cut.wav"
    cut.write_bytes(data[: len(data) // 3])  # cut off mid-stream
    assert decodes_cleanly(cut, "ffmpeg") is False
