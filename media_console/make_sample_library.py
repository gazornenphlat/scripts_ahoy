#!/usr/bin/env python3
"""Build a throwaway sample library for trying the media console safely.

Usage:
    python make_sample_library.py "C:\\Temp\\media_test"

Creates a folder tree with placeholder files (not real media). Use it to
rehearse each action on Windows before pointing the tools at real data.

The placeholder audio and video files cannot be decoded, so conversion
actions will refuse to delete them. That is intentional: it checks the
safety rule works on your machine.
"""

import sys
from pathlib import Path


def build(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"Refusing to write into a non-empty folder: {root}")

    layout = {
        # 1 and 10: loose audio and files that need organizing
        "music/Artist One/track_01.mp3": "fake",
        "music/Artist One/track_02.flac": "fake",
        "music/Artist Two/song.m4a": "fake",
        # 6: FLAC conversion (should be refused: placeholders are not decodable)
        "flac/album/disc.flac": "fake",
        # 7: MKA conversion (same check)
        "mka/clip.mka": "fake",
        # 8 and 9: names with underscores and removable text
        "names/my_album_v2/readme.txt": "x",
        "names/draft_copy/notes.txt": "x",
        # 5: folder archiving, one subfolder per item
        "archive/projectA/file.txt": "x",
        "archive/projectB/file.txt": "x",
        # 3: duplicate episodes across containers
        "tv/Show/Show.S01E01.mkv": "fake",
        "tv/Show/Show.S01E01.mp4": "fake",
        "tv/Show/Show.S01E02.avi": "fake",
        # 10: loose files for organize
        "loose/notes.txt": "x",
        "loose/photo.jpg": "x",
    }
    for rel, content in layout.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(f"Sample library written to {root}")
    print("Point config.json at these folders, or copy this layout into your test area.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
