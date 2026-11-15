#!/usr/bin/env python3
"""MEDIA_N - Hacker Aesthetic Media Console.

LEGACY - SUPERSEDED BY media_console. Kept for reference only.
Do not use it for real work: its actions delete source files
without the verification the rewrite performs, and its reboot
is immediate. Running this file requires typing LEGACY at startup.

Combined, menu-driven media utility.

Design reference: design.md (Hacker Aesthetic CRT/CLI)
  - Black background (#050505) with phosphor green (#2CFF56) text
  - VT323 monospace type, amber accents (#FFB200), red error state (#FF3333)
  - ASCII art, command-line interface, retro CRT feel

Each action creates a helper script and runs it in a new window.
"""

import os
import subprocess
import sys
import tempfile

FG_GREEN = "\033[38;2;44;255;87m"   # #2CFF56
FG_AMBER = "\033[38;2;255;178;0m"    # #FFB200
FG_RED = "\033[38;2;255;51;51m"      # #FF3333
FG_WHITE = "\033[38;2;255;255;255m"  # #FFFFFF
BG_BLACK = "\033[48;2;5;5;5m"        # #050505
RESET = "\033[0m"

GREEN = FG_GREEN
AMBER = FG_AMBER
RED = FG_RED
WHITE = FG_WHITE
BLACK_BG = BG_BLACK

BANNER_SUBTITLE = "SCRIPTS AHOY!"
MENU_TITLE = "HACKER AESTHETIC MEDIA CONSOLE"
MENU_SUBTITLE = "COMBINED OPERATIONS MENU"

ASCII_LOGO = [
    "  +" + "-" * 40 + "+  ",
    "  |" + " " * 40 + "|  ",
    "  |" + (" " + BANNER_SUBTITLE).ljust(40) + "|",
    "  |" + " " * 40 + "|  ",
    "  +" + "-" * 40 + "+  ",
]

PLEX_SCANNER = r"d:\Plex\Plex Media Server\Plex Media Scanner.exe"
PLEX_SECTIONS = [67, 3, 60, 71, 73, 74, 75, 5]


def build_folderbat_content() -> str:
    return "\r\n".join([
        "@echo off",
        "setlocal enabledelayedexpansion",
        "for %%f in (*.mp3 *.flac *.m4a) do (",
        '    set "randfolder=folder_!random!_!time:~6,2!!time:~3,2!!time:~0,2!"',
        '    mkdir "!randfolder!"',
        '    move "%%f" "!randfolder!"',
        '    echo Moved "%%f" into "!randfolder!"',
        ")",
        "echo All mp3 and flac files have been moved into random folders.",
        "pause",
        'del "%%~f0"',
    ]) + "\r\n"


def build_plex_batch_content() -> str:
    lines = ["@echo off"]
    lines += [f'"{PLEX_SCANNER}" --scan --refresh --section {s}' for s in PLEX_SECTIONS]
    lines.append("echo Plex refresh complete.")
    lines.append("pause")
    return "\r\n".join(lines) + "\r\n"


def build_reboot_batch_content() -> str:
    return "@echo off\r\necho REBOOTING SYSTEM NOW...\r\nshutdown /r /f /t 0\r\n"


def build_dupes_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, re
from datetime import datetime

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

PRIORITY = {".mkv": 1, ".mp4": 2, ".avi": 3}

def main():
    print(f"{G}=== SCAN DUPLICATES ==={R}")
    directory = "N:\\TV Shows\\D\\"
    if not os.path.isdir(directory):
        print(f"{R}Error: Directory '{directory}' not found!{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return
    video_files = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith((".mkv", ".mp4", ".avi")):
                video_files.append(os.path.join(root, f))
    video_files.sort(key=str.lower)
    log_file = "N:/duplicate_scan_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(log_file, "w") as lf:
        lf.write("Duplicate Video File Scan Results\n")
        lf.write("Scan started: %s\n" % datetime.now())
        lf.write("Directory: %s\n" % directory)
        lf.write("Priority: MKV > MP4 > AVI\n")
        lf.write("---------------------------------------\n")
        lf.write("Listing all video files found:\n")
        count = 0
        for p in video_files:
            count += 1
            lf.write("FILE %d: %s\n" % (count, p))
        lf.write("Found %d video files\n" % count)
        lf.write("---------------------------------------\n")
        lf.write("Processing duplicates:\n")
        episodes = {}
        for p in video_files:
            m = re.search(r"S\d{2}E\d{2}", os.path.splitext(os.path.basename(p))[0])
            if m:
                episodes.setdefault(m.group(0), []).append(p)
        for ep, files in sorted(episodes.items()):
            if len(files) > 1:
                files_sorted = sorted(files, key=lambda p: PRIORITY.get(os.path.splitext(p)[1].lower(), 4))
                keep = files_sorted[0]
                lf.write("KEEP: %s (Episode %s)\n" % (keep, ep))
                for f in files_sorted[1:]:
                    lf.write("DELETE: %s (Episode %s)\n" % (f, ep))
    print(f"{G}Scan complete! Check {log_file} for results.{R}")
    print(f"{G}Found {count} total video files.{R}")
    input(f"\n{A}Press Enter to close...{R}")

if __name__ == "__main__":
    main()
'''


def build_organize_files_py_content(target_dir: str) -> str:
    return f'''#!/usr/bin/env python3
import os, shutil

G = "\\033[38;2;44;255;87m"
A = "\\033[38;2;255;178;0m"
R = "\\033[0m"

def main():
    print(f"{{G}}=== ORGANIZE FILES ==={{R}}")
    target_dir = {repr(target_dir)}
    if not os.path.isdir(target_dir):
        print(f'{{R}}Error: "{{target_dir}}" is not a directory or does not exist.{{R}}')
        input(f"\\n{{A}}Press Enter to close...{{R}}")
        return 1

    moved = 0
    skipped = 0

    for entry in sorted(os.listdir(target_dir)):
        src = os.path.join(target_dir, entry)
        if not os.path.isfile(src):
            continue
        basename = os.path.splitext(entry)[0]
        dest_dir = os.path.join(target_dir, basename)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, entry)
        if os.path.exists(dest):
            print(f"Skipped (already exists): {{dest}}")
            skipped += 1
        else:
            shutil.move(src, dest)
            print(f"Moved: {{entry}}  ->  {{basename}}")
            moved += 1

    print(f"\\n{{G}}Done. Files moved: {{moved}}  |  Skipped: {{skipped}}{{R}}")
    input(f"\\n{{A}}Press Enter to close...{{R}}")
    return 0

if __name__ == "__main__":
    main()
'''


def build_flac_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, shutil, subprocess

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def find_flacs(root: str) -> list:
    results = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.lower().endswith(".flac"):
                results.append(os.path.join(dirpath, f))
    return sorted(results)

def main() -> int:
    print(f"{G}=== FLAC TO MP3 CONVERTER ==={R}")
    if shutil.which("ffmpeg") is None:
        print(f"{R}ERROR: FFmpeg is not installed or not in PATH{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    folder = ""
    while not folder or not os.path.isdir(folder):
        folder = input(f"{A}Enter the folder path to search for FLAC files: {R}").strip()
        if folder and os.path.isdir(folder):
            break
        print(f"{R}Folder does not exist. Please try again.{R}")

    print(f"\nSearching for FLAC files in {folder}...")
    flacs = find_flacs(folder)
    if not flacs:
        print(f"{R}No FLAC files found.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 0

    print(f"{G}Found {len(flacs)} FLAC files to convert{R}\n")
    for current, f in enumerate(flacs, 1):
        print(f'Converting [{current}/{len(flacs)}]: "{os.path.basename(f)}"')
        output = os.path.splitext(f)[0] + ".mp3"
        proc = subprocess.run(
            [
                "ffmpeg", "-i", f, "-b:a", "320k", "-map_metadata", "0",
                "-id3v2_version", "3", output, "-y", "-hide_banner", "-loglevel", "error",
            ],
            check=False,
        )
        if proc.returncode == 0:
            print("Conversion successful, deleting original FLAC file")
            os.remove(f)
        else:
            print(f"{R}Error converting - keeping original file{R}")
            if os.path.exists(output):
                os.remove(output)

    print(f"\n{G}Conversion complete!{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_mkaconvert_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, shutil, subprocess

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main() -> int:
    print(f"{G}=== MKA TO MP3 CONVERTER ==={R}")
    if shutil.which("ffmpeg") is None:
        print(f"{R}ERROR: FFmpeg is not installed or not in PATH{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    source_folder = ""
    while not source_folder or not os.path.isdir(source_folder):
        source_folder = input(f"{A}Enter the folder path containing .mka files: {R}").strip()
        if source_folder and os.path.isdir(source_folder):
            break
        print(f"{R}Folder does not exist. Please try again.{R}")

    mka_files = sorted(
        f for f in os.listdir(source_folder)
        if f.lower().endswith(".mka") and os.path.isfile(os.path.join(source_folder, f))
    )

    if len(mka_files) == 0:
        print(f"{R}No .mka files found in {source_folder}{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 0

    print(f"{G}Found {len(mka_files)} .mka file(s) to convert{R}\n")
    converted = 0
    for current, f in enumerate(mka_files, 1):
        base = os.path.splitext(os.path.basename(f))[0]
        print(f"[{current}/{len(mka_files)}] Converting: {os.path.basename(f)}")
        src = os.path.join(source_folder, f)
        out = os.path.join(source_folder, base + ".mp3")
        proc = subprocess.run(
            ["ffmpeg", "-i", src, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "320k", out, "-y"],
            check=False,
        )
        if proc.returncode == 0:
            print(f"SUCCESS: Created {base}.mp3")
            os.remove(src)
            converted += 1
        else:
            print(f"{R}ERROR: Failed to convert {os.path.basename(f)}{R}")

    print(f"\n{G}Conversion complete! Converted: {converted} / {len(mka_files)}{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_rename_folders_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main() -> None:
    print(f"{G}=== RENAME FOLDERS ==={R}")
    root_directory = input(f"{A}Enter the path of the directory to scan (leave blank for current directory): {R}").strip()
    if not root_directory:
        root_directory = "."

    if not os.path.exists(root_directory):
        print(f"{R}The specified directory does not exist.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return

    search_text = input(f"{A}Enter the text to look for (leave blank to cancel): {R}").strip()
    if not search_text:
        print(f"{R}No text provided, skipping.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return

    renamed = False
    for dirpath, dirnames, filenames in os.walk(root_directory, topdown=False):
        for dirname in dirnames:
            if search_text in dirname:
                old_path = os.path.join(dirpath, dirname)
                new_dirname = dirname.replace(search_text, "").strip()
                new_path = os.path.join(dirpath, new_dirname)
                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed:\n  '{dirname}'\n-> '{new_dirname}'\n")
                    renamed = True
                except Exception as e:
                    print(f"{R}Error renaming '{dirname}': {e}{R}")

    if renamed:
        print(f"{G}Done!{R}")
    else:
        print(f"{R}No folders found containing the text.{R}")
    input(f"\n{A}Press Enter to close...{R}")

if __name__ == "__main__":
    main()
'''


def build_rename_folders_remove_underscores_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os
from pathlib import Path

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main():
    print(f"{G}=== REMOVE UNDERSCORES FROM FOLDERS ==={R}")
    target_dir = input(f"{A}Enter the path of the directory to scan: {R}").strip()
    if not target_dir:
        target_dir = "."

    path = Path(target_dir)
    if not path.is_dir():
        print(f"{R}Error: '{target_dir}' is not a valid directory.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return

    folders = sorted(
        [p for p in path.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    )

    renamed_count = 0
    for folder in folders:
        if "_" in folder.name:
            new_name = folder.name.replace("_", " ")
            new_path = folder.parent / new_name

            try:
                folder.rename(new_path)
                print(f"Renamed: '{folder.name}' -> '{new_name}'")
                renamed_count += 1
            except Exception as e:
                print(f"{R}Failed to rename '{folder.name}': {e}{R}")

    print(f"\n{G}Done! Total folders renamed: {renamed_count}{R}")
    input(f"\n{A}Press Enter to close...{R}")

if __name__ == "__main__":
    main()
'''


def build_encrypt_folders_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, subprocess, shutil

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main():
    print(f"{G}=== ENCRYPT / COMPRESS FOLDERS (MAX RAR5) ==={R}")
    print("-" * 45)

    winrar_path = r"C:\Program Files\WinRAR\WinRAR.exe"
    rar_cmd = winrar_path if os.path.exists(winrar_path) else "rar"

    target_dir = input(f"{A}Enter the path to the target directory: {R}").strip()
    if not os.path.isdir(target_dir):
        print(f"{R}The directory '{target_dir}' does not exist or is invalid.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    if not os.path.exists(winrar_path) and shutil.which("rar") is None:
        print(f"{R}WinRAR not found at '{winrar_path}' or in PATH.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    folders = [os.path.join(target_dir, d) for d in sorted(os.listdir(target_dir)) if os.path.isdir(os.path.join(target_dir, d))]
    if not folders:
        print(f"{A}No folders found in {target_dir}.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 0

    print(f"\n{G}Found {len(folders)} subfolder(s) to process.{R}\n")

    for folder_path in folders:
        folder_name = os.path.basename(folder_path)
        archive_name = f"{folder_path}.rar"
        print(f"Processing: {folder_name}...")

        arguments = [rar_cmd, "a", "-y", "-m5", "-afrar", archive_name, f"{folder_path}\\*"]
        proc = subprocess.run(arguments, capture_output=True, text=True, check=False)

        if proc.returncode == 0:
            print(f"{G}Successfully archived: {folder_name}. Removing original folder...{R}")
            try:
                shutil.rmtree(folder_path)
            except Exception as e:
                print(f"{R}Error removing folder {folder_name}: {e}{R}")
        else:
            print(f"{A}Compression failed or returned warnings for {folder_name} (Exit Code: {proc.returncode}). Folder NOT deleted.{R}")
        print()

    print(f"{G}All tasks completed!{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    main()
'''


def build_tdarr_cleanup_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, sys, json, re, subprocess, urllib.request
from datetime import datetime

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

DEFAULT_TDARR_URL = "http://10.120.1.147:8265"
DEFAULT_API_KEY = ""
DEFAULT_HANDBRAKE_CLI = r"C:\Program Files\HandBrake\HandBrakeCLI.exe"
DEFAULT_FINISHED_DIR = r"N:\aaa_finished"
DEFAULT_FAILED_DIR = r"N:\aaa_failed"
DEFAULT_OUT_EXT = ".mkv"

def log(msg: str, log_file: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    with open(log_file, "a") as f:
        f.write(line + "\n")

def query_tdarr(tdarr_url: str, api_key: str):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    body = json.dumps({"data": {"collection": "FileJSONDB", "mode": "getAll"}}).encode()
    req = urllib.request.Request(
        f"{tdarr_url}/api/v2/cruddb", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def main() -> None:
    print(f"{G}=== TDARR CLEANUP & RETRY ==={R}")
    finished_dir = DEFAULT_FINISHED_DIR
    failed_dir = DEFAULT_FAILED_DIR
    out_ext = DEFAULT_OUT_EXT
    log_file = os.path.join(finished_dir, "tdarr-handbrake.log")

    os.makedirs(finished_dir, exist_ok=True)
    os.makedirs(failed_dir, exist_ok=True)

    if not os.path.exists(DEFAULT_HANDBRAKE_CLI):
        print(f"{R}HandBrakeCLI not found at {DEFAULT_HANDBRAKE_CLI}{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return

    log(f"Querying Tdarr at {DEFAULT_TDARR_URL} ...", log_file)
    try:
        all_items = query_tdarr(DEFAULT_TDARR_URL, DEFAULT_API_KEY)
    except Exception as e:
        log(f"Failed to query Tdarr: {e}", log_file)
        input(f"\n{A}Press Enter to close...{R}")
        return

    targets = []
    for item in all_items if isinstance(all_items, list) else []:
        decision = str(item.get("TranscodeDecisionMaker") or "")
        if re.search(r"(?i)transcode (error|cancelled)", decision):
            targets.append(item)

    log(f"Found {len(targets)} Error/Cancelled item(s).", log_file)
    ok, bad = 0, 0

    for item in targets:
        src = item.get("file") or ""
        if not src or not os.path.exists(src):
            log(f"SKIP (missing on disk): {src}", log_file)
            continue

        name = os.path.splitext(os.path.basename(src))[0]
        out = os.path.join(finished_dir, name + out_ext)
        i = 1
        while os.path.exists(out):
            out = os.path.join(finished_dir, f"{name} ({i}){out_ext}")
            i += 1

        log(f"ENCODE: {src}", log_file)
        proc = subprocess.run(
            [
                DEFAULT_HANDBRAKE_CLI, "-i", src, "-o", out,
                "-e", "x265", "-r", "30", "--pfr", "--all-audio",
                "-E", "copy", "--audio-fallback", "av_aac",
            ],
            capture_output=True, text=True,
        )
        if proc.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1024 * 1024:
            os.remove(src)
            log(f"OK: {out} (source deleted)", log_file)
            doc_id = item.get("_id") or src
            try:
                del_body = json.dumps(
                    {"data": {"collection": "FileJSONDB", "mode": "removeOne", "docID": doc_id}}
                ).encode()
                req = urllib.request.Request(
                    f"{DEFAULT_TDARR_URL}/api/v2/cruddb",
                    data=del_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=30).read()
                log(f"Removed from Tdarr: {doc_id}", log_file)
            except Exception:
                pass
            ok += 1
        else:
            if os.path.exists(out):
                os.remove(out)
            dest = os.path.join(failed_dir, os.path.basename(src))
            os.rename(src, dest)
            log(f"FAILED: moved source to {dest}", log_file)
            bad += 1

    log(f"Done. Success: {ok}  Failed: {bad}", log_file)
    input(f"\n{A}Press Enter to close...{R}")

if __name__ == "__main__":
    main()
'''


def build_winrar_wizard_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, subprocess
from datetime import datetime

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main():
    print(f"{G}=== INTERACTIVE WINRAR WIZARD ==={R}")
    print("-" * 40)
    
    dir_path = input(f"{A}Enter directory: {R}").strip()
    if not os.path.isdir(dir_path):
        print(f"{R}Error: Directory '{dir_path}' not found!{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    winrar_path = r"C:\Program Files\WinRAR\WinRAR.exe"
    rar_cmd = winrar_path if os.path.exists(winrar_path) else "rar"
    os.chdir(dir_path)

    now = datetime.now()
    hr = f"{now.hour:02d}"
    today = f"{now.month:02d}-{now.day:02d}-{now.year}-{hr}{now.minute:02d}{now.second:02d}{now.microsecond // 10000:02d}"

    print(f"\nTarget Folder:\n{dir_path}\n")
    print(f"{G}1.{R} Compress files in dir individually (no subdirs)")
    print(f"{G}2.{R} Compress all files in dir and subdirs individually - no paths")
    print(f"{G}3.{R} Compress all files in dir into a single archive (no subdirs)")
    print(f"{G}4.{R} Compress all files in dir and subdirs into a single archive")
    print(f"{G}5.{R} Compress all files in dir and subdirs into a single archive - no paths")
    print(f"{G}6.{R} Exit\n")

    choice = input(f"{A}Enter your selection (1-6): {R}").strip()
    print()

    if choice == "1":
        for f in os.listdir(dir_path):
            if os.path.isfile(f):
                base = os.path.splitext(f)[0]
                subprocess.run([rar_cmd, "a", base, f], check=False)
    elif choice == "2":
        for root, dirs, files in os.walk(dir_path):
            for f in files:
                full_path = os.path.join(root, f)
                base = os.path.splitext(f)[0]
                subprocess.run([rar_cmd, "a", "-ep", base, full_path], check=False)
    elif choice == "3":
        name = input(f"{A}Enter base filename for archive: {R}").strip()
        subprocess.run([rar_cmd, "a", f"{name}_{today}"], check=False)
    elif choice == "4":
        name = input(f"{A}Enter base filename for archive: {R}").strip()
        subprocess.run([rar_cmd, "a", "-r", name], check=False)
    elif choice == "5":
        name = input(f"{A}Enter base filename for archive: {R}").strip()
        subprocess.run([rar_cmd, "a", "-r", "-ep", f"{name}_{today}"], check=False)
    else:
        print("No selection made - script exited")

    print(f"\n{G}Task Completed{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    main()
'''


def build_reset_recent_py_content() -> str:
    return r'''#!/usr/bin/env python3
import os, glob

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def main():
    print(f"{G}=== RESET AND CLEAR RECENT ITEMS ==={R}")
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        print(f"{R}Error: APPDATA environment variable not found.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    paths = [
        os.path.join(appdata, r"Microsoft\Windows\Recent\*"),
        os.path.join(appdata, r"Microsoft\Windows\Recent\AutomaticDestinations\*"),
        os.path.join(appdata, r"Microsoft\Windows\Recent\CustomDestinations\*")
    ]

    for p_pattern in paths:
        for f in glob.glob(p_pattern):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                    print(f"Removed: {f}")
            except Exception as e:
                print(f"Could not remove {f}: {e}")

    print(f"\n{G}Recent items and frequent places cleared successfully.{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    main()
'''


def build_context_menu_reg_py_content() -> str:
    return r'''#!/usr/bin/env python3
import subprocess, sys, ctypes

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    print(f"{G}=== CONTEXT MENU REGISTRATION ==={R}")
    if not is_admin():
        print(f"{R}ERROR: Administrative privileges required!{R}")
        print(f"{A}Please run this console as Administrator.{R}")
        input(f"\n{A}Press Enter to close...{R}")
        return 1

    reg_commands = [
        r'reg add "HKEY_CLASSES_ROOT\AllFilesystemObjects\shellex\ContextMenuHandlers\{C2FBB630-2971-11D1-A18C-00C04FD75D13}" /ve /d "Copy To" /f',
        r'reg add "HKEY_CLASSES_ROOT\AllFilesystemObjects\shellex\ContextMenuHandlers\{C2FBB631-2971-11D1-A18C-00C04FD75D13}" /ve /d "Move To" /f'
    ]

    for cmd in reg_commands:
        res = subprocess.run(cmd, shell=True)
        if res.returncode == 0:
            print(f"{G}SUCCESS: Added handler{R}")
        else:
            print(f"{R}FAILED: {cmd}{R}")

    print(f"\n{G}Context menu entries added successfully.{R}")
    input(f"\n{A}Press Enter to close...{R}")
    return 0

if __name__ == "__main__":
    main()
'''


def build_winrm_reboot_py_content() -> str:
    return r'''#!/usr/bin/env python3
import getpass
import json
import os
import sys
import winrm

G = "\033[38;2;44;255;87m"
A = "\033[38;2;255;178;0m"
R = "\033[0m"

CONFIG_FILE = "windows_computers.json"

def load_saved_computers():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_computers(computers):
    with open(CONFIG_FILE, "w") as f:
        json.dump(computers, f, indent=4)

def add_computer(computers):
    print(f"\n{G}--- Add a New Windows Computer ---{R}")
    name = input(f"{A}Enter a friendly name/alias (e.g., 'Office PC'): {R}").strip()
    if not name:
        print(f"{R}[-] Name cannot be empty.{R}")
        return

    host = input(f"{A}Enter IP address or hostname: {R}").strip()
    user = input(f"{A}Enter Administrator username (e.g., Administrator or DOMAIN\\User): {R}").strip()
    
    computers[name] = {
        "host": host,
        "username": user
    }
    
    save_computers(computers)
    print(f"{G}[✓] Windows computer '{name}' saved successfully!{R}")

def reboot_windows_remote(host, username, password):
    print(f"\n{A}[*] Connecting to Windows host {host} via WinRM...{R}")
    try:
        session = winrm.Session(f'http://{host}:5985/wsman', auth=(username, password), transport='ntlm')
        command = "shutdown /r /t 0"
        
        print(f"{A}[*] Executing reboot command on {host}...{R}")
        result = session.run_cmd(command)

        if result.status_code == 0:
            print(f"{G}[✓] Reboot signal successfully sent to Windows host {host}.{R}")
        else:
            err_msg = result.std_err.decode().strip()
            print(f"{R}[-] Failed to reboot {host}: {err_msg}{R}")

    except Exception as e:
        print(f"{R}[-] Connection or execution error on {host}: {e}{R}")

def select_and_reboot(computers):
    if not computers:
        print(f"\n{R}[-] No saved Windows computers found. Please add one first.{R}")
        return

    print(f"\n{G}--- Saved Windows Computers ---{R}")
    names = list(computers.keys())
    for idx, name in enumerate(names, 1):
        info = computers[name]
        print(f"{G}[{idx}]{R} {name} ({info['username']}@{info['host']})")

    choice = input(f"\n{A}Select a number to reboot (or 'c' to cancel): {R}").strip()
    if choice.lower() == 'c':
        return

    try:
        index = int(choice) - 1
        if index < 0 or index >= len(names):
            print(f"{R}[-] Invalid selection.{R}")
            return
        
        selected_name = names[index]
        comp = computers[selected_name]
        
        pwd = getpass.getpass(f"Enter password for {comp['username']}@{comp['host']}: ")

        confirm = input(f"{A}⚠️ Are you sure you want to REBOOT Windows host '{selected_name}' ({comp['host']})? (y/N): {R}").strip().lower()
        if confirm == 'y':
            reboot_windows_remote(
                host=comp['host'],
                username=comp['username'],
                password=pwd
            )
        else:
            print("Reboot cancelled.")

    except ValueError:
        print(f"{R}[-] Please enter a valid number.{R}")

def main():
    computers = load_saved_computers()
    
    while True:
        print(f"\n{G}=== Windows Remote Reboot Manager ==={R}")
        print(f"{G}1.{R} Save a new Windows computer")
        print(f"{G}2.{R} Pick a saved computer to reboot")
        print(f"{G}3.{R} Back to Main Menu")
        
        choice = input(f"{A}Choose an option (1-3): {R}").strip()
        
        if choice == "1":
            add_computer(computers)
        elif choice == "2":
            select_and_reboot(computers)
        elif choice == "3":
            break
        else:
            print(f"{R}[-] Invalid choice. Please choose 1, 2, or 3.{R}")
        input(f"\n{A}Press Enter to continue...{R}")

if __name__ == "__main__":
    main()
'''


def say(text: str = "", color: str = GREEN) -> None:
    print(f"{color}{text}{RESET}")


def show_banner() -> None:
    print(f"{BLACK_BG}{GREEN}")
    for line in ASCII_LOGO:
        print(f"{GREEN}{line.rstrip()}{RESET}")


def create_and_run(script_path: str, content: str, runner: str = "cmd") -> None:
    with open(script_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(content)
    
    if runner == "python":
        subprocess.run(["cmd.exe", "/c", "start", "cmd.exe", "/k", sys.executable, script_path], check=False)
    else:
        subprocess.run(["cmd.exe", "/c", "start", "cmd.exe", "/k", script_path], check=False)


def action_organize_media() -> None:
    root = input(f"{AMBER}TARGET ROOT DIRECTORY: ").strip()
    if not root:
        say("NO TARGET DIRECTORY PROVIDED", RED)
        return
    if not os.path.isdir(root):
        say(f"ERROR: {root} IS NOT A DIRECTORY", RED)
        return
    for entry in sorted(os.listdir(root)):
        p = os.path.join(root, entry)
        if not os.path.isdir(p):
            continue
        script = os.path.join(p, "folder.bat")
        create_and_run(script, build_folderbat_content(), runner="cmd")
    say("ORGANIZE MEDIA SPAWNED", GREEN)


def action_plex_refresh() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_plex.bat")
    create_and_run(script, build_plex_batch_content(), runner="cmd")
    say("PLEX REFRESH SPAWNED", GREEN)


def action_scan_duplicates() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_dupes.py")
    create_and_run(script, build_dupes_py_content(), runner="python")
    say("SCAN DUPLICATES SPAWNED", GREEN)


def action_reboot() -> None:
    # The generated batch reboots immediately (shutdown /r /f /t 0),
    # so require a typed confirmation before spawning it.
    answer = input(f"{AMBER}TYPE REBOOT TO CONFIRM, ANYTHING ELSE TO CANCEL: {RESET}").strip()
    if answer != "REBOOT":
        say("REBOOT CANCELLED", AMBER)
        return
    script = os.path.join(tempfile.gettempdir(), "media_tool_reboot.bat")
    create_and_run(script, build_reboot_batch_content(), runner="cmd")
    say("REBOOT INITIATED", AMBER)


def action_encrypt_folders() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_encrypt.py")
    create_and_run(script, build_encrypt_folders_py_content(), runner="python")
    say("ENCRYPT FOLDERS SPAWNED", GREEN)


def action_flac_convert() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_flac.py")
    create_and_run(script, build_flac_py_content(), runner="python")
    say("FLAC CONVERT SPAWNED", GREEN)


def action_mka_convert() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_mka.py")
    create_and_run(script, build_mkaconvert_py_content(), runner="python")
    say("MKA CONVERT SPAWNED", GREEN)


def action_rename_folders() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_rename_folders.py")
    create_and_run(script, build_rename_folders_py_content(), runner="python")
    say("RENAME FOLDERS SPAWNED", GREEN)


def action_rename_folders_remove_underscores() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_rename_underscores.py")
    create_and_run(script, build_rename_folders_remove_underscores_py_content(), runner="python")
    say("REMOVE UNDERSCORES FROM FOLDERS SPAWNED", GREEN)


def action_organize_files() -> None:
    target = input(f"{AMBER}TARGET FOLDER TO ORGANIZE: ").strip()
    if not target:
        say("NO TARGET FOLDER PROVIDED", RED)
        return
    if not os.path.isdir(target):
        say(f"ERROR: {target} IS NOT A DIRECTORY", RED)
        return
    script = os.path.join(tempfile.gettempdir(), "media_tool_organize.py")
    create_and_run(script, build_organize_files_py_content(target), runner="python")
    say("ORGANIZE FILES SPAWNED", GREEN)


def action_tdarr_cleanup() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_tdarr.py")
    create_and_run(script, build_tdarr_cleanup_py_content(), runner="python")
    say("TDARR CLEANUP SPAWNED", GREEN)


def action_winrar_wizard() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_winrar.py")
    create_and_run(script, build_winrar_wizard_py_content(), runner="python")
    say("WINRAR WIZARD SPAWNED", GREEN)


def action_reset_recent() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_reset_recent.py")
    create_and_run(script, build_reset_recent_py_content(), runner="python")
    say("RESET RECENT ITEMS SPAWNED", GREEN)


def action_context_menu_reg() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_context_menu.py")
    create_and_run(script, build_context_menu_reg_py_content(), runner="python")
    say("CONTEXT MENU REG SPAWNED", GREEN)


def action_winrm_reboot() -> None:
    script = os.path.join(tempfile.gettempdir(), "media_tool_winrm_reboot.py")
    create_and_run(script, build_winrm_reboot_py_content(), runner="python")
    say("WINRM REBOOT MANAGER SPAWNED", GREEN)


MENU_ITEMS = [
    ("1", "FIX MUSIC DUPLICATES", "Creates folder.bat in subfolders to move media files into random-named folders and delete itself."),
    ("2", "PLEX REFRESH", "Scans and refreshes the Plex library across configured sections."),
    ("3", "SCAN DUPLICATES", "Scans the TV library for duplicate episodes, keeping the best format."),
    ("4", "REBOOT", "Reboots the computer immediately."),
    ("5", "ENCRYPT FOLDERS", "Compress & Delete Folders"),
    ("6", "FLAC CONVERT", "Converts FLAC files to MP3 using FFmpeg."),
    ("7", "MKA CONVERT", "Converts MKA files to MP3 using FFmpeg."),
    ("8", "RENAME FOLDERS", "Scans a directory and removes specified text from matching folder names."),
    ("9", "REMOVE UNDERSCORES FROM FOLDERS", "Recursively replaces underscores with spaces in folder names (deepest first)."),
    ("10", "ORGANIZE FILES", "Moves files into subfolders named after the file."),
    ("11", "TDARR CLEANUP", "Runs Tdarr HandBrake retry cleanup."),
    ("12", "WINRAR WIZARD", "Interactive WinRAR archive & compression wizard."),
    ("13", "RESET RECENT ITEMS", "Clears Windows Recent items and destinations."),
    ("14", "ADD COPY/MOVE TO CONTEXT MENU", "Adds 'Copy To' and 'Move To' to context menu for all users (Admin)."),
    ("15", "WINDOWS REMOTE REBOOT", "Manages saved remote Windows hosts and executes WinRM reboots."),
    ("16", "EXIT", ""),
]

ACTIONS = {
    "1": action_organize_media,
    "2": action_plex_refresh,
    "3": action_scan_duplicates,
    "4": action_reboot,
    "5": action_encrypt_folders,
    "6": action_flac_convert,
    "7": action_mka_convert,
    "8": action_rename_folders,
    "9": action_rename_folders_remove_underscores,
    "10": action_organize_files,
    "11": action_tdarr_cleanup,
    "12": action_winrar_wizard,
    "13": action_reset_recent,
    "14": action_context_menu_reg,
    "15": action_winrm_reboot,
}


def show_menu() -> None:
    say(MENU_SUBTITLE, AMBER)
    for k, name, desc in MENU_ITEMS:
        if desc:
            say(f"{GREEN}{k}) {name} - {desc}{RESET}")
        else:
            say(f"{GREEN}{k}) {name}{RESET}")
    say(f"{AMBER}SELECT>{RESET}", WHITE)


def main() -> None:
    # Legacy launcher: superseded by media_console. Its actions delete
    # sources without verification and its reboot is immediate, so
    # require a deliberate opt-in before showing the menu at all.
    show_banner()
    say("WARNING: LEGACY LAUNCHER - SUPERSEDED BY media_console", RED)
    say("Actions here delete source files WITHOUT verification.", RED)
    say("Use media_console instead unless you know exactly what this does.", RED)
    answer = input(f"{AMBER}TYPE LEGACY TO CONTINUE, ANYTHING ELSE TO EXIT: {RESET}").strip()
    if answer != "LEGACY":
        say("EXITING - NOTHING WAS RUN", AMBER)
        return
    while True:
        show_banner()
        show_menu()
        choice = input(f"{AMBER}SELECT>{RESET} ").strip()
        if choice == "16" or choice == "":
            say("MEDIA_N SESSION END", AMBER)
            break
        action = ACTIONS.get(choice)
        if action is None:
            say(f"INVALID OPTION: {choice}", RED)
            continue
        say(f"SPAWN: {action.__name__}")
        action()
        subprocess.run(["cmd.exe", "/c", "timeout", "/t", "1", ">nul"], check=False)


if __name__ == "__main__":
    main()