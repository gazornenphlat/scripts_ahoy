# scripts_ahoy

A Windows console toolkit for maintaining a media library: music and TV file
cleanup, FLAC/MKA to MP3 conversion, folder archiving, Plex refresh, Tdarr
cleanup, and remote reboot over WinRM.

The repository has two parts:

| Path | What it is |
|---|---|
| `legacy/scripts_ahoy.py` | The original menu-driven launcher, kept for reference only. Superseded by `media_console`. |
| `media_console/` | A safer rewrite of every action in the launcher (menu items 1–15). Previews changes, asks for confirmation, and verifies conversions and encodes before deleting sources. |

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Optional, depending on which actions you use:
  - [ffmpeg](https://ffmpeg.org/) and ffprobe (FLAC/MKA conversion, Tdarr verification)
  - WinRAR's console `Rar.exe` (folder archiving, RAR wizard)
  - HandBrakeCLI (Tdarr cleanup)
  - Plex Media Scanner (Plex refresh)
  - `pywinrm` (`pip install pywinrm`, remote reboot)

## Quick start: the safe tools

```bat
cd media_console
python tools.py
```

The menu opens with **dry run ON**, so nothing changes until you turn it off
with `D`.

1. Pick an action by number.
2. Read the preview: every planned change is listed.
3. To apply, turn dry run off (`D`), run the action again, and type the
   confirmation word shown (`APPLY`, or `DELETE` where source files are removed).

Anything other than the confirmation word cancels.

### What each safe action does

| # | Action | Changes files? | Safety |
|---|---|---|---|
| 1 | Fix music duplicates | Moves audio into unique subfolders | Preview, confirm |
| 2 | Plex refresh | Asks Plex to rescan the sections in config | Non-destructive; confirm with `APPLY` |
| 3 | Scan duplicates | Writes a report ranking copies by resolution, then bitrate, then container | Never deletes |
| 4 | Reboot | Restarts the computer | 30-second delay, cancel with `shutdown /a` |
| 5 | Archive folders | Creates `.rar`, deletes folder | Runs `rar t` before deleting |
| 6 | FLAC to MP3 | Converts, deletes FLAC | Duration must match the source, output must have audio, and must decode with no errors |
| 7 | MKA to MP3 | Converts, deletes MKA | Same checks as item 6 |
| 8 | Remove text from folder names | Renames folders | Skips empty or colliding names |
| 9 | Underscores to spaces | Renames folders | Skips empty or colliding names |
| 10 | Organize files | Moves files into folders | Skips existing destinations |
| 11 | Tdarr cleanup | Re-encodes Tdarr error/cancelled items; deletes source and Tdarr record on success | Checks output size, duration, video stream, and full decode; on failure the source is moved to the failed folder, not deleted |
| 12 | WinRAR wizard | Creates RAR archives from a folder | Never deletes sources; skips existing archives |
| 13 | Reset recent items | Deletes Windows Recent and jump-list files | Confirm with `DELETE` |
| 14 | Context menu entries | Adds "Copy To" and "Move To" to Explorer | Needs administrator; warns if not admin |
| 15 | Remote reboot (WinRM) | Reboots a saved Windows host | Saves host and username only; password is prompted at reboot time; confirm with `REBOOT` |

## Configuration

Settings for the safe tools live in `media_console/config.json`:

```json
{
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffprobe",
    "rar_path": "C:\\Program Files\\WinRAR\\Rar.exe",
    "handbrake_cli": "C:\\Program Files\\HandBrake\\HandBrakeCLI.exe",
    "plex_scanner": "d:\\Plex\\Plex Media Server\\Plex Media Scanner.exe",
    "plex_sections": [67, 3, 60, 71, 73, 74, 75, 5],
    "tv_dupes_dir": "N:\\TV Shows\\D",
    "report_dir": "N:\\",
    "tdarr_url": "http://10.120.1.147:8265",
    "tdarr_api_key_env": "TDARR_API_KEY",
    "tdarr_out_ext": ".mkv",
    "tdarr_finished_dir": "N:\\aaa_finished",
    "tdarr_failed_dir": "N:\\aaa_failed",
    "tdarr_min_output_bytes": 1048576,
    "duration_tolerance_seconds": 1.0,
    "reboot_delay_seconds": 30,
    "windows_computers_file": "windows_computers.json",
    "winrm_port": 5985,
    "winrm_use_https": false
}
```

Check these paths before the first run. Several are specific to the original
setup (the `N:` drive, the Tdarr address, and the Plex section IDs).

Secrets are never stored in the config. Tdarr's API key is read from the
environment variable named in `tdarr_api_key_env` (set `TDARR_API_KEY` before
starting the console). WinRM passwords are prompted for at reboot time.

The tools check the config at startup. If a key is missing, has the wrong type,
is out of range, or is misspelled, they print every problem and exit before
doing anything.

## Installing

```bat
pip install -e ".[dev]"            :: tests and lint
pip install -e ".[winrm]"          :: adds pywinrm for remote reboot (item 15)
```

## Trying it safely: rehearsal on a sample library

Before pointing the tools at real data, rehearse on a throwaway library:

1. Build the sample: `python media_console\make_sample_library.py C:\Temp\media_test`
2. Point `config.json` at the sample folders (or copy the layout into your
   test area).
3. Start `python media_console\tools.py`. Leave dry run **on** and run each
   action. Check the preview matches what you expect.
4. Turn dry run off (`D`) and run items 1, 8, 9, and 10 on the sample. Check the
   result by hand.
5. Run items 6 and 7 on the sample. The placeholder audio cannot be decoded,
   so the tool should **refuse to delete** the source and say so. If it
   deletes anything, stop and report it.
6. Run item 5 on the sample, then check that the archives open.

Only move on to real data once each step behaves as described.

## Running the tests

```bat
cd media_console
python -m pytest
```

Lint runs from the repository root with `python -m ruff check .`. CI runs both
on Windows for every push (`.github/workflows/ci.yml`).

The tests (79 of them) cover config validation, duplicate detection and ranking,
folder rename planning (including collisions and empty names), the conversion
check, Tdarr record selection, RAR archive planning, recent-item discovery,
registry command construction, saved-computer handling, and the guarantee that
dry run and a declined confirmation change nothing. They do not contact a Tdarr
server or WinRM host, run ffmpeg, RAR or HandBrake, touch the registry, or move
files on your library.

## Legacy: the original launcher

`legacy/scripts_ahoy.py` is the original menu-driven launcher, kept for
reference only. Do not use it for real work. It is superseded by
`media_console`, which covers all of its actions with safety checks.

It is a menu of 16 actions. Each one writes a helper script to the temp folder
and opens it in a new `cmd` window. Several actions delete source files
without the verification the rewrite performs. The file now requires typing
`LEGACY` at startup before it shows the menu, and its reboot action requires
typing `REBOOT`; the `winrarPath` crash in the encrypt action is fixed.
The JDownloader watch-folder action was defined but never wired into the
menu, so it was removed rather than carried over; the rewrite has no
equivalent for it.

## Known limitations

- **Encryption is not real encryption.** The original "Encrypt folders" action
  (launcher item 5) only compresses. The safe equivalent in `media_console`
  (item 5) is named "archive" for that reason. Add `-hp` for a password if you
  need encryption.
- **The safe tools are not yet tested on Windows** in this repository. Run
  them on a copy of a small test folder first.
- **Verification depends on ffprobe.** If it cannot read a duration, the
  source file is kept.
- **Tdarr and WinRM actions are untested against real servers.** The request
  and command formats were copied from the original launcher; check one
  record or one host before running them on a whole library.
- **The legacy launcher is guarded, not made safe.** `legacy/scripts_ahoy.py`
  now requires typing `LEGACY` at startup and `REBOOT` before rebooting, but
  its actions still delete without verification and its paths are hard-coded.
  Prefer `media_console`.

## Safety notes

- Deleting actions are irreversible. Keep backups of anything important.
- Dry run is on at startup in `media_console`. Leave it on until you have read
  the preview for each action.
- `windows_computers.json` holds remote hosts and usernames, and is listed in
  `.gitignore`, so it is not committed. It never holds passwords.

## Licence

No licence is set yet.
