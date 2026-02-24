"""Tests for metadata-based audio matching in AudioDiscoveryService."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.feature_engineering.audio_discovery import (
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.models import (
    AudioStatus,
    MusicLibraryEntry,
    MusicLibraryIndex,
)


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def _make_index(
    entries: list[MusicLibraryEntry], source_dirs: tuple[str, ...] = ()
) -> MusicLibraryIndex:
    return MusicLibraryIndex(entries=tuple(entries), source_dirs=source_dirs)


def test_metadata_title_match_beats_filename_mismatch(tmp_path: Path) -> None:
    """A file whose metadata title matches the sequence song should win
    even when its filename is completely unrelated."""
    music_root = tmp_path / "music"
    _write_audio(music_root / "Polar Express Medley_FINAL.mp3")

    index = _make_index(
        [
            MusicLibraryEntry(
                path=str(music_root / "Polar Express Medley_FINAL.mp3"),
                title="Rockin' on Top of the World",
                artist="Steven Tyler",
                album="",
                duration_s=294.0,
            ),
        ]
    )

    service = AudioDiscoveryService(
        options=AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=0.85,
        ),
        music_library_index=index,
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=tmp_path / "profiles" / "p",
            media_file="some_other_path.mp3",
            song="Rockin' on Top of the World",
            sequence_filename="Polar Express.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_MUSIC_DIR
    assert result.audio_path is not None
    assert "Polar Express Medley_FINAL" in result.audio_path


def test_metadata_artist_confirmation_boosts_score(tmp_path: Path) -> None:
    """When both title and artist match, the score should be higher
    than title-only match."""
    music_root = tmp_path / "music"
    _write_audio(music_root / "trackA.mp3")
    _write_audio(music_root / "trackB.mp3")

    index = _make_index(
        [
            MusicLibraryEntry(
                path=str(music_root / "trackA.mp3"),
                title="Jingle Bells",
                artist="Wrong Artist",
            ),
            MusicLibraryEntry(
                path=str(music_root / "trackB.mp3"),
                title="Jingle Bells",
                artist="Burl Ives",
            ),
        ]
    )

    service = AudioDiscoveryService(
        options=AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=0.50,
        ),
        music_library_index=index,
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=tmp_path / "profiles" / "p",
            media_file="",
            song="Jingle Bells",
            artist="Burl Ives",
            sequence_filename="JingleBells.xsq",
        )
    )

    assert result.audio_path is not None
    assert "trackB" in result.audio_path


def test_no_metadata_index_uses_existing_heuristics(tmp_path: Path) -> None:
    """When no music library index is provided, the existing filename
    heuristic scoring continues to work."""
    music_root = tmp_path / "music"
    _write_audio(music_root / "Wrap Me Up.mp3")

    service = AudioDiscoveryService(
        options=AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=0.80,
        ),
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=tmp_path / "profiles" / "p",
            media_file="Wrap Me Up.mp3",
            song="Wrap Me Up",
            sequence_filename="Wrap Me Up.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_MUSIC_DIR
    assert result.audio_path is not None


def test_metadata_match_overrides_low_filename_score(tmp_path: Path) -> None:
    """Metadata match rescues a candidate that would be LOW_CONFIDENCE
    based on filename alone."""
    music_root = tmp_path / "music"
    _write_audio(music_root / "Christmas Remix.mp3")

    index = _make_index(
        [
            MusicLibraryEntry(
                path=str(music_root / "Christmas Remix.mp3"),
                title="Mix by audio-joiner.com",
                artist="TopHits",
            ),
        ]
    )

    service = AudioDiscoveryService(
        options=AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=0.85,
        ),
        music_library_index=index,
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=tmp_path / "profiles" / "p",
            media_file="some_path.mp3",
            song="Mix by audio-joiner.com",
            sequence_filename="Christmas.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_MUSIC_DIR
    assert result.audio_path is not None
    assert "Christmas Remix" in result.audio_path


def test_duration_close_match_provides_bonus(tmp_path: Path) -> None:
    """When sequence duration and audio duration are close, the match
    gets a confidence boost."""
    music_root = tmp_path / "music"
    _write_audio(music_root / "track.mp3")

    index = _make_index(
        [
            MusicLibraryEntry(
                path=str(music_root / "track.mp3"),
                title="Holiday Song",
                duration_s=180.0,
            ),
        ]
    )

    service = AudioDiscoveryService(
        options=AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=0.50,
        ),
        music_library_index=index,
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=tmp_path / "profiles" / "p",
            media_file="",
            song="Holiday Song",
            sequence_filename="show.xsq",
            sequence_duration_ms=180000,
        )
    )

    assert result.audio_path is not None
    assert result.match_confidence is not None
    # Score should include duration bonus
    for candidate in result.candidate_rankings:
        if "track.mp3" in candidate.path:
            assert "duration" in candidate.reason.lower()
            break
