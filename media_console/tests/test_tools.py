from pathlib import Path

import pytest

import tools
from tools import (find_episode_dupes, plan_renames, rank_copies,
                   run_actions, verify_conversion)


# ---------- duplicate detection and ranking ----------

def test_dupes_group_by_episode_code_case_insensitively():
    videos = [
        Path("a/Show.S01E02.mp4"),
        Path("b/show.s01e02.mkv"),
        Path("c/Show.S01E03.mkv"),
    ]
    dupes = find_episode_dupes(videos)
    assert list(dupes) == ["S01E02"]
    assert len(dupes["S01E02"]) == 2


def test_single_copies_are_not_reported():
    assert find_episode_dupes([Path("Show.S01E01.mkv")]) == {}


def test_files_without_episode_code_are_ignored():
    assert find_episode_dupes([Path("movie.mkv"), Path("movie2.mkv")]) == {}


def test_rank_prefers_mkv_then_mp4_then_avi_then_other():
    ranked = rank_copies([Path("x.avi"), Path("x.wmv"), Path("x.mp4"), Path("x.mkv")])
    assert [p.suffix for p in ranked] == [".mkv", ".mp4", ".avi", ".wmv"]


# ---------- folder rename planning ----------

def test_underscores_become_spaces(tmp_path):
    (tmp_path / "my_album").mkdir()
    planned, skipped = plan_renames(tmp_path, "_", " ")
    assert [d.name for d, _ in planned] == ["my_album"]
    assert planned[0][1].name == "my album"
    assert skipped == []


def test_deepest_folders_are_renamed_first(tmp_path):
    (tmp_path / "a_parent" / "b_child").mkdir(parents=True)
    planned, _ = plan_renames(tmp_path, "_", " ")
    names = [d.name for d, _ in planned]
    assert names.index("b_child") < names.index("a_parent")


def test_removing_text_that_leaves_empty_name_is_skipped(tmp_path):
    (tmp_path / "xyz").mkdir()
    planned, skipped = plan_renames(tmp_path, "xyz", "")
    assert planned == []
    assert skipped == [("xyz", "new name would be empty")]


def test_collision_with_existing_folder_is_skipped(tmp_path):
    (tmp_path / "a_b").mkdir()
    (tmp_path / "a b").mkdir()
    planned, skipped = plan_renames(tmp_path, "_", " ")
    assert planned == []
    assert skipped == [("a_b", "'a b' already exists")]


def test_two_folders_mapping_to_same_name_only_one_is_planned(tmp_path):
    # Removing "_" turns both "ab_" and "a_b" into "ab": only the first is planned.
    (tmp_path / "ab_").mkdir()
    (tmp_path / "a_b").mkdir()
    planned, skipped = plan_renames(tmp_path, "_", "")
    assert len(planned) == 1
    assert len(skipped) == 1
    assert skipped[0][1] == "'ab' already exists"


def test_nothing_changes_on_disk_when_planning(tmp_path):
    (tmp_path / "x_y").mkdir()
    plan_renames(tmp_path, "_", " ")
    assert (tmp_path / "x_y").is_dir()
    assert not (tmp_path / "x y").exists()


# ---------- conversion verification ----------

def test_verified_when_ffmpeg_ok_and_durations_match():
    assert verify_conversion(0, 200.0, 200.4, 1.0)


def test_rejected_when_ffmpeg_failed_even_if_durations_match():
    assert not verify_conversion(1, 200.0, 200.0, 1.0)


def test_rejected_when_duration_differs_beyond_tolerance():
    assert not verify_conversion(0, 200.0, 150.0, 1.0)


def test_rejected_when_source_duration_unknown():
    assert not verify_conversion(0, None, 200.0, 1.0)


def test_rejected_when_output_duration_unknown():
    assert not verify_conversion(0, 200.0, None, 1.0)


def test_rejected_when_duration_is_zero():
    assert not verify_conversion(0, 0.0, 0.0, 1.0)


# ---------- dry run never changes anything ----------

def test_dry_run_does_not_call_act(monkeypatch):
    monkeypatch.setattr(tools, "DRY_RUN", True)
    calls = []

    def act(item):
        calls.append(item)
        return True

    run_actions([("a", "b")], lambda it: str(it), act, "test label")
    assert calls == []


def test_declined_confirmation_does_not_call_act(monkeypatch):
    monkeypatch.setattr(tools, "DRY_RUN", False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "no")
    calls = []
    run_actions([("a", "b")], lambda it: str(it), lambda it: calls.append(it) or True, "test")
    assert calls == []


def test_confirmed_action_runs_on_every_item(monkeypatch):
    monkeypatch.setattr(tools, "DRY_RUN", False)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "APPLY")
    calls = []
    run_actions([1, 2], str, lambda it: calls.append(it) or True, "test")
    assert calls == [1, 2]
