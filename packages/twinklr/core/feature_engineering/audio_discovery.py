"""Deterministic audio discovery for feature engineering."""

from __future__ import annotations

import string
import time
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Protocol

from twinklr.core.feature_engineering.models import (
    AudioCandidate,
    AudioCandidateOrigin,
    AudioDiscoveryResult,
    AudioStatus,
)

_AUDIO_EXT_PRIORITY: tuple[str, ...] = (".wav", ".flac", ".m4a", ".mp3", ".aac", ".ogg")
_PUNCT_TRANSLATOR = str.maketrans(dict.fromkeys(string.punctuation, " "))
_LOW_CONFIDENCE_FLOOR = 0.60


class AudioAnalyzerLike(Protocol):
    """Protocol wrapper for sync analyzer usage."""

    def analyze_sync(self, audio_path: str, *, force_reprocess: bool = False): ...  # noqa: ANN201


@dataclass(frozen=True)
class AudioDiscoveryOptions:
    """Audio discovery configuration."""

    confidence_threshold: float = 0.85
    extracted_search_roots: tuple[Path, ...] = (Path("data/vendor_packages"),)
    music_repo_roots: tuple[Path, ...] = (Path("data/music"),)
    audio_extensions: tuple[str, ...] = _AUDIO_EXT_PRIORITY


@dataclass(frozen=True)
class AudioDiscoveryContext:
    """Inputs needed to discover audio for a sequence."""

    profile_dir: Path
    media_file: str
    song: str
    sequence_filename: str


class AudioDiscoveryService:
    """Rank and select audio files using deterministic scoring."""

    def __init__(self, options: AudioDiscoveryOptions | None = None) -> None:
        self._options = options or AudioDiscoveryOptions()
        self._ext_bonus: dict[str, float] = self._build_extension_bonus(self._options.audio_extensions)

    @staticmethod
    def _build_extension_bonus(ordered_exts: tuple[str, ...]) -> dict[str, float]:
        if not ordered_exts:
            return {}
        max_i = max(1, len(ordered_exts) - 1)
        return {
            ext: 0.05 * (1.0 - (idx / max_i))
            for idx, ext in enumerate(ordered_exts)
        }

    def discover_audio(self, context: AudioDiscoveryContext) -> AudioDiscoveryResult:
        candidates = self._collect_candidates(context)
        if not candidates:
            return AudioDiscoveryResult(
                audio_path=None,
                audio_status=AudioStatus.MISSING,
                match_confidence=None,
                match_reason="no audio candidates found in extracted files or music repo",
                candidate_rankings=(),
            )

        ranked = self._rank_candidates(candidates, context)
        best = ranked[0]
        if best.score < self._options.confidence_threshold:
            return AudioDiscoveryResult(
                audio_path=None,
                audio_status=AudioStatus.LOW_CONFIDENCE,
                match_confidence=best.score,
                match_reason=(
                    f"best candidate below threshold "
                    f"({best.score:.3f} < {self._options.confidence_threshold:.3f})"
                ),
                candidate_rankings=tuple(ranked),
            )

        status = (
            AudioStatus.FOUND_IN_PACK
            if best.origin is AudioCandidateOrigin.PACK
            else AudioStatus.FOUND_IN_MUSIC_DIR
        )
        return AudioDiscoveryResult(
            audio_path=best.path,
            audio_status=status,
            match_confidence=best.score,
            match_reason=best.reason,
            candidate_rankings=tuple(ranked),
        )

    def run_audio_analysis(
        self,
        result: AudioDiscoveryResult,
        *,
        analyzer: AudioAnalyzerLike | None,
        analyzer_version: str = "AudioAnalyzer",
        force_reprocess: bool = False,
        audio_required: bool = False,
    ) -> AudioDiscoveryResult:
        if result.audio_status not in {AudioStatus.FOUND_IN_PACK, AudioStatus.FOUND_IN_MUSIC_DIR}:
            if audio_required:
                raise ValueError(f"Audio required but status={result.audio_status.value}")
            return result

        if analyzer is None:
            if audio_required:
                raise ValueError("Audio required but no analyzer configured")
            return result.model_copy(update={"analyzer_error": "analyzer not configured"})

        assert result.audio_path is not None  # guaranteed by status
        start = time.perf_counter()
        try:
            analyzer.analyze_sync(result.audio_path, force_reprocess=force_reprocess)
        except Exception as exc:  # noqa: BLE001
            if audio_required:
                raise
            return result.model_copy(
                update={
                    "analyzer_version": analyzer_version,
                    "analyzer_error": str(exc),
                    "compute_ms": int((time.perf_counter() - start) * 1000),
                    "cache_hit": None,
                }
            )

        compute_ms = int((time.perf_counter() - start) * 1000)
        cache_hit = compute_ms < 500
        return result.model_copy(
            update={
                "analyzer_version": analyzer_version,
                "cache_hit": cache_hit,
                "compute_ms": compute_ms,
                "analyzer_error": None,
            }
        )

    def _collect_candidates(self, context: AudioDiscoveryContext) -> list[tuple[Path, AudioCandidateOrigin]]:
        pack_candidates = self._iter_pack_candidates(context)
        music_candidates = self._iter_music_repo_candidates()
        combined = [*pack_candidates, *music_candidates]
        combined.sort(key=lambda item: item[0].as_posix().lower())
        return combined

    def _iter_pack_candidates(
        self, context: AudioDiscoveryContext
    ) -> list[tuple[Path, AudioCandidateOrigin]]:
        profile_stem = context.profile_dir.name.removesuffix("_profile")
        all_candidates: list[tuple[Path, AudioCandidateOrigin]] = []
        for root in self._options.extracted_search_roots:
            root_path = root.resolve()
            if not root_path.exists():
                continue
            for directory in sorted(root_path.glob("*_extracted")):
                if profile_stem and profile_stem not in directory.name:
                    continue
                for path in self._walk_audio_files(directory):
                    all_candidates.append((path, AudioCandidateOrigin.PACK))
        return all_candidates

    def _iter_music_repo_candidates(self) -> list[tuple[Path, AudioCandidateOrigin]]:
        all_candidates: list[tuple[Path, AudioCandidateOrigin]] = []
        for root in self._options.music_repo_roots:
            root_path = root.resolve()
            if not root_path.exists():
                continue
            for path in self._walk_audio_files(root_path):
                all_candidates.append((path, AudioCandidateOrigin.MUSIC_REPO))
        return all_candidates

    def _walk_audio_files(self, root: Path) -> list[Path]:
        files = [
            path.resolve()
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in self._options.audio_extensions
        ]
        files.sort(key=lambda path: path.as_posix().lower())
        return files

    def _rank_candidates(
        self,
        candidates: list[tuple[Path, AudioCandidateOrigin]],
        context: AudioDiscoveryContext,
    ) -> list[AudioCandidate]:
        media_stem = self._normalize_text(Path(context.media_file).stem)
        song_norm = self._normalize_text(context.song)
        sequence_norm = self._normalize_text(Path(context.sequence_filename).stem)

        ranked: list[AudioCandidate] = []
        for path, origin in candidates:
            score, reason = self._score_candidate(
                candidate_stem=self._normalize_text(path.stem),
                candidate_ext=path.suffix.lower(),
                origin=origin,
                media_stem=media_stem,
                song_norm=song_norm,
                sequence_norm=sequence_norm,
            )
            ranked.append(
                AudioCandidate(
                    path=str(path),
                    origin=origin,
                    score=score,
                    reason=reason,
                )
            )
        ranked.sort(
            key=lambda c: (
                0 if self._normalize_text(Path(c.path).stem) == media_stem and media_stem else 1,
                -c.score,
                -self._ext_bonus.get(Path(c.path).suffix.lower(), 0.0),
                0 if c.origin is AudioCandidateOrigin.PACK else 1,
                c.path.lower(),
            )
        )
        return ranked

    def _score_candidate(
        self,
        *,
        candidate_stem: str,
        candidate_ext: str,
        origin: AudioCandidateOrigin,
        media_stem: str,
        song_norm: str,
        sequence_norm: str,
    ) -> tuple[float, str]:
        score = 0.0
        parts: list[str] = []

        if candidate_stem and media_stem and candidate_stem == media_stem:
            score += 1.0
            parts.append("exact media basename")

        song_similarity = self._token_similarity(candidate_stem, song_norm)
        if song_similarity > 0.0:
            weighted = song_similarity * 0.90
            score += weighted
            parts.append(f"song similarity {weighted:.3f}")

        seq_similarity = self._token_similarity(candidate_stem, sequence_norm)
        if seq_similarity > 0.0:
            weighted = seq_similarity * 0.25
            score += weighted
            parts.append(f"sequence similarity {weighted:.3f}")

        ext_bonus = self._ext_bonus.get(candidate_ext, 0.0)
        score += ext_bonus
        if ext_bonus > 0.0:
            parts.append(f"extension bonus {ext_bonus:.3f}")

        if origin is AudioCandidateOrigin.PACK:
            score += 0.05
            parts.append("pack source bonus 0.050")

        if score < _LOW_CONFIDENCE_FLOOR:
            parts.append("below low-confidence floor")
        return score, ", ".join(parts) if parts else "no strong match signals"

    @staticmethod
    def _token_similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        left_tokens = sorted(token for token in left.split(" ") if token)
        right_tokens = sorted(token for token in right.split(" ") if token)
        if not left_tokens or not right_tokens:
            return 0.0
        left_joined = " ".join(left_tokens)
        right_joined = " ".join(right_tokens)
        return SequenceMatcher(a=left_joined, b=right_joined).ratio()

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        normalized = normalized.translate(_PUNCT_TRANSLATOR)
        normalized = " ".join(normalized.lower().split())
        return normalized
