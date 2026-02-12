"""Audio analyzer - extracts musical features from audio files.

This module provides the AudioAnalyzer class which replaces the old
process_song() module function. It follows the manager pattern where
configuration is provided at initialization.

Example:
    analyzer = AudioAnalyzer(app_config, job_config)
    features = analyzer.analyze("song.mp3")
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import librosa
import numpy as np

# Import all the analysis modules
from twinklr.core.audio.advanced.tension import compute_tension_curve
from twinklr.core.audio.cache_adapter import (
    load_audio_features_async,
    save_audio_features_async,
)
from twinklr.core.audio.energy.builds_drops import detect_builds_and_drops
from twinklr.core.audio.energy.multiscale import extract_smoothed_energy
from twinklr.core.audio.enhancement_factory import EnhancementServiceFactory
from twinklr.core.audio.harmonic.chords import detect_chords
from twinklr.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from twinklr.core.audio.harmonic.key import detect_musical_key, extract_chroma
from twinklr.core.audio.harmonic.pitch import extract_pitch_tracking
from twinklr.core.audio.models import (
    LyricsBundle,
    MetadataBundle,
    PhonemeBundle,
    SongBundle,
    SongTiming,
)
from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.metadata import EmbeddedMetadata
from twinklr.core.audio.phonemes.bundle import build_phoneme_bundle
from twinklr.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
)
from twinklr.core.audio.rhythm.tempo import detect_tempo_changes
from twinklr.core.audio.spectral.bands import extract_dynamic_features
from twinklr.core.audio.spectral.basic import extract_spectral_features
from twinklr.core.audio.spectral.vocals import detect_vocals
from twinklr.core.audio.structure.sections import detect_song_sections
from twinklr.core.audio.timeline.builder import build_timeline_export
from twinklr.core.audio.validation.validator import validate_features
from twinklr.core.caching import FSCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.io import RealFileSystem, absolute_path

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """Analyzes audio files to extract musical features.

    Provides comprehensive audio analysis including:
    - Tempo, beats, bars, downbeats
    - Energy at multiple temporal scales
    - Spectral characteristics
    - Dynamic features (frequency bands, transients)
    - Song structure (sections with labels)
    - Harmonic analysis (key, chords, pitch)
    - Unified timeline for lighting synchronization

    Results are cached to avoid reprocessing the same audio file.
    """

    def __init__(
        self,
        app_config: AppConfig,
        job_config: JobConfig,
        service_factory: EnhancementServiceFactory | None = None,
    ):
        """Initialize audio analyzer with configuration.

        Args:
            app_config: Application configuration (audio processing settings)
            job_config: Job configuration (checkpoint settings)
            service_factory: Optional factory for creating enhancement services (DI)
        """
        self.app_config = app_config
        self.job_config = job_config

        # Initialize async cache
        fs = RealFileSystem()
        cache_root = absolute_path(str(Path(app_config.cache_dir or "data/cache")))
        self.cache = FSCache(fs, cache_root)

        # Initialize cache if not in an async context
        try:
            asyncio.get_running_loop()
            # Already in async context - cache will be initialized on first use
            self._cache_initialized = False
        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            asyncio.run(self.cache.initialize())
            self._cache_initialized = True

        # Initialize enhancement services via factory (DI pattern)
        self.service_factory = service_factory or EnhancementServiceFactory()
        self.metadata_pipeline = self.service_factory.create_metadata_pipeline(app_config)
        self.lyrics_pipeline = self.service_factory.create_lyrics_pipeline(app_config)

    async def analyze(
        self,
        audio_path: str,
        *,
        force_reprocess: bool = False,
    ) -> SongBundle:
        """Analyze audio file to extract musical features and enhancements (async).

        Returns a SongBundle (v3.0) containing:
        - features: Complete features dict
        - timing: Basic timing information
        - metadata/lyrics/phonemes: Optional enhancements (when enabled)

        Checks cache before reprocessing. Results are saved to cache (global).

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            force_reprocess: If True, skip cache and reprocess

        Returns:
            SongBundle with v3.0 schema

        Example:
            analyzer = AudioAnalyzer(app_config, job_config)
            bundle = await analyzer.analyze("song.mp3")
            tempo = bundle.features["tempo_bpm"]
            beats = bundle.features["beats_s"]
        """
        # Initialize cache if not already initialized (async context)
        if not self._cache_initialized:
            await self.cache.initialize()
            self._cache_initialized = True

        # Check cache (unless forcing reprocess)
        if not force_reprocess:
            cached_bundle = await load_audio_features_async(audio_path, self.cache, SongBundle)
            if cached_bundle:
                logger.debug("Using cached SongBundle")
                return cached_bundle

        start_time_ms = time.perf_counter() * 1000

        # Extract embedded metadata first (fast, needed for genre-aware section detection)
        logger.debug("Extracting embedded metadata for genre detection")
        embedded_metadata = await self._extract_embedded_metadata_fast(audio_path)
        genre = embedded_metadata.genre[0] if embedded_metadata.genre else None

        # Process audio (CPU-bound, run in thread pool) with genre hint
        logger.debug(f"Analyzing audio: {audio_path} (genre={genre})")
        features = await asyncio.to_thread(self._process_audio, audio_path, genre=genre)

        # Build bundle (includes async metadata/lyrics extraction)
        bundle = await self._build_song_bundle(audio_path, features, embedded_metadata)

        # Calculate total compute time
        compute_ms = time.perf_counter() * 1000 - start_time_ms

        # Save to cache (SongBundle format, v3.0) with compute time
        await save_audio_features_async(audio_path, self.cache, bundle, compute_ms=compute_ms)

        logger.debug(f"Audio analysis complete: {compute_ms:.0f}ms")

        return bundle

    def analyze_sync(
        self,
        audio_path: str,
        *,
        force_reprocess: bool = False,
    ) -> SongBundle:
        """Analyze audio synchronously and return SongBundle.

        This is a sync wrapper around async analyze(). Prefer using async analyze() directly
        when in async context.

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            force_reprocess: If True, skip cache and reprocess

        Returns:
            SongBundle with v3.0 schema including metadata

        Example:
            analyzer = AudioAnalyzer(app_config, job_config)
            bundle = analyzer.analyze_sync("song.mp3")
            tempo = bundle.features["tempo_bpm"]
            artist = bundle.metadata.embedded.artist if bundle.metadata else None
        """
        return asyncio.run(self.analyze(audio_path, force_reprocess=force_reprocess))

    async def _extract_embedded_metadata_fast(self, audio_path: str) -> EmbeddedMetadata:
        """Extract embedded metadata quickly (genre, artist, title).

        This is a fast pre-pass before audio analysis to enable genre-aware processing.

        Args:
            audio_path: Path to audio file

        Returns:
            EmbeddedMetadata with genre/artist/title
        """
        try:
            from twinklr.core.audio.metadata.embedded_tags import extract_embedded_metadata

            return await asyncio.to_thread(extract_embedded_metadata, audio_path)
        except Exception as e:
            logger.warning(f"Failed to extract embedded metadata: {e}")
            return EmbeddedMetadata()

    async def _build_song_bundle(
        self, audio_path: str, features: dict[str, Any], embedded_metadata: EmbeddedMetadata
    ) -> SongBundle:
        """Build SongBundle from v2.3 features dict (async).

        Args:
            audio_path: Path to audio file
            features: v2.3 features dict
            embedded_metadata: Pre-extracted embedded metadata (for efficiency)

        Returns:
            SongBundle with v3.0 schema
        """
        # Extract timing from features (with sensible defaults)
        sr = features.get("sr", 22050)
        hop_length = features.get("hop_length", 512)
        duration_s = features.get("duration_s", 0.1)  # Default to 0.1s minimum for validation
        if duration_s <= 0:
            duration_s = 0.1  # Ensure positive for validation
        duration_ms = max(1, int(duration_s * 1000))  # Ensure at least 1ms

        # Generate recording ID (same format as cache keys)
        import hashlib

        fingerprint = f"{audio_path}:{sr}:{hop_length}"
        recording_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]

        # Extract metadata and lyrics in parallel (async)
        # Pass embedded_metadata to avoid re-extracting
        metadata_bundle, lyrics_bundle = await asyncio.gather(
            self._extract_metadata_if_enabled(audio_path, embedded_metadata),
            self._extract_lyrics_if_enabled(audio_path, duration_ms, None),
        )

        # If lyrics needs metadata, re-extract with metadata context
        if (
            lyrics_bundle.stage_status == StageStatus.SKIPPED
            and metadata_bundle.stage_status != StageStatus.SKIPPED
        ):
            lyrics_bundle = await self._extract_lyrics_if_enabled(
                audio_path, duration_ms, metadata_bundle
            )

        # Extract phonemes from timed words (depends on lyrics)
        phoneme_bundle = await self._extract_phonemes_if_enabled(lyrics_bundle, duration_ms)

        # Build bundle
        return SongBundle(
            schema_version="3.0",
            audio_path=audio_path,
            recording_id=recording_id,
            features=features,
            timing=SongTiming(
                sr=sr,
                hop_length=hop_length,
                duration_s=duration_s,
                duration_ms=duration_ms,
            ),
            metadata=metadata_bundle,
            lyrics=lyrics_bundle,
            phonemes=phoneme_bundle,
        )

    async def _extract_metadata_if_enabled(
        self, audio_path: str, embedded_metadata: EmbeddedMetadata | None = None
    ) -> MetadataBundle:
        """Extract metadata if feature is enabled (async).

        Uses pre-initialized metadata pipeline for extraction.

        Args:
            audio_path: Path to audio file
            embedded_metadata: Pre-extracted embedded metadata (optional, for efficiency)

        Returns:
            MetadataBundle (with SKIPPED status if disabled)
        """
        # Check if pipeline was initialized (feature enabled)
        if self.metadata_pipeline is None:
            return MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.SKIPPED,
                embedded=EmbeddedMetadata(),
            )

        # Use pre-initialized pipeline
        try:
            logger.debug(f"Extracting metadata (Phase 3 pipeline) from {audio_path}")
            bundle = await self.metadata_pipeline.extract(
                audio_path, embedded_metadata=embedded_metadata
            )
            return bundle

        except Exception as e:
            logger.warning(f"Metadata pipeline failed for {audio_path}: {e}")
            return MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.FAILED,
                embedded=EmbeddedMetadata(),
                warnings=[f"Metadata pipeline failed: {e!s}"],
            )

    async def _extract_lyrics_if_enabled(
        self,
        audio_path: str,
        duration_ms: int,
        metadata_bundle: MetadataBundle | None,
    ) -> LyricsBundle:
        """Extract lyrics if feature is enabled (async).

        Uses pre-initialized lyrics pipeline for extraction.

        Args:
            audio_path: Path to audio file
            duration_ms: Song duration in milliseconds
            metadata_bundle: Resolved metadata (for artist/title)

        Returns:
            LyricsBundle (with SKIPPED status if disabled)
        """
        # Check if pipeline was initialized (feature enabled)
        if self.lyrics_pipeline is None:
            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.SKIPPED,
            )

        # Use pre-initialized pipeline
        try:
            logger.debug(f"Extracting lyrics (Phase 4 pipeline) from {audio_path}")

            # Extract artist/title from metadata
            artist = None
            title = None
            if metadata_bundle:
                # Try resolved metadata first (best quality)
                if metadata_bundle.resolved and (
                    metadata_bundle.resolved.artist or metadata_bundle.resolved.title
                ):
                    artist = metadata_bundle.resolved.artist
                    title = metadata_bundle.resolved.title
                # Fall back to embedded metadata
                elif metadata_bundle.embedded and (
                    metadata_bundle.embedded.artist or metadata_bundle.embedded.title
                ):
                    artist = metadata_bundle.embedded.artist
                    title = metadata_bundle.embedded.title

            logger.debug(
                f"Lyrics lookup with artist='{artist}', title='{title}' "
                f"(from {'resolved' if metadata_bundle and metadata_bundle.resolved and artist else 'embedded' if artist else 'none'})"
            )

            bundle = await self.lyrics_pipeline.resolve(
                audio_path=audio_path,
                duration_ms=duration_ms,
                artist=artist,
                title=title,
            )
            return bundle

        except Exception as e:
            logger.warning(f"Lyrics pipeline failed for {audio_path}: {e}")
            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.FAILED,
                warnings=[f"Lyrics pipeline failed: {e!s}"],
            )

    async def _extract_phonemes_if_enabled(
        self,
        lyrics_bundle: LyricsBundle,
        duration_ms: int,
    ) -> PhonemeBundle | None:
        """Extract phonemes from timed words if feature is enabled.

        Requires lyrics with timed words (LyricWord list). Runs G2P -> distribution
        -> viseme mapping -> smoothing pipeline via build_phoneme_bundle.

        Args:
            lyrics_bundle: Resolved lyrics (may have timed words).
            duration_ms: Song duration in milliseconds.

        Returns:
            PhonemeBundle if enabled and words available, None otherwise.
        """
        enhancements = self.app_config.audio_processing.enhancements

        if not enhancements.enable_phonemes:
            return None

        # Need timed words for phoneme generation
        words = lyrics_bundle.words if lyrics_bundle else []
        if not words:
            logger.debug("Phoneme pipeline skipped: no timed words available")
            return None

        try:
            logger.debug(
                f"Building phoneme bundle from {len(words)} timed words (duration={duration_ms}ms)"
            )
            bundle = await asyncio.to_thread(
                build_phoneme_bundle,
                duration_ms=duration_ms,
                words=words,
                mapping_version=enhancements.viseme_mapping_version,
                enable_g2p_en=enhancements.phoneme_enable_g2p_fallback,
                min_phoneme_ms=enhancements.phoneme_min_duration_ms,
                vowel_weight=enhancements.phoneme_vowel_weight,
                consonant_weight=enhancements.phoneme_consonant_weight,
                min_hold_ms=enhancements.viseme_min_hold_ms,
                min_burst_ms=enhancements.viseme_min_burst_ms,
                boundary_soften_ms=enhancements.viseme_boundary_soften_ms,
            )
            logger.debug(
                f"Phoneme bundle built: {len(bundle.phonemes)} phonemes, "
                f"{len(bundle.visemes)} visemes, confidence={bundle.confidence:.2f}"
            )
            return bundle

        except Exception as e:
            logger.warning(f"Phoneme pipeline failed: {e}")
            return None

    def _process_audio(self, audio_path: str, genre: str | None = None) -> dict[str, Any]:
        """Process audio file (internal implementation).

        Args:
            audio_path: Path to audio file
            genre: Optional genre hint for section detection

        Returns:
            Feature dictionary
        """
        hop_length = int(self.app_config.audio_processing.hop_length)
        frame_length = int(self.app_config.audio_processing.frame_length)

        # Load audio
        y, sr_raw = librosa.load(audio_path, sr=None, mono=True)
        sr = int(sr_raw)  # Ensure sr is int
        duration = float(len(y)) / float(sr)

        # Handle very short audio
        if duration < 10.0:
            logger.warning(f"Audio too short ({duration:.1f}s) for meaningful analysis")
            return self._minimal_features(audio_path, y, sr, duration)

        # HPSS decomposition - do this first to get onset envelope
        harmonic, percussive = compute_hpss(y)
        onset_env = compute_onset_env(percussive, sr, hop_length=hop_length)

        # Core rhythm analysis - uses onset envelope
        tempo_bpm, beat_frames = compute_beats(onset_env=onset_env, sr=sr, hop_length=hop_length)
        time_sig_result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)
        time_sig_label = time_sig_result["time_signature"]
        # Extract beats_per_bar from time signature (e.g., "4/4" -> 4, "3/4" -> 3)
        beats_per_bar = int(time_sig_label.split("/")[0])

        # Convert beat frames to times
        beats_s = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

        # Detect downbeats - need to extract chroma first for the function
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        downbeat_result = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=beats_per_bar,
        )
        bars_s = [db["time_s"] for db in downbeat_result["downbeats"]]
        downbeats_idx = [db["beat_index"] for db in downbeat_result["downbeats"]]

        # Energy analysis
        energy_result = extract_smoothed_energy(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        rms_norm = energy_result["raw"]
        rms_times_s = energy_result["times_s"]

        builds_drops = detect_builds_and_drops(
            energy_curve=rms_norm,
            times_s=rms_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=tempo_bpm,
        )
        builds = builds_drops["builds"]
        drops = builds_drops["drops"]

        # Spectral analysis
        spectral_features = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        dynamic_features = extract_dynamic_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )

        # Extract numpy arrays for vocals detection before removing _np dict
        spectral_centroid_np = spectral_features["_np"]["centroid_norm"]
        spectral_flatness_np = spectral_features["_np"]["flatness_norm"]

        # Vocal detection - needs spectral features and HPSS components
        # Use numpy arrays extracted earlier (before _np dict removal)
        vocal_result = detect_vocals(
            y_harm=harmonic,
            y_perc=percussive,
            spectral_centroid=spectral_centroid_np,
            spectral_flatness=spectral_flatness_np,
            times_s=np.asarray(spectral_features["times_s"]),
            sr=sr,
        )
        # Extract just the segments list for backward compatibility
        vocal_regions = vocal_result["vocal_segments"]

        # Harmonic analysis (chroma already computed above for downbeat detection)
        key_result = detect_musical_key(y, sr, hop_length=hop_length)
        chords = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
        )
        pitch = extract_pitch_tracking(y, sr, hop_length=hop_length)

        # Structure analysis - pass context for improved detection
        sections = detect_song_sections(
            y,
            sr,
            hop_length=hop_length,
            genre=genre,
            rms_for_energy=rms_norm,
            chroma_cqt=chroma,
            beats_s=beats_s,
            bars_s=bars_s,
            builds=builds,
            drops=drops,
            vocal_segments=vocal_regions,
            chords=chords["chords"],  # Extract chord list from result dict
        )
        tempo_changes = detect_tempo_changes(y, sr, hop_length=hop_length)

        # Tension curve
        tension = compute_tension_curve(
            chroma_cqt=chroma,
            energy_curve=rms_norm,
            spectral_flatness=spectral_features["spectral_flatness"],
            onset_env=onset_env,
            times_s=rms_times_s,
            key_info=key_result,
            sr=sr,
            hop_length=hop_length,
        )

        # Remove _np dicts before final assembly (they contain numpy arrays)
        spectral_features.pop("_np", None)
        dynamic_features.pop("_np", None)

        # Build timeline
        timeline_export = build_timeline_export(
            y=y,
            sr=sr,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=spectral_features["brightness"],
            flatness_norm=spectral_features["spectral_flatness"],
            motion_norm=dynamic_features["motion"],
            chroma_cqt=chroma,
            beats_s=beats_s,
            downbeats_s=bars_s,
            section_bounds_s=sections["boundary_times_s"],
            y_harm=harmonic,
            y_perc=percussive,
        )

        # Assemble results
        features = {
            "schema_version": "2.3",
            "audio_path": audio_path,
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": tempo_bpm,
            "beats_s": beats_s,
            "bars_s": bars_s,
            "time_signature": time_sig_result,  # Full result dict from detect_time_signature
            "assumptions": {
                "time_signature": time_sig_label,
                "beats_per_bar": beats_per_bar,
            },
            "rhythm": {
                "beat_confidence": time_sig_result.get("confidence", 0.0),
                "downbeats": [int(i) for i in downbeats_idx],
            },
            "energy": {
                "rms_norm": rms_norm.tolist() if isinstance(rms_norm, np.ndarray) else rms_norm,
                "times_s": rms_times_s.tolist()
                if isinstance(rms_times_s, np.ndarray)
                else rms_times_s,
                "builds": builds,
                "drops": drops,
            },
            "spectral": spectral_features,
            "dynamics": dynamic_features,
            "vocals": vocal_regions,
            "harmonic": {
                "chroma": chroma.tolist() if isinstance(chroma, np.ndarray) else chroma,
                "key": key_result,
                "chords": chords,
                "pitch": pitch,
            },
            "structure": sections,
            "tempo_analysis": tempo_changes,
            "tension": tension,
            "timeline": timeline_export["timeline"],  # Extract timeline from export result
            "composites": timeline_export["composites"],  # Add composites at top level
        }

        # Validate
        validation_warnings = validate_features(features)
        if validation_warnings:
            logger.debug(f"Feature validation warnings: {validation_warnings}")

        return features

    @staticmethod
    def _minimal_features(
        audio_path: str, y: np.ndarray, sr: int, duration: float
    ) -> dict[str, Any]:
        """Generate minimal features for very short audio.

        Args:
            audio_path: Path to audio file
            y: Audio samples
            sr: Sample rate
            duration: Duration in seconds

        Returns:
            Minimal feature dictionary
        """
        return {
            "schema_version": "2.3",
            "audio_path": audio_path,
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": 0.0,
            "beats_s": [],
            "bars_s": [],
            "energy": {"rms_norm": [], "times_s": []},
            "time_signature": {"time_signature": "4/4", "confidence": 0.0, "method": "default"},
            "assumptions": {"time_signature": "4/4 (default)", "beats_per_bar": 4},
            "rhythm": {"beat_confidence": [], "downbeats": []},
            "spectral": {},
            "dynamics": {},
            "structure": {"sections": [], "boundary_times_s": [0.0, duration]},
            "tempo_analysis": {},
            "key": {"key": "C", "mode": "major", "confidence": 0.0},
            "warnings": ["Audio too short for meaningful analysis"],
        }
