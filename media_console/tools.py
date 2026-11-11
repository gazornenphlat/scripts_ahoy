#!/usr/bin/env python3
"""Media console tools: menu items 1, 3-10 from scripts_ahoy.py, rewritten safely.

Safety model:
  * Dry run is ON at startup. Dry run only previews; nothing is changed.
  * With dry run OFF, every planned change is listed first and needs a typed word.
  * Source files are deleted only after the replacement is verified.
"""

import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from common import (AMBER, ask_dir, confirm, error, have_command, load_config,
                    pause, probe_duration, say, warn)

CFG = load_config()
DRY_RUN = True

AUDIO_EXTS = (".mp3", ".flac", ".m4a")
VIDEO_EXTS = (".mkv", ".mp4", ".avi")
PRIORITY = {".mkv": 1, ".mp4": 2, ".avi": 3}
FLAC_ARGS = ["-vn", "-map_metadata", "0", "-id3v2_version", "3", "-b:a", "320k"]
MKA_ARGS = ["-vn", "-ar", "44100", "-ac", "2", "-b:a", "320k"]


# ---------- shared plan / apply machinery ----------

def run_actions(items, describe, act, label, word="APPLY"):
    """Preview every item, then act on them only if dry run is off and confirmed."""
    if not items:
        say("Nothing to do.")
        return
    for it in items:
        say(describe(it))
    say(f"\n{len(items)} item(s) planned.")
    if DRY_RUN:
        warn("DRY RUN is ON: nothing was changed.")
        return
    if not confirm(f"About to: {label} ({len(items)} item(s))", word):
        warn("Cancelled. Nothing was changed.")
        return
    ok = sum(1 for it in items if act(it))
    say(f"Finished: {ok}/{len(items)} succeeded.")


def move(item):
    src, dst = item
    try:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except OSError as e:
        error(f"FAILED {src}: {e}")
        return False


def move_describe(item):
    src, dst = item
    return f"{src}  ->  {dst}"


# ---------- 1. Fix music duplicates ----------

def fix_music_duplicates():
    root = ask_dir("Root folder (each of its subfolders is processed): ")
    if not root:
        return
    items = []
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(sub.iterdir()):
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                items.append((f, sub / f"track_{uuid.uuid4().hex[:8]}" / f.name))
    run_actions(items, move_describe, move,
                "move audio files into their own unique subfolders")


# ---------- 3. Scan duplicates (report only, never deletes) ----------

def scan_duplicates():
    folder = Path(CFG["tv_dupes_dir"])
    if not folder.is_dir():
        error(f"Not found: {folder}")
        return
    videos = sorted(
        (Path(r) / f for r, _dirs, files in os.walk(folder) for f in files
         if f.lower().endswith(VIDEO_EXTS)),
        key=lambda p: str(p).lower(),
    )
    episodes = {}
    for p in videos:
        m = re.search(r"S\d{2}E\d{2}", p.stem, re.IGNORECASE)
        if m:
            episodes.setdefault(m.group(0).upper(), []).append(p)
    dupes = {ep: fs for ep, fs in sorted(episodes.items()) if len(fs) > 1}

    now = datetime.now()
    report = Path(CFG["report_dir"]) / f"duplicate_scan_{now:%Y%m%d_%H%M%S}.txt"
    with open(report, "w", encoding="utf-8") as lf:
        lf.write(f"Duplicate scan {now:%Y-%m-%d %H:%M:%S}\n")
        lf.write(f"Directory: {folder}\n")
        lf.write(f"Video files found: {len(videos)}\n")
        lf.write("Ranking: MKV > MP4 > AVI. This scan deletes nothing.\n\n")
        for ep, fs in dupes.items():
            ranked = sorted(fs, key=lambda p: PRIORITY.get(p.suffix.lower(), 4))
            lf.write(f"{ep}  ({len(fs)} copies)\n")
            lf.write(f"  highest-ranked: {ranked[0]}\n")
            for p in ranked[1:]:
                lf.write(f"  review:         {p}\n")
            lf.write("\n")
        lf.write(f"Episodes with duplicates: {len(dupes)}\n")

    say(f"Scanned {len(videos)} video files; {len(dupes)} episode(s) have duplicates.")
    say(f"Report written to {report}")


# ---------- 4. Reboot (delayed, cancellable) ----------

def reboot():
    delay = int(CFG["reboot_delay_seconds"])
    cmd = ["shutdown", "/r", "/t", str(delay)]
    if DRY_RUN:
        warn(f"DRY RUN: would run: {' '.join(cmd)}")
        return
    if not confirm(f"This computer restarts in {delay} seconds. "
                   f"To cancel after confirming, run 'shutdown /a'.", "REBOOT"):
        warn("Reboot cancelled.")
        return
    subprocess.run(cmd, check=False)


# ---------- 5. Archive subfolders (RAR, verify, then delete) ----------

def archive_folder(item, rar):
    folder, archive = item
    rc = subprocess.run(
        [rar, "a", "-r", "-m5", "-y", "-idq", str(archive), str(folder)], check=False,
    ).returncode
    verified = rc == 0 and subprocess.run(
        [rar, "t", "-idq", str(archive)], check=False,
    ).returncode == 0
    if verified:
        try:
            shutil.rmtree(folder)
            say(f"OK {folder.name}: archived, verified, original removed.")
            return True
        except OSError as e:
            error(f"Archived {folder.name} but could not remove original: {e}")
            return False
    archive.unlink(missing_ok=True)
    error(f"FAILED {folder.name} (rar exit {rc}); original kept.")
    return False


def compress_folders():
    target = ask_dir("Folder whose subfolders will be archived: ")
    if not target:
        return
    rar = CFG["rar_path"]
    if not have_command(rar):
        error(f"Rar.exe not found at {rar}. Use the console Rar.exe, not WinRAR.exe (GUI).")
        return
    items = []
    for f in sorted(p for p in target.iterdir() if p.is_dir()):
        archive = target / f"{f.name}.rar"
        if archive.exists():
            warn(f"SKIP {f.name}: {archive.name} already exists")
            continue
        items.append((f, archive))
    run_actions(items,
                lambda it: f"{it[0]}  ->  {it[1].name}",
                lambda it: archive_folder(it, rar),
                "archive each subfolder, verify it, then DELETE the original folder",
                word="DELETE")


# ---------- 6 and 7. Audio to MP3 (verify, then delete source) ----------

def convert_to_mp3(sources, extra, label):
    ffmpeg, ffprobe = CFG["ffmpeg"], CFG["ffprobe"]
    if not have_command(ffmpeg):
        error("ffmpeg not found. Install it or set the path in config.json.")
        return
    tol = float(CFG["duration_tolerance_seconds"])
    items = []
    for src in sources:
        out = src.with_suffix(".mp3")
        if out.exists():
            warn(f"SKIP {src.name}: {out.name} already exists")
            continue
        items.append((src, out))

    def act(item):
        src, out = item
        rc = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-n",
             "-i", str(src), *extra, str(out)],
            check=False,
        ).returncode
        d_src = probe_duration(src, ffprobe)
        d_out = probe_duration(out, ffprobe) if rc == 0 and out.exists() else None
        if rc == 0 and d_src and d_out and abs(d_src - d_out) <= tol:
            src.unlink()
            say(f"OK {src.name} -> {out.name} (verified, source deleted)")
            return True
        out.unlink(missing_ok=True)
        error(f"FAILED {src.name} (ffmpeg exit {rc}; durations {d_src} / {d_out}); source kept.")
        return False

    run_actions(items, lambda it: f"{it[0]}  ->  {it[1].name}", act, label, word="DELETE")


def flac_to_mp3():
    root = ask_dir("Folder to search recursively for FLAC files: ")
    if not root:
        return
    sources = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".flac")
    convert_to_mp3(sources, FLAC_ARGS, "convert FLAC to 320k MP3, verify, then DELETE each FLAC")


def mka_to_mp3():
    folder = ask_dir("Folder containing .mka files (not recursive): ")
    if not folder:
        return
    sources = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".mka")
    convert_to_mp3(sources, MKA_ARGS, "convert MKA to 320k MP3, verify, then DELETE each MKA")


# ---------- 8 and 9. Folder renames ----------

def rename_folders(root, needle, replacement, label):
    # Deepest first, so a parent's path stays valid while its children are renamed.
    dirs = sorted((p for p in root.rglob("*") if p.is_dir() and needle in p.name),
                  key=lambda p: len(p.parts), reverse=True)
    items, planned = [], set()
    for d in dirs:
        new_name = d.name.replace(needle, replacement).strip()
        dst = d.with_name(new_name)
        if not new_name or dst.exists() or dst in planned:
            warn(f"SKIP '{d.name}': new name is empty or already exists")
            continue
        planned.add(dst)
        items.append((d, dst))
    run_actions(items, move_describe, move, label)


def remove_text_from_folders():
    root = ask_dir("Root folder to scan: ")
    if not root:
        return
    text = input(f"{AMBER}Text to remove from folder names: ")
    if not text:
        warn("No text given.")
        return
    rename_folders(root, text, "", f"remove '{text}' from folder names")


def underscores_to_spaces():
    root = ask_dir("Root folder to scan: ")
    if not root:
        return
    rename_folders(root, "_", " ", "replace underscores with spaces in folder names")


# ---------- 10. Organize files into folders named after them ----------

def organize_files():
    folder = ask_dir("Folder whose files will be organized: ")
    if not folder:
        return
    items = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        dst = folder / f.stem / f.name
        if dst.exists():
            warn(f"SKIP {f.name}: destination already exists")
            continue
        items.append((f, dst))
    run_actions(items, move_describe, move,
                "move each file into a subfolder named after it")


# ---------- menu ----------

ACTIONS = {
    "1": ("FIX MUSIC DUPLICATES", fix_music_duplicates),
    "3": ("SCAN DUPLICATES (report only)", scan_duplicates),
    "4": ("REBOOT (delayed, cancellable)", reboot),
    "5": ("ARCHIVE FOLDERS (RAR, verify, delete)", compress_folders),
    "6": ("FLAC TO MP3 (verify, delete)", flac_to_mp3),
    "7": ("MKA TO MP3 (verify, delete)", mka_to_mp3),
    "8": ("RENAME FOLDERS: REMOVE TEXT", remove_text_from_folders),
    "9": ("REMOVE UNDERSCORES FROM FOLDERS", underscores_to_spaces),
    "10": ("ORGANIZE FILES INTO FOLDERS", organize_files),
}


def main():
    global DRY_RUN
    while True:
        say("=== MEDIA CONSOLE: SAFE TOOLS ===", AMBER)
        for key, (name, _fn) in ACTIONS.items():
            say(f"{key}) {name}")
        say("D) Toggle dry run    Q) Quit")
        state = "ON (preview only)" if DRY_RUN else "OFF (changes apply after confirm)"
        warn(f"Dry run is {state}")
        choice = input("SELECT> ").strip().upper()
        if choice in ("", "Q"):
            break
        if choice == "D":
            DRY_RUN = not DRY_RUN
            continue
        if choice in ACTIONS:
            ACTIONS[choice][1]()
            pause()
        else:
            error(f"INVALID OPTION: {choice}")


if __name__ == "__main__":
    main()
