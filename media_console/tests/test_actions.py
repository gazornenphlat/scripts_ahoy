"""Tests for the ported actions (Plex, Tdarr, RAR, recent items, context menu, WinRM).

None of these tests contact a server, run HandBrake or RAR, or touch the registry.
They cover the planning logic and the safety rules around it.
"""

from pathlib import Path

import pytest

import tools
from tools import (context_menu_commands, load_saved_computers, plex_commands,
                   rar_wizard_plan, recent_item_files, run_actions,
                   save_computers, select_tdarr_targets, unique_output_path,
                   validate_computer)


# ---------- 2. Plex ----------

def test_plex_commands_one_per_section_in_order():
    cmds = plex_commands("scanner.exe", [67, 3])
    assert cmds == [
        ["scanner.exe", "--scan", "--refresh", "--section", "67"],
        ["scanner.exe", "--scan", "--refresh", "--section", "3"],
    ]


# ---------- 11. Tdarr ----------

def test_tdarr_selects_error_and_cancelled_case_insensitively():
    records = [
        {"_id": "a", "TranscodeDecisionMaker": "Transcode Error"},
        {"_id": "b", "TranscodeDecisionMaker": "transcode cancelled"},
        {"_id": "c", "TranscodeDecisionMaker": "Transcode Success"},
        {"_id": "d"},
        "not a record",
    ]
    picked = [r["_id"] for r in select_tdarr_targets(records)]
    assert picked == ["a", "b"]


def test_tdarr_select_handles_non_list_response():
    assert select_tdarr_targets({"error": "nope"}) == []
    assert select_tdarr_targets(None) == []


def test_unique_output_path_returns_free_name(tmp_path):
    taken = {str(tmp_path / "Show.mkv"), str(tmp_path / "Show (1).mkv")}
    out = unique_output_path(tmp_path, "Show", ".mkv", exists=lambda p: p in taken)
    assert out == tmp_path / "Show (2).mkv"


def test_unique_output_path_when_free(tmp_path):
    assert unique_output_path(tmp_path, "Show", ".mkv", exists=lambda p: False) == tmp_path / "Show.mkv"


# ---------- 12. RAR wizard ----------

def make_tree(root):
    (root / "sub").mkdir()
    (root / "top.txt").write_text("a")
    (root / "other.txt").write_text("b")
    (root / "sub" / "deep.txt").write_text("c")


def test_rar_mode1_one_archive_per_top_level_file(tmp_path):
    make_tree(tmp_path)
    items, skipped = rar_wizard_plan(tmp_path, 1, "x", "stamp", "rar")
    archives = sorted(i[2].name for i in items)
    assert archives == ["other.rar", "top.rar"]
    assert skipped == []


def test_rar_mode2_uses_no_paths_and_recurses(tmp_path):
    make_tree(tmp_path)
    items, _ = rar_wizard_plan(tmp_path, 2, "x", "stamp", "rar")
    assert sorted(i[2].name for i in items) == ["deep.rar", "other.rar", "top.rar"]
    assert all("-ep" in i[1] for i in items)


def test_rar_mode3_single_archive_for_top_level_files_only(tmp_path):
    make_tree(tmp_path)
    items, _ = rar_wizard_plan(tmp_path, 3, "batch", "stamp", "rar")
    assert len(items) == 1
    assert items[0][2].name == "batch_stamp.rar"
    assert items[0][3] == 2  # top.txt and other.txt, not deep.txt


def test_rar_mode4_includes_subfolders(tmp_path):
    make_tree(tmp_path)
    items, _ = rar_wizard_plan(tmp_path, 4, "all", "stamp", "rar")
    assert items[0][3] == 3


def test_rar_existing_archive_is_skipped_not_updated(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "top.rar").write_text("existing")
    items, skipped = rar_wizard_plan(tmp_path, 1, "x", "stamp", "rar")
    assert "top.rar" not in [i[2].name for i in items]
    assert any("top.rar" in s for s in skipped)
    assert (tmp_path / "top.rar").read_text() == "existing"


def test_rar_commands_use_relative_names(tmp_path):
    make_tree(tmp_path)
    items, _ = rar_wizard_plan(tmp_path, 4, "all", "stamp", "rar")
    args = items[0][1]
    assert args[0] == "rar"
    assert all(not Path(a).is_absolute() for a in args[1:])


def test_rar_empty_folder_plans_nothing(tmp_path):
    assert rar_wizard_plan(tmp_path, 3, "x", "stamp", "rar") == ([], [])


# ---------- 13. Recent items ----------

def test_recent_items_lists_only_files_in_known_locations(tmp_path):
    base = tmp_path / "Microsoft" / "Windows" / "Recent"
    (base / "AutomaticDestinations").mkdir(parents=True)
    (base / "CustomDestinations").mkdir()
    (base / "a.lnk").write_text("x")
    (base / "AutomaticDestinations" / "b.automaticDestinations-ms").write_text("x")
    (base / "CustomDestinations" / "c.customDestinations-ms").write_text("x")
    (base / "subdir").mkdir()  # directories are never listed
    names = sorted(p.name for p in recent_item_files(tmp_path))
    assert names == ["a.lnk", "b.automaticDestinations-ms", "c.customDestinations-ms"]


def test_recent_items_missing_folder_gives_empty_list(tmp_path):
    assert recent_item_files(tmp_path) == []


# ---------- 14. Context menu ----------

def test_context_menu_commands_use_known_handler_ids():
    cmds = context_menu_commands()
    assert len(cmds) == 2
    joined = [" ".join(c) for c in cmds]
    assert any("{C2FBB630-2971-11D1-A18C-00C04FD75D13}" in j and "Copy To" in j for j in joined)
    assert any("{C2FBB631-2971-11D1-A18C-00C04FD75D13}" in j and "Move To" in j for j in joined)
    assert all(c[:2] == ["reg", "add"] and c[-1] == "/f" for c in cmds)


# ---------- 15. WinRM saved computers ----------

def test_saved_computers_never_contain_a_password(tmp_path):
    path = tmp_path / "windows_computers.json"
    save_computers(path, {"Office": {"host": "10.0.0.7", "username": "Administrator"}})
    text = path.read_text(encoding="utf-8").lower()
    assert "password" not in text


def test_saved_computers_round_trip(tmp_path):
    path = tmp_path / "windows_computers.json"
    data = {"Office": {"host": "10.0.0.7", "username": "Administrator"}}
    save_computers(path, data)
    assert load_saved_computers(path) == data


def test_missing_saved_computers_file_is_empty(tmp_path):
    assert load_saved_computers(tmp_path / "none.json") == {}


def test_bad_saved_computers_file_is_reported(tmp_path):
    path = tmp_path / "windows_computers.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_saved_computers(path)


@pytest.mark.parametrize("name,host,user", [
    ("", "10.0.0.1", "admin"),
    ("PC", "  ", "admin"),
    ("PC", "10.0.0.1", ""),
    ("PC", "my host", "admin"),
    ("PC", "host/evil", "admin"),
])
def test_invalid_computer_entries_are_rejected(name, host, user):
    assert validate_computer(name, host, user) is not None


def test_valid_computer_entry_is_accepted():
    assert validate_computer("Office", "10.0.0.7", "DOMAIN\\admin") is None


# ---------- dry run covers the new actions too ----------

def test_dry_run_never_calls_new_action_bodies(monkeypatch):
    monkeypatch.setattr(tools, "DRY_RUN", True)
    calls = []
    run_actions([("PC", {"host": "x"})], lambda it: "plan", lambda it: calls.append(it) or True,
                "reboot")
    assert calls == []
