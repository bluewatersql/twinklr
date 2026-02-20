#!/usr/bin/env python3
"""Build a music library index from audio files.

Scans one or more directories for audio files, extracts embedded metadata
(ID3 tags for MP3, Vorbis for FLAC/OGG, etc.), and writes a JSON index
to ``data/music/music_library_index.json``.

Usage::

    uv run python scripts/build_music_library_index.py
    uv run python scripts/build_music_library_index.py --dirs data/music data/extra_audio
    uv run python scripts/build_music_library_index.py --output data/custom_index.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from twinklr.core.feature_engineering.music_library_indexer import build_music_library_index

_DEFAULT_MUSIC_DIR = Path("data/music")
_DEFAULT_OUTPUT = Path("data/music/music_library_index.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build music library metadata index")
    parser.add_argument(
        "--dirs",
        nargs="+",
        type=Path,
        default=[_DEFAULT_MUSIC_DIR],
        help="Directories to scan for audio files (default: data/music)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output JSON path (default: data/music/music_library_index.json)",
    )
    args = parser.parse_args()

    print(f"Scanning {len(args.dirs)} director{'y' if len(args.dirs) == 1 else 'ies'}...")
    for d in args.dirs:
        print(f"  {d.resolve()}")

    index = build_music_library_index(source_dirs=tuple(args.dirs))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(index.model_dump_json(indent=2))

    tagged = sum(1 for e in index.entries if e.title)
    untagged = len(index.entries) - tagged

    print(f"\nIndexed {len(index.entries)} audio files:")
    print(f"  With metadata: {tagged}")
    print(f"  Without tags:  {untagged}")
    print(f"\nIndex written to: {args.output}")

    if tagged > 0:
        print("\nSample entries:")
        for entry in index.entries[:5]:
            if entry.title:
                dur = f"{entry.duration_s:.1f}s" if entry.duration_s > 0 else "n/a"
                print(f"  {Path(entry.path).name}")
                print(f"    title={entry.title!r} artist={entry.artist!r} duration={dur}")


if __name__ == "__main__":
    main()
