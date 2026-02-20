"""Tests for music library indexer."""

from __future__ import annotations

from pathlib import Path

import pytest

from twinklr.core.feature_engineering.models import MusicLibraryEntry, MusicLibraryIndex
from twinklr.core.feature_engineering.music_library_indexer import build_music_library_index


def _write_valid_mp3(path: Path, *, title: str, artist: str, album: str) -> None:
    """Create a minimal valid MP3 file with ID3 tags via mutagen."""
    from mutagen.id3 import TALB, TIT2, TPE1
    from mutagen.mp3 import MP3

    path.parent.mkdir(parents=True, exist_ok=True)
    # MPEG1 Layer3 128kbps 44100Hz frame = 417 bytes; need several for a valid sync
    frame = bytearray(b"\xff\xfb\x90\x00") + b"\x00" * 413
    path.write_bytes(bytes(frame) * 10)

    mp3 = MP3(path)
    mp3.add_tags()
    mp3.tags.add(TIT2(encoding=3, text=[title]))
    mp3.tags.add(TPE1(encoding=3, text=[artist]))
    mp3.tags.add(TALB(encoding=3, text=[album]))
    mp3.save()


@pytest.fixture()
def _mp3_with_tags(tmp_path: Path) -> Path:
    mp3_path = tmp_path / "music" / "01 - Wrap Me Up.mp3"
    _write_valid_mp3(
        mp3_path, title="Wrap Me Up", artist="Jimmy Fallon & Meghan Trainor", album="Wrap Me Up"
    )
    return mp3_path


def test_build_index_extracts_metadata(tmp_path: Path, _mp3_with_tags: Path) -> None:
    """Index builder reads ID3 tags from audio files."""
    music_dir = tmp_path / "music"
    index = build_music_library_index(source_dirs=(music_dir,))

    assert isinstance(index, MusicLibraryIndex)
    assert len(index.entries) == 1

    entry = index.entries[0]
    assert entry.title == "Wrap Me Up"
    assert entry.artist == "Jimmy Fallon & Meghan Trainor"
    assert entry.album == "Wrap Me Up"
    assert entry.path.endswith("01 - Wrap Me Up.mp3")


def test_build_index_skips_untagged_files(tmp_path: Path) -> None:
    """Files without readable tags get empty metadata but are still indexed."""
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    (music_dir / "mystery.mp3").write_bytes(b"\x00" * 100)

    index = build_music_library_index(source_dirs=(music_dir,))

    assert len(index.entries) == 1
    entry = index.entries[0]
    assert entry.title == ""
    assert entry.artist == ""


def test_build_index_ignores_non_audio_files(tmp_path: Path) -> None:
    """Non-audio extensions are excluded."""
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    (music_dir / "readme.txt").write_text("hi")
    (music_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff")

    index = build_music_library_index(source_dirs=(music_dir,))

    assert len(index.entries) == 0


def test_build_index_multiple_dirs(tmp_path: Path, _mp3_with_tags: Path) -> None:
    """Index builder scans multiple source directories."""
    dir_a = tmp_path / "music"
    dir_b = tmp_path / "extra"
    dir_b.mkdir(parents=True, exist_ok=True)
    (dir_b / "track.mp3").write_bytes(b"\x00" * 100)

    index = build_music_library_index(source_dirs=(dir_a, dir_b))
    assert len(index.entries) == 2


def test_build_index_records_source_dirs(tmp_path: Path) -> None:
    """Index records which directories were scanned."""
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    index = build_music_library_index(source_dirs=(music_dir,))
    assert str(music_dir) in index.source_dirs


def test_roundtrip_json(tmp_path: Path, _mp3_with_tags: Path) -> None:
    """Index serialises to JSON and deserialises back."""
    music_dir = tmp_path / "music"
    index = build_music_library_index(source_dirs=(music_dir,))

    json_path = tmp_path / "index.json"
    json_path.write_text(index.model_dump_json(indent=2))

    loaded = MusicLibraryIndex.model_validate_json(json_path.read_text())
    assert loaded == index
