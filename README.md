# scripts_ahoy

A Windows console toolkit for maintaining a media library: music and TV file
cleanup, FLAC/MKA to MP3 conversion, folder archiving, Plex refresh, Tdarr
cleanup, and remote reboot over WinRM.

The repository has two parts:

| Path | What it is |
|---|---|
| `scripts_ahoy.py` | The original menu-driven launcher, with 16 actions. Kept for reference and for the actions not yet ported. |
| `media_console/` | A safer rewrite of the file-changing actions (menu items 1, 3–10). Previews changes, asks for confirmation, and verifies conversions before deleting sources. |

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Optional, depending on which actions you use:
  - [ffmpeg](https://ffmpeg.org/) and ffprobe (FLAC/MKA conversion)
  - WinRAR's console `Rar.exe` (folder archiving)
  - HandBrakeCLI (Tdarr cleanup, original launcher only)
  - Plex Media Scanner (Plex refresh, original launcher only)
  - `pywinrm` (`pip install pywinrm`, remote reboot, original launcher only)

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
| 3 | Scan duplicates | Writes a report only | Never deletes |
| 4 | Reboot | Restarts the computer | 30-second delay, cancel with `shutdown /a` |
| 5 | Archive folders | Creates `.rar`, deletes folder | Runs `rar t` before deleting |
| 6 | FLAC to MP3 | Converts, deletes FLAC | Duration must match the source |
| 7 | MKA to MP3 | Converts, deletes MKA | Duration must match the source |
| 8 | Remove text from folder names | Renames folders | Skips empty or colliding names |
| 9 | Underscores to spaces | Renames folders | Skips empty or colliding names |
| 10 | Organize files | Moves files into folders | Skips existing destinations |

## Configuration

Settings for the safe tools live in `media_console/config.json`:

```json
{
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffprobe",
    "rar_path": "C:\\Program Files\\WinRAR\\Rar.exe",
    "tv_dupes_dir": "N:\\TV Shows\\D",
    "report_dir": "N:\\",
    "duration_tolerance_seconds": 1.0,
    "reboot_delay_seconds": 30
}
```

Check these paths before the first run. `tv_dupes_dir` and `report_dir` are
specific to the original setup.

The tools check the config at startup. If a key is missing, has the wrong type,
is out of range, or is misspelled, they print every problem and exit before
doing anything.

## Running the tests

```bat
cd media_console
pip install pytest
python -m pytest
```

The tests cover config validation, duplicate detection and ranking, folder
rename planning (including collisions and empty names), the conversion check,
and the guarantee that dry run and a declined confirmation change nothing. They
do not run ffmpeg, RAR, or any real file moves on your library.

## The original launcher

```bat
python scripts_ahoy.py
```

It is a menu of 16 actions. Each one writes a helper script to the temp folder
and opens it in a new `cmd` window. Several actions delete source files
without a confirmation step. Use the `media_console` tools for those, or review
the original's behaviour before running it on data you care about.

## Known limitations

- **Encryption is not real encryption.** The original "Encrypt folders" action
  (launcher item 5) only compresses. The safe equivalent in `media_console`
  (item 5) is named "archive" for that reason. Add `-hp` for a password if you
  need encryption.
- **The safe tools are not yet tested on Windows** in this repository. Run
  them on a copy of a small test folder first.
- **Items 2, 11–15 of the original** (Plex refresh, Tdarr cleanup, WinRAR
  wizard, reset recent items, context menu registration, remote reboot) are
  only in `scripts_ahoy.py`.
- **Verification depends on ffprobe.** If it cannot read a duration, the
  source file is kept.
- **Hard-coded paths in the original.** The launcher still contains paths and
  IP addresses from its original setup. Move them to a config file before
  using it elsewhere.

## Safety notes

- Deleting actions are irreversible. Keep backups of anything important.
- Dry run is on at startup in `media_console`. Leave it on until you have read
  the preview for each action.
- Do not commit `windows_computers.json`. It holds remote hosts and usernames.
  Add it to `.gitignore`.

## Licence

No licence is set yet.
