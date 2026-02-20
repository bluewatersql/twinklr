from __future__ import annotations

from pathlib import Path

from twinklr.core.feature_engineering.audio_discovery import (
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.models import AudioStatus


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")


def test_discovery_prefers_pack_exact_match(tmp_path: Path) -> None:
    extracted_root = tmp_path / "vendor"
    music_root = tmp_path / "music"
    profile_dir = tmp_path / "profiles" / "show_profile"

    _write_audio(extracted_root / "show_extracted" / "Need A Favor.mp3")
    _write_audio(music_root / "Need A Favor.wav")
    profile_dir.mkdir(parents=True, exist_ok=True)

    service = AudioDiscoveryService(
        AudioDiscoveryOptions(
            extracted_search_roots=(extracted_root,),
            music_repo_roots=(music_root,),
            confidence_threshold=0.85,
        )
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=profile_dir,
            media_file="Need A Favor.mp3",
            song="Need A Favor",
            sequence_filename="Need A Favor.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_PACK
    assert result.audio_path is not None
    assert result.audio_path.endswith("Need A Favor.mp3")
    assert result.match_confidence is not None and result.match_confidence >= 0.85


def test_discovery_falls_back_to_music_repo(tmp_path: Path) -> None:
    extracted_root = tmp_path / "vendor"
    music_root = tmp_path / "music"
    profile_dir = tmp_path / "profiles" / "show_profile"

    _write_audio(music_root / "Holiday Mix.flac")
    profile_dir.mkdir(parents=True, exist_ok=True)

    service = AudioDiscoveryService(
        AudioDiscoveryOptions(
            extracted_search_roots=(extracted_root,),
            music_repo_roots=(music_root,),
            confidence_threshold=0.80,
        )
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=profile_dir,
            media_file="",
            song="Holiday Mix",
            sequence_filename="Holiday Mix.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_MUSIC_DIR
    assert result.audio_path is not None
    assert result.audio_path.endswith("Holiday Mix.flac")


def test_discovery_below_threshold_is_low_confidence(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    profile_dir = tmp_path / "profiles" / "show_profile"

    _write_audio(music_root / "Unknown Track.mp3")
    profile_dir.mkdir(parents=True, exist_ok=True)

    service = AudioDiscoveryService(
        AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(music_root,),
            confidence_threshold=1.40,
        )
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=profile_dir,
            media_file="Need A Favor.mp3",
            song="Need A Favor",
            sequence_filename="Need A Favor.xsq",
        )
    )

    assert result.audio_status is AudioStatus.LOW_CONFIDENCE
    assert result.audio_path is None
    assert result.candidate_rankings


def test_discovery_missing_when_no_candidates(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "show_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    service = AudioDiscoveryService(
        AudioDiscoveryOptions(
            extracted_search_roots=(),
            music_repo_roots=(),
        )
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=profile_dir,
            media_file="Need A Favor.mp3",
            song="Need A Favor",
            sequence_filename="Need A Favor.xsq",
        )
    )

    assert result.audio_status is AudioStatus.MISSING
    assert result.audio_path is None


def test_normalization_handles_punctuation_and_case(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    profile_dir = tmp_path / "profiles" / "show_profile"

    _write_audio(music_root / "Childrens Christmas Mix.wav")
    profile_dir.mkdir(parents=True, exist_ok=True)

    service = AudioDiscoveryService(
        AudioDiscoveryOptions(extracted_search_roots=(), music_repo_roots=(music_root,))
    )
    result = service.discover_audio(
        AudioDiscoveryContext(
            profile_dir=profile_dir,
            media_file="Children's Christmas Mix.mp3",
            song="CHILDREN'S Christmas Mix",
            sequence_filename="children's christmas mix.xsq",
        )
    )

    assert result.audio_status is AudioStatus.FOUND_IN_MUSIC_DIR
    assert result.audio_path is not None
    assert result.audio_path.endswith("Childrens Christmas Mix.wav")
