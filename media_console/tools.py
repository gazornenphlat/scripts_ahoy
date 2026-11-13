#!/usr/bin/env python3
"""Media console tools: every action from scripts_ahoy.py, rewritten with safety checks.

Safety model:
  * Dry run is ON at startup. Dry run only previews; nothing is changed.
  * With dry run OFF, every planned change is listed first and needs a typed word.
  * Source files are deleted only after the replacement is verified.
  * Credentials are never written to disk. Tdarr's key comes from an environment
    variable and the WinRM password is prompted for at run time.
"""

import ctypes
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from common import (AMBER, RESET, ConfigError, ask_dir, confirm, error, have_command,
                    load_config, pause, probe_duration, say, warn)

try:
    CFG = load_config()
except ConfigError as e:
    print(f"ERROR: {e}")
    print("Fix config.json and start again.")
    sys.exit(1)

DRY_RUN = True

AUDIO_EXTS = (".mp3", ".flac", ".m4a")
VIDEO_EXTS = (".mkv", ".mp4", ".avi")
PRIORITY = {".mkv": 1, ".mp4": 2, ".avi": 3}
FLAC_ARGS = ["-vn", "-map_metadata", "0", "-id3v2_version", "3", "-b:a", "320k"]
MKA_ARGS = ["-vn", "-ar", "44100", "-ac", "2", "-b:a", "320k"]
EPISODE_RE = re.compile(r"S\d{2}E\d{2}", re.IGNORECASE)


# ---------- pure helpers (no filesystem changes; these are what the tests cover) ----------

def find_episode_dupes(videos):
    """Group video paths by SxxEyy code and keep only codes with more than one file."""
    episodes = {}
    for p in videos:
        m = EPISODE_RE.search(Path(p).stem)
        if m:
            episodes.setdefault(m.group(0).upper(), []).append(Path(p))
    return {ep: fs for ep, fs in sorted(episodes.items()) if len(fs) > 1}


def rank_copies(paths):
    """Order copies best first: MKV, then MP4, then AVI, then anything else."""
    return sorted(paths, key=lambda p: PRIORITY.get(Path(p).suffix.lower(), 4))


def parse_ffprobe_video(text):
    """Read (height, bitrate) from ffprobe's JSON output. Returns (None, None) if unreadable."""
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return None, None
    streams = data.get("streams") or []
    height = streams[0].get("height") if streams and isinstance(streams[0], dict) else None
    bitrate = (data.get("format") or {}).get("bit_rate")
    try:
        height = int(height) if height is not None else None
    except (TypeError, ValueError):
        height = None
    try:
        bitrate = int(bitrate) if bitrate is not None else None
    except (TypeError, ValueError):
        bitrate = None
    return height, bitrate


def probe_video(path, ffprobe):
    """Return (height, bitrate) for a video file, or (None, None) if ffprobe fails."""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=height:format=bit_rate", "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    return parse_ffprobe_video(out)


def rank_by_quality(entries):
    """Order copies best first. entries are dicts with path, height and bitrate.

    Higher resolution wins, then higher bitrate, then container preference
    (MKV > MP4 > AVI). Copies with unknown quality sort after known ones,
    and are then ordered by container preference alone.
    """
    def key(e):
        height = e.get("height")
        bitrate = e.get("bitrate")
        container = PRIORITY.get(Path(e["path"]).suffix.lower(), 4)
        return (
            height is None,                       # unknown resolution last
            -(height or 0),
            bitrate is None,                      # unknown bitrate after known ones
            -(bitrate or 0),
            container,
            str(e["path"]),
        )
    return sorted(entries, key=key)


def plan_renames(root, needle, replacement):
    """Return (planned, skipped) for renaming folders under root.

    planned: list of (old_path, new_path), deepest folders first, so a parent's
             path is still valid when its children are renamed.
    skipped: list of (name, reason) for folders that cannot be renamed safely.
    """
    dirs = sorted((p for p in root.rglob("*") if p.is_dir() and needle in p.name),
                  key=lambda p: len(p.parts), reverse=True)
    planned, skipped, taken = [], [], set()
    for d in dirs:
        new_name = d.name.replace(needle, replacement).strip()
        if not new_name:
            # Check before with_name(): an empty name raises ValueError.
            skipped.append((d.name, "new name would be empty"))
            continue
        dst = d.with_name(new_name)
        if dst.exists() or dst in taken:
            skipped.append((d.name, f"'{new_name}' already exists"))
        else:
            taken.add(dst)
            planned.append((d, dst))
    return planned, skipped


def count_streams(path, ffprobe, kind):
    """Number of streams of kind 'a' (audio) or 'v' (video). 0 if unreadable or missing."""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", kind,
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def decodes_cleanly(path, ffmpeg):
    """Fully decode the file and report failure on any error.

    This catches truncated or corrupt output that still has the right duration
    on paper. It is slow on long files, so it runs only after the cheaper checks pass.
    """
    try:
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and not result.stderr.strip()


def verify_conversion(return_code, duration_src, duration_out, tolerance):
    """True only if ffmpeg succeeded and both durations are known and match within tolerance."""
    if return_code != 0 or not duration_src or not duration_out:
        # None or 0.0 both mean "unknown or empty": never delete on that.
        return False
    return abs(duration_src - duration_out) <= tolerance


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
    ffprobe = CFG["ffprobe"]
    if not folder.is_dir():
        error(f"Not found: {folder}")
        return
    if not have_command(ffprobe):
        warn("ffprobe not found; duplicates will be ranked by container only.")
    videos = sorted(
        (Path(r) / f for r, _dirs, files in os.walk(folder) for f in files
         if f.lower().endswith(VIDEO_EXTS)),
        key=lambda p: str(p).lower(),
    )
    dupes = find_episode_dupes(videos)

    now = datetime.now()
    report = Path(CFG["report_dir"]) / f"duplicate_scan_{now:%Y%m%d_%H%M%S}.txt"
    with open(report, "w", encoding="utf-8") as lf:
        lf.write(f"Duplicate scan {now:%Y-%m-%d %H:%M:%S}\n")
        lf.write(f"Directory: {folder}\n")
        lf.write(f"Video files found: {len(videos)}\n")
        lf.write("Ranking: resolution, then bitrate, then MKV > MP4 > AVI. "
                 "This scan deletes nothing.\n")
        lf.write("Copies with 'quality unknown' could not be probed by ffprobe.\n\n")
        for ep, fs in dupes.items():
            entries = []
            for p in fs:
                height, bitrate = probe_video(p, ffprobe)
                entries.append({"path": p, "height": height, "bitrate": bitrate})
            ranked = rank_by_quality(entries)
            lf.write(f"{ep}  ({len(fs)} copies)\n")
            for i, e in enumerate(ranked):
                label = "highest-ranked" if i == 0 else "review        "
                if e["height"] is None:
                    quality = "quality unknown"
                else:
                    kbps = f"{e['bitrate'] // 1000} kb/s" if e["bitrate"] else "bitrate unknown"
                    quality = f"{e['height']}p, {kbps}"
                lf.write(f"  {label}: {e['path']}  [{quality}]\n")
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
        # Cheap checks first; the slow decode only runs if they all pass.
        if (verify_conversion(rc, d_src, d_out, tol)
                and count_streams(out, ffprobe, "a") >= 1
                and decodes_cleanly(out, ffmpeg)):
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
    items, skipped = plan_renames(root, needle, replacement)
    for name, reason in skipped:
        warn(f"SKIP '{name}': {reason}")
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


# ---------- 2. Plex refresh (non-destructive) ----------

def plex_commands(scanner, sections):
    return [[scanner, "--scan", "--refresh", "--section", str(s)] for s in sections]


def plex_refresh():
    scanner = CFG["plex_scanner"]
    if not have_command(scanner):
        error(f"Plex Media Scanner not found at {scanner}.")
        return
    run_actions(
        plex_commands(scanner, CFG["plex_sections"]),
        lambda c: f"Plex refresh: section {c[-1]}",
        lambda c: subprocess.run(c, check=False).returncode == 0,
        "refresh the Plex library sections listed in config.json",
    )


# ---------- 11. Tdarr: re-encode failed items, verify, then delete source ----------

TDARR_BAD_DECISION = re.compile(r"transcode (error|cancelled)", re.IGNORECASE)


def select_tdarr_targets(records):
    """Keep Tdarr records whose last decision was a transcode error or cancellation."""
    if not isinstance(records, list):
        return []
    return [r for r in records
            if isinstance(r, dict)
            and TDARR_BAD_DECISION.search(str(r.get("TranscodeDecisionMaker") or ""))]


def unique_output_path(folder, stem, ext, exists=os.path.exists):
    """Return folder/stem+ext, or folder/stem (n)+ext, whichever is free."""
    candidate = Path(folder) / f"{stem}{ext}"
    n = 1
    while exists(str(candidate)):
        candidate = Path(folder) / f"{stem} ({n}){ext}"
        n += 1
    return candidate


def tdarr_request(payload):
    """POST to Tdarr's cruddb API. The key is read from an environment variable."""
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(CFG["tdarr_api_key_env"], "")
    if key:
        headers["x-api-key"] = key
    req = urllib.request.Request(
        f"{CFG['tdarr_url']}/api/v2/cruddb",
        data=json.dumps(payload).encode(), headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode() or "null")


def tdarr_cleanup():
    handbrake, ffprobe = CFG["handbrake_cli"], CFG["ffprobe"]
    if not have_command(handbrake):
        error(f"HandBrakeCLI not found at {handbrake}.")
        return
    if not os.environ.get(CFG["tdarr_api_key_env"]):
        warn(f"Environment variable {CFG['tdarr_api_key_env']} is not set; sending no API key.")
    try:
        records = tdarr_request({"data": {"collection": "FileJSONDB", "mode": "getAll"}})
    except Exception as e:  # nothing has been changed yet
        error(f"Could not query Tdarr at {CFG['tdarr_url']}: {e}")
        return

    finished, failed = Path(CFG["tdarr_finished_dir"]), Path(CFG["tdarr_failed_dir"])
    ext = CFG["tdarr_out_ext"]
    tol = float(CFG["duration_tolerance_seconds"])
    min_bytes = int(CFG["tdarr_min_output_bytes"])

    items, taken = [], set()
    for rec in select_tdarr_targets(records):
        raw = str(rec.get("file") or "")
        src = Path(raw)
        if not raw or not src.is_file():
            warn(f"SKIP missing on disk: {raw or '(no path)'}")
            continue
        out = unique_output_path(finished, src.stem, ext,
                                 exists=lambda p: p in taken or os.path.exists(p))
        taken.add(str(out))
        items.append({"src": src, "out": out, "doc_id": rec.get("_id")})

    def describe(it):
        return (f"encode {it['src']}  ->  {it['out']}   "
                f"(success: delete source and Tdarr record; failure: move source to {failed})")

    def act(it):
        src, out = it["src"], it["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        rc = subprocess.run(
            [handbrake, "-i", str(src), "-o", str(out), "-e", "x265", "-r", "30", "--pfr",
             "--all-audio", "-E", "copy", "--audio-fallback", "av_aac"],
            capture_output=True, text=True, check=False,
        ).returncode
        size_ok = out.is_file() and out.stat().st_size >= min_bytes
        d_src = probe_duration(src, ffprobe)
        d_out = probe_duration(out, ffprobe) if size_ok else None
        # Cheap checks first; the slow decode only runs if they all pass.
        if (size_ok and verify_conversion(rc, d_src, d_out, tol)
                and count_streams(out, ffprobe, "v") >= 1
                and decodes_cleanly(out, CFG["ffmpeg"])):
            src.unlink()
            say(f"OK {out.name} (verified, source deleted)")
            if it["doc_id"]:
                try:
                    tdarr_request({"data": {"collection": "FileJSONDB",
                                            "mode": "removeOne", "docID": it["doc_id"]}})
                except Exception as e:
                    warn(f"Source deleted, but the Tdarr record could not be removed: {e}")
            return True
        out.unlink(missing_ok=True)  # out was chosen to be a free name, so this is ours
        failed.mkdir(parents=True, exist_ok=True)
        dest = unique_output_path(failed, src.stem, src.suffix)
        try:
            shutil.move(str(src), str(dest))
            outcome = f"source moved to {dest}"
        except OSError as e:
            outcome = f"source kept (could not move: {e})"
        error(f"FAILED {src.name} (HandBrake exit {rc}, output "
              f"{'ok' if size_ok else 'missing or too small'}); {outcome}")
        return False

    run_actions(items, describe, act,
                "re-encode Tdarr error/cancelled items, verify, then DELETE each source",
                word="DELETE")


# ---------- 12. RAR wizard (creates archives; never deletes sources) ----------

RAR_MODES = {
    "1": "Each file in the folder, one archive per file (no subfolders)",
    "2": "Every file in the folder and subfolders, one archive per file, no paths",
    "3": "All files in the folder into one archive (no subfolders)",
    "4": "All files in the folder and subfolders into one archive",
    "5": "All files in the folder and subfolders into one archive, no paths",
}
BAD_NAME_CHARS = set('\\/:*?"<>|')


def rar_wizard_plan(folder, mode, name, stamp, rar):
    """Return (items, skipped) for a RAR mode 1-5.

    Each item is (cwd, command, archive_path, file_count). Commands run inside
    the folder with relative names, so archives never store absolute paths.
    Existing archives are skipped, never updated.
    """
    folder = Path(folder)
    items, skipped, planned = [], [], set()

    def add(archive, names, switches):
        if (folder / archive).exists() or archive in planned:
            skipped.append(f"{archive} already exists or is planned twice")
            return
        planned.add(archive)
        items.append((folder, [rar, "a", *switches, archive, *names],
                      folder / archive, len(names)))

    direct = sorted(p.name for p in folder.iterdir() if p.is_file())
    recursive = sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    if mode == 1:
        for f in direct:
            add(f"{Path(f).stem}.rar", [f], [])
    elif mode == 2:
        for rel in recursive:
            add(f"{Path(rel).stem}.rar", [rel], ["-ep"])
    elif mode == 3 and direct:
        add(f"{name}_{stamp}.rar", direct, [])
    elif mode == 4 and recursive:
        add(f"{name}.rar", recursive, [])
    elif mode == 5 and recursive:
        add(f"{name}_{stamp}.rar", recursive, ["-ep"])
    return items, skipped


def rar_act(item):
    cwd, command, archive, count = item
    rc = subprocess.run(command, cwd=str(cwd), check=False).returncode
    if rc == 0 and archive.is_file():
        say(f"OK {archive.name} ({count} file(s))")
        return True
    archive.unlink(missing_ok=True)  # planning confirmed this archive did not exist
    error(f"FAILED {archive.name} (rar exit {rc})")
    return False


def winrar_wizard():
    rar = CFG["rar_path"]
    if not have_command(rar):
        error(f"Rar.exe not found at {rar}.")
        return
    folder = ask_dir("Target folder: ")
    if not folder:
        return
    for key, text in RAR_MODES.items():
        say(f"{key}) {text}")
    mode = input(f"{AMBER}Mode (1-5): {RESET}").strip()
    if mode not in RAR_MODES:
        warn("No valid mode selected.")
        return
    name = "archive"
    if mode in ("3", "4", "5"):
        name = input(f"{AMBER}Base name for the archive: {RESET}").strip() or "archive"
        if any(c in BAD_NAME_CHARS for c in name):
            error("Name must not contain \\ / : * ? \" < > |")
            return
    stamp = datetime.now().strftime("%m-%d-%Y-%H%M%S")
    items, skipped = rar_wizard_plan(folder, int(mode), name, stamp, rar)
    for s in skipped:
        warn(f"SKIP {s}")
    run_actions(items,
                lambda it: f"{it[2].name}  <-  {it[3]} file(s) from {it[0]}",
                rar_act,
                f"create {len(items)} archive(s); no source files are deleted",
                word="APPLY")


# ---------- 13. Reset recent items ----------

def recent_item_files(appdata):
    base = Path(appdata) / "Microsoft" / "Windows" / "Recent"
    found = []
    for sub in (base, base / "AutomaticDestinations", base / "CustomDestinations"):
        if sub.is_dir():
            found.extend(p for p in sorted(sub.iterdir()) if p.is_file())
    return found


def delete_file(path):
    try:
        path.unlink()
        return True
    except OSError as e:
        error(f"Could not remove {path}: {e}")
        return False


def reset_recent():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        error("APPDATA is not set; this action only works on Windows.")
        return
    run_actions(recent_item_files(appdata), lambda p: f"delete {p}", delete_file,
                "delete Windows recent-item and jump-list files", word="DELETE")


# ---------- 14. Explorer context menu entries (registry; needs administrator) ----------

CONTEXT_HANDLERS = [
    ("{C2FBB630-2971-11D1-A18C-00C04FD75D13}", "Copy To"),
    ("{C2FBB631-2971-11D1-A18C-00C04FD75D13}", "Move To"),
]


def context_menu_commands():
    base = r"HKEY_CLASSES_ROOT\AllFilesystemObjects\shellex\ContextMenuHandlers"
    return [["reg", "add", f"{base}\\{clsid}", "/ve", "/d", label, "/f"]
            for clsid, label in CONTEXT_HANDLERS]


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):  # not Windows, or the check is unavailable
        return False


def context_menu_register():
    if not is_admin():
        warn("Not running as administrator: the registry changes will fail. "
             "Restart the console as administrator to apply them.")
    run_actions(context_menu_commands(), lambda c: " ".join(c),
                lambda c: subprocess.run(c, check=False).returncode == 0,
                "add 'Copy To' and 'Move To' to the Explorer context menu (registry)")


# ---------- 15. Remote reboot over WinRM ----------
# Saved file holds host and username only. Passwords are prompted for at reboot time.

def load_saved_computers(path):
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"cannot read {path}: {e}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def save_computers(path, computers):
    Path(path).write_text(json.dumps(computers, indent=4), encoding="utf-8")


def validate_computer(name, host, username):
    """Return a problem description, or None if the entry is acceptable."""
    if not name.strip():
        return "name must not be empty"
    if not host.strip():
        return "host must not be empty"
    if not username.strip():
        return "username must not be empty"
    if any(c in host for c in " /\\"):
        return "host must not contain spaces or slashes"
    return None


def winrm_shutdown(host, username, password):
    import winrm  # imported here so the other tools work without pywinrm installed
    scheme = "https" if CFG["winrm_use_https"] else "http"
    session = winrm.Session(f"{scheme}://{host}:{CFG['winrm_port']}/wsman",
                            auth=(username, password), transport="ntlm")
    result = session.run_cmd("shutdown /r /t 0")
    if result.status_code != 0:
        detail = result.std_err.decode(errors="replace").strip()
        raise RuntimeError(detail or f"exit code {result.status_code}")


def winrm_reboot():
    path = CFG["windows_computers_file"]
    try:
        computers = load_saved_computers(path)
    except ValueError as e:
        error(str(e))
        return
    say("--- Saved Windows computers ---", AMBER)
    names = list(computers)
    for i, name in enumerate(names, 1):
        c = computers[name]
        say(f"{i}) {name}  ({c.get('username')}@{c.get('host')})")
    say("A) Add a computer    Enter) cancel")
    choice = input(f"{AMBER}Select: {RESET}").strip().upper()

    if choice == "A":
        name = input("Friendly name: ").strip()
        host = input("Host or IP: ").strip()
        user = input("Username (e.g. Administrator or DOMAIN\\User): ").strip()
        problem = validate_computer(name, host, user)
        if problem:
            error(problem)
        elif name in computers:
            error(f"'{name}' already exists")
        elif DRY_RUN:
            warn(f"DRY RUN: would save '{name}' to {path}")
        else:
            computers[name] = {"host": host, "username": user}
            save_computers(path, computers)
            say(f"Saved '{name}'. No password was stored.")
        return

    if not choice.isdigit() or not 1 <= int(choice) <= len(names):
        return
    name = names[int(choice) - 1]
    comp = computers[name]
    host, user = comp.get("host", ""), comp.get("username", "")

    def describe(it):
        return f"REBOOT '{it[0]}' ({user}@{host}:{CFG['winrm_port']}) via WinRM"

    def act(it):
        password = getpass.getpass(f"Password for {user}@{host}: ")
        try:
            winrm_shutdown(host, user, password)
            say(f"Reboot signal sent to {host}.")
            return True
        except Exception as e:
            error(f"FAILED {host}: {e}")
            return False

    run_actions([(name, comp)], describe, act,
                f"reboot Windows host '{name}' ({host}) now", word="REBOOT")


# ---------- menu ----------

ACTIONS = {
    "1": ("FIX MUSIC DUPLICATES", fix_music_duplicates),
    "2": ("PLEX REFRESH (non-destructive)", plex_refresh),
    "3": ("SCAN DUPLICATES (report only)", scan_duplicates),
    "4": ("REBOOT (delayed, cancellable)", reboot),
    "5": ("ARCHIVE FOLDERS (RAR, verify, delete)", compress_folders),
    "6": ("FLAC TO MP3 (verify, delete)", flac_to_mp3),
    "7": ("MKA TO MP3 (verify, delete)", mka_to_mp3),
    "8": ("RENAME FOLDERS: REMOVE TEXT", remove_text_from_folders),
    "9": ("REMOVE UNDERSCORES FROM FOLDERS", underscores_to_spaces),
    "10": ("ORGANIZE FILES INTO FOLDERS", organize_files),
    "11": ("TDARR CLEANUP (re-encode, verify, delete)", tdarr_cleanup),
    "12": ("WINRAR WIZARD (creates archives only)", winrar_wizard),
    "13": ("RESET RECENT ITEMS (deletes history)", reset_recent),
    "14": ("ADD COPY/MOVE TO CONTEXT MENU (admin)", context_menu_register),
    "15": ("WINDOWS REMOTE REBOOT (WinRM)", winrm_reboot),
}


def main():
    global DRY_RUN
    while True:
        say("=== MEDIA CONSOLE ===", AMBER)
        for key in sorted(ACTIONS, key=int):
            name, _fn = ACTIONS[key]
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
