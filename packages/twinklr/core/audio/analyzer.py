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
from pathlib import Path
import time
from typing import Any

import librosa
import numpy as np

# Import all the analysis modules
from twinklr.core.audio.advanced.tension import compute_tension_curve
from twinklr.core.audio.cache_adapter import (
    AUDIO_FEATURES_CACHE_VERSION,
    audio_analysis_fingerprint,
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
from twinklr.core.audio.mir.sources import (
    DSPSource,
    MIRInput,
    RhythmAnalysis,
    RhythmSource,
    StructureAnalysis,
    StructureSource,
    create_rhythm_source,
    create_structure_source,
)
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
from twinklr.core.audio.rhythm.tempo import detect_tempo_changes
from twinklr.core.audio.spectral.bands import extract_dynamic_features
from twinklr.core.audio.spectral.basic import extract_spectral_features
from twinklr.core.audio.spectral.vocals import detect_vocals
from twinklr.core.audio.stems import (
    StemFeatures,
    StemSeparator,
    StemStatus,
    analyze_stems,
    apply_stem_consumers,
    stem_result_matches_config,
)
from twinklr.core.audio.timeline.builder import build_timeline_export
from twinklr.core.audio.validation.validator import validate_features
from twinklr.core.caching import FSCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.config.paths import resolve_project_root
from twinklr.core.io import RealFileSystem, anchored_path

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
        stem_separator: StemSeparator | None = None,
    ):
        """Initialize audio analyzer with configuration.

        Args:
            app_config: Application configuration (audio processing settings)
            job_config: Job configuration (checkpoint settings)
            service_factory: Optional factory for creating enhancement services (DI)
            stem_separator: Optional source-separation adapter for dependency injection
        """
        self.app_config = app_config
        self.job_config = job_config
        self.stem_separator = stem_separator

        # Initialize async cache
        fs = RealFileSystem()
        cache_root = anchored_path(
            app_config.cache_dir or "data/cache",
            resolve_project_root(app_config),
        )
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

    async def __aenter__(self) -> AudioAnalyzer:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Release enhancement HTTP pools owned by this analyzer."""
        await self.service_factory.aclose()

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

        analysis_identity = audio_analysis_fingerprint(self.app_config.audio_processing)

        # Check cache (unless forcing reprocess)
        cache_version = self._audio_cache_version()
        if not force_reprocess:
            cached_bundle = await load_audio_features_async(
                audio_path,
                self.cache,
                SongBundle,
                step_version=cache_version,
                analysis_identity=analysis_identity,
            )
            if cached_bundle and stem_result_matches_config(
                cached_bundle.features.get("stems", {}),
                self.app_config.audio_processing.enhancements.stems,
            ):
                # If lyrics were skipped when the cache was populated but are now enabled,
                # extract them and refresh the cache so has_lyrics is correct downstream.
                if (
                    self.lyrics_pipeline is not None
                    and cached_bundle.lyrics is not None
                    and cached_bundle.lyrics.stage_status == StageStatus.SKIPPED
                ):
                    logger.debug(
                        "Cached bundle has SKIPPED lyrics but lyrics pipeline is enabled — "
                        "extracting lyrics and refreshing cache"
                    )
                    lyrics_bundle = await self._extract_lyrics_if_enabled(
                        audio_path,
                        cached_bundle.timing.duration_ms,
                        cached_bundle.metadata,
                        cached_bundle.features.get("vocals", []),
                        cached_bundle.features.get("vocal_gate_open"),
                    )
                    cached_bundle = cached_bundle.model_copy(update={"lyrics": lyrics_bundle})
                    await save_audio_features_async(
                        audio_path,
                        self.cache,
                        cached_bundle,
                        step_version=cache_version,
                        analysis_identity=analysis_identity,
                    )

                logger.debug("Using cached SongBundle")
                return cached_bundle

        start_time_ms = time.perf_counter() * 1000

        # Extract embedded metadata first (fast, needed for genre-aware section detection)
        logger.debug("Extracting embedded metadata for genre detection")
        embedded_metadata = await self._extract_embedded_metadata_fast(audio_path)
        genre = embedded_metadata.genre[0] if embedded_metadata.genre else None

        stem_features = await analyze_stems(
            Path(audio_path),
            self.cache,
            self.app_config.audio_processing.enhancements.stems,
            separator=self.stem_separator,
        )

        # Process audio (CPU-bound, run in thread pool) with genre hint
        logger.debug(f"Analyzing audio: {audio_path} (genre={genre})")
        features = await asyncio.to_thread(
            self._process_audio,
            audio_path,
            genre=genre,
            stem_features=stem_features,
        )

        # Build bundle (includes async metadata/lyrics extraction)
        bundle = await self._build_song_bundle(audio_path, features, embedded_metadata)

        # Calculate total compute time
        compute_ms = time.perf_counter() * 1000 - start_time_ms

        # Save to cache (SongBundle format, v3.0) with compute time
        await save_audio_features_async(
            audio_path,
            self.cache,
            bundle,
            step_version=cache_version,
            analysis_identity=analysis_identity,
            compute_ms=compute_ms,
        )

        logger.debug(f"Audio analysis complete: {compute_ms:.0f}ms")

        return bundle

    def _audio_cache_version(self) -> str:
        """Partition SongBundle caches by the configured stem consumer mode."""
        config = self.app_config.audio_processing.enhancements.stems
        mode = config.model_name if config.enabled else "off"
        return f"{AUDIO_FEATURES_CACHE_VERSION}:stems:{mode}"

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
        """Build SongBundle from the v2.4 features dict (async).

        Args:
            audio_path: Path to audio file
            features: v2.4 features dict
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

        # Extract vocal segments for passing to lyrics pipeline
        vocal_segments: list[dict] = features.get("vocals", [])

        # Metadata resolves first: the lyrics pipeline gates LRCLib and Genius —
        # its two highest-priority sources — on having an artist/title. Running
        # the two concurrently hands lyrics no metadata, so those providers are
        # structurally skipped and ASR outranks synced lyrics.
        metadata_bundle = await self._extract_metadata_if_enabled(audio_path, embedded_metadata)

        # Single, metadata-informed lyrics pass
        lyrics_bundle = await self._extract_lyrics_if_enabled(
            audio_path,
            duration_ms,
            metadata_bundle,
            vocal_segments,
            features.get("vocal_gate_open"),
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
            warnings=[str(w) for w in features.get("warnings", [])],
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
            # Carry the embedded tags anyway: they are what lets the lyrics
            # pipeline reach LRCLib/Genius when provider lookup is disabled.
            return MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.SKIPPED,
                embedded=embedded_metadata or EmbeddedMetadata(),
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
        vocal_segments: list[dict] | None = None,
        vocal_gate_open: bool | None = None,
    ) -> LyricsBundle:
        """Extract lyrics if feature is enabled (async).

        Uses pre-initialized lyrics pipeline for extraction.

        Args:
            audio_path: Path to audio file
            duration_ms: Song duration in milliseconds
            metadata_bundle: Resolved metadata (for artist/title)
            vocal_segments: Optional vocal detector segments for vocal_presence_pct
            vocal_gate_open: Whether separated vocals justify WhisperX processing;
                None preserves the full-mix fallback behavior.

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

            resolve_kwargs: dict[str, Any] = {
                "audio_path": audio_path,
                "duration_ms": duration_ms,
                "artist": artist,
                "title": title,
                "vocal_segments": vocal_segments or [],
            }
            if vocal_gate_open is not None:
                resolve_kwargs["vocal_gate_open"] = vocal_gate_open
            bundle = await self.lyrics_pipeline.resolve(
                **resolve_kwargs,
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

    def _process_audio(
        self,
        audio_path: str,
        genre: str | None = None,
        stem_features: StemFeatures | None = None,
    ) -> dict[str, Any]:
        """Process audio file (internal implementation).

        Args:
            audio_path: Path to audio file
            genre: Optional genre hint for section detection
            stem_features: Optional cached source-separation feature result

        Returns:
            Feature dictionary
        """
        hop_length = int(self.app_config.audio_processing.hop_length)
        frame_length = int(self.app_config.audio_processing.frame_length)

        # Load audio
        y, sr_raw = librosa.load(audio_path, sr=None, mono=True)
        sr = int(sr_raw)  # Ensure sr is int
        duration = float(len(y)) / float(sr)
        rhythm_source = create_rhythm_source(self.app_config.audio_processing.rhythm_source)
        structure_source = create_structure_source(
            self.app_config.audio_processing.structure_source
        )

        # Handle very short audio
        if duration < 10.0:
            logger.warning(f"Audio too short ({duration:.1f}s) for meaningful analysis")
            return self._short_audio_features(
                audio_path,
                y,
                sr,
                duration,
                hop_length=hop_length,
                rhythm_source=rhythm_source,
                structure_source=structure_source,
                genre=genre,
                stem_features=stem_features,
            )

        # HPSS decomposition - do this first to get onset envelope
        hpss = compute_hpss(y)
        harmonic, percussive = hpss.harmonic, hpss.percussive
        hpss_separated, hpss_error = hpss.separated, hpss.error
        del hpss  # keeps PERF-18's reclaim of the component arrays effective
        onset_env = compute_onset_env(percussive, sr, hop_length=hop_length)

        # Rhythm sources share the same already-loaded waveform and preprocessing.
        # The selected result becomes the sole beats/bars truth that all later
        # analysis and BeatGrid consumers receive.
        chroma = extract_chroma(y, sr, hop_length=hop_length)
        mir_input = MIRInput(
            audio_path=Path(audio_path),
            audio=y,
            sample_rate=sr,
            hop_length=hop_length,
            onset_envelope=onset_env,
            chroma=chroma,
            genre=genre,
            harmonic_audio=harmonic,
        )
        rhythm_analysis = rhythm_source.analyze_rhythm(mir_input)
        tempo_bpm = rhythm_analysis.tempo_bpm
        beats_s = rhythm_analysis.beats_s
        bars_s = rhythm_analysis.downbeats_s
        beats_per_bar = rhythm_analysis.beats_per_bar
        time_sig_label = f"{beats_per_bar}/4"
        time_sig_result = dict(
            rhythm_analysis.metadata.get(
                "time_signature",
                {
                    "time_signature": time_sig_label,
                    "confidence": rhythm_analysis.beat_confidence,
                    "method": rhythm_analysis.source,
                },
            )
        )
        time_sig_label = str(time_sig_result.get("time_signature", time_sig_label))
        beat_frames = np.asarray(
            librosa.time_to_frames(beats_s, sr=sr, hop_length=hop_length), dtype=int
        )
        downbeats_idx = (
            [
                int(np.argmin(np.abs(np.asarray(beats_s, dtype=np.float64) - downbeat)))
                for downbeat in bars_s
            ]
            if beats_s
            else []
        )
        downbeat_result = dict(rhythm_analysis.metadata.get("downbeat_meta", {}))

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
            beats_per_bar=beats_per_bar,
        )
        builds = builds_drops["builds"]
        drops = builds_drops["drops"]

        # Pre-compute STFT magnitude and RMS once for reuse (PERF-03, PERF-04)
        stft_mag = np.abs(librosa.stft(y, n_fft=frame_length, hop_length=hop_length)).astype(
            np.float32
        )
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0].astype(
            np.float32
        )

        # Spectral analysis
        spectral_features = extract_spectral_features(
            y, sr, hop_length=hop_length, frame_length=frame_length
        )
        dynamic_features = extract_dynamic_features(
            y,
            sr,
            hop_length=hop_length,
            frame_length=frame_length,
            rms_precomputed=rms,
            onset_env=onset_env,
            stft_mag=stft_mag,
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
            hop_length=hop_length,
        )
        active_stems = stem_features or StemFeatures(
            status=StemStatus.DISABLED_FULL_MIX_FALLBACK,
            fallback_reason="Stem analysis was not requested",
        )
        stem_consumers = apply_stem_consumers(
            active_stems,
            full_mix_beat_confidence=rhythm_analysis.beat_confidence,
            beats_s=beats_s,
            full_mix_builds_drops=builds_drops,
            full_mix_vocal_segments=vocal_result["vocal_segments"],
            full_mix_vocal_statistics=vocal_result["statistics"],
            tempo_bpm=tempo_bpm,
            beats_per_bar=beats_per_bar,
        )
        builds = stem_consumers["energy"]["builds"]
        drops = stem_consumers["energy"]["drops"]
        vocal_regions = stem_consumers["vocals"]

        # Harmonic analysis (chroma already computed above for downbeat detection)
        key_result = detect_musical_key(y, sr, hop_length=hop_length, chroma=chroma)
        chords = detect_chords(
            chroma_cqt=chroma,
            beat_frames=beat_frames,
            sr=sr,
            hop_length=hop_length,
        )
        pitch = extract_pitch_tracking(y, sr, hop_length=hop_length)

        # Structure analysis - pass context for improved detection
        # Compute STFT with n_fft=2048 for section detection (separate from dynamic features STFT)
        stft_mag_2048 = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length)).astype(
            np.float32
        )
        structure_input = MIRInput(
            audio_path=Path(audio_path),
            audio=y,
            sample_rate=sr,
            hop_length=hop_length,
            onset_envelope=onset_env,
            chroma=chroma,
            genre=genre,
            harmonic_audio=harmonic,
            rms=np.asarray(rms_norm),
            stft_magnitude=stft_mag_2048,
            builds=builds,
            drops=drops,
            vocal_segments=vocal_regions,
            chords=chords["chords"],
        )
        structure_analysis = structure_source.analyze_structure(structure_input, rhythm_analysis)
        sections = {
            "sections": structure_analysis.sections,
            "boundary_times_s": structure_analysis.boundary_times_s,
            "meta": structure_analysis.metadata,
        }
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
            section_bounds_s=structure_analysis.boundary_times_s,
            y_harm=harmonic,
            y_perc=percussive,
        )

        # Reclaim memory: y, harmonic, percussive no longer needed (PERF-18)
        del y, harmonic, percussive

        # Assemble results
        features = {
            "schema_version": "2.4",
            "audio_path": audio_path,
            "sr": sr,
            "hop_length": hop_length,
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
                "beat_confidence": rhythm_analysis.beat_confidence,
                **stem_consumers["rhythm"],
                "downbeats": [int(i) for i in downbeats_idx],
                "downbeat_meta": {
                    "phase": int(downbeat_result.get("phase", 0)),
                    "phase_confidence": rhythm_analysis.downbeat_confidence,
                },
            },
            "analysis_sources": {
                "rhythm": {
                    "name": rhythm_analysis.source,
                    "version": rhythm_analysis.source_version,
                },
                "structure": {
                    "name": structure_analysis.source,
                    "version": structure_analysis.source_version,
                },
            },
            "energy": {
                "rms_norm": rms_norm.tolist() if isinstance(rms_norm, np.ndarray) else rms_norm,
                "times_s": rms_times_s.tolist()
                if isinstance(rms_times_s, np.ndarray)
                else rms_times_s,
                "builds": builds,
                "drops": drops,
                **stem_consumers["energy"],
            },
            "spectral": spectral_features,
            "dynamics": dynamic_features,
            "vocals": vocal_regions,
            "vocals_statistics": stem_consumers["vocals_statistics"],
            "vocals_source": stem_consumers["vocals_source"],
            "full_mix_vocals": stem_consumers["full_mix_vocals"],
            "full_mix_vocals_statistics": stem_consumers["full_mix_vocals_statistics"],
            "vocal_gate_open": stem_consumers["vocal_gate_open"],
            "stems": stem_consumers["stems"],
            "harmonic": {
                "chroma": chroma.tolist() if isinstance(chroma, np.ndarray) else chroma,
                "key": key_result,
                "chords": chords,
                "pitch": pitch,
                "hpss": {"separated": hpss_separated, "error": hpss_error},
            },
            "structure": sections,
            "tempo_analysis": tempo_changes,
            "tension": tension,
            "timeline": timeline_export["timeline"],  # Extract timeline from export result
            "composites": timeline_export["composites"],  # Add composites at top level
        }

        # Validate. These reach the caller on SongBundle.warnings — a warning nobody
        # can see is not a check.
        analysis_warnings: list[str] = []
        analysis_warnings.extend(active_stems.warnings)
        if not hpss_separated:
            analysis_warnings.append(
                f"HPSS separation failed ({hpss_error}) - harmonic ratios are unreliable"
            )
        analysis_warnings.extend(validate_features(features))
        if analysis_warnings:
            logger.warning(f"Feature validation warnings: {analysis_warnings}")
        features["warnings"] = analysis_warnings

        return features

    @classmethod
    def _short_audio_features(
        cls,
        audio_path: str,
        y: np.ndarray,
        sr: int,
        duration: float,
        *,
        hop_length: int,
        rhythm_source: RhythmSource,
        structure_source: StructureSource,
        genre: str | None,
        stem_features: StemFeatures | None = None,
    ) -> dict[str, Any]:
        """Honor explicit MIR selections without silently substituting short-audio defaults."""
        frame_count = max(1, 1 + len(y) // hop_length)
        inputs = MIRInput(
            audio_path=Path(audio_path),
            audio=y,
            sample_rate=sr,
            hop_length=hop_length,
            onset_envelope=np.zeros(frame_count, dtype=np.float32),
            chroma=np.zeros((12, frame_count), dtype=np.float32),
            genre=genre,
        )
        if rhythm_source.name == DSPSource.name:
            rhythm = RhythmAnalysis(
                tempo_bpm=0.0,
                beats_s=[],
                downbeats_s=[],
                beats_per_bar=4,
                beat_confidence=0.0,
                downbeat_confidence=0.0,
                source=rhythm_source.name,
                source_version=rhythm_source.version,
                metadata={"short_audio": True},
            )
        else:
            rhythm = rhythm_source.analyze_rhythm(inputs)

        if structure_source.name == DSPSource.name:
            structure = StructureAnalysis(
                sections=[],
                boundary_times_s=[0.0, duration],
                source=structure_source.name,
                source_version=structure_source.version,
                metadata={"short_audio": True},
            )
        else:
            structure = structure_source.analyze_structure(inputs, rhythm)

        result = cls._minimal_features(
            audio_path,
            y,
            sr,
            duration,
            stem_features,
            full_mix_beat_confidence=rhythm.beat_confidence,
        )
        result["hop_length"] = hop_length
        stem_rhythm = dict(result["rhythm"])
        result.update(
            {
                "tempo_bpm": rhythm.tempo_bpm,
                "beats_s": rhythm.beats_s,
                "bars_s": rhythm.downbeats_s,
                "assumptions": {
                    "time_signature": f"{rhythm.beats_per_bar}/4 (short audio)",
                    "beats_per_bar": rhythm.beats_per_bar,
                },
                "rhythm": {**stem_rhythm, "downbeats": []},
                "structure": {
                    "sections": structure.sections,
                    "boundary_times_s": structure.boundary_times_s,
                    "meta": structure.metadata,
                },
                "analysis_sources": {
                    "rhythm": {"name": rhythm.source, "version": rhythm.source_version},
                    "structure": {
                        "name": structure.source,
                        "version": structure.source_version,
                    },
                },
            }
        )
        return result

    @staticmethod
    def _minimal_features(
        audio_path: str,
        y: np.ndarray,
        sr: int,
        duration: float,
        stem_features: StemFeatures | None = None,
        *,
        full_mix_beat_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Generate minimal features for very short audio.

        Args:
            audio_path: Path to audio file
            y: Audio samples
            sr: Sample rate
            duration: Duration in seconds
            stem_features: Optional stem-stage status to retain in short-file results

        Returns:
            Minimal feature dictionary
        """
        active_stems = stem_features or StemFeatures(
            status=StemStatus.DISABLED_FULL_MIX_FALLBACK,
            fallback_reason="Stem analysis was not requested",
        )
        stem_consumers = apply_stem_consumers(
            active_stems,
            full_mix_beat_confidence=full_mix_beat_confidence,
            beats_s=[],
            full_mix_builds_drops={"builds": [], "drops": [], "statistics": {}},
            full_mix_vocal_segments=[],
            full_mix_vocal_statistics={},
            tempo_bpm=120.0,
            beats_per_bar=4,
        )
        return {
            "schema_version": "2.4",
            "audio_path": audio_path,
            "sr": sr,
            "duration_s": duration,
            "tempo_bpm": 0.0,
            "beats_s": [],
            "bars_s": [],
            "energy": {
                "rms_norm": [],
                "times_s": [],
                **stem_consumers["energy"],
            },
            "time_signature": {"time_signature": "4/4", "confidence": 0.0, "method": "default"},
            "assumptions": {"time_signature": "4/4 (default)", "beats_per_bar": 4},
            "rhythm": {**stem_consumers["rhythm"], "downbeats": []},
            "spectral": {},
            "dynamics": {},
            "structure": {"sections": [], "boundary_times_s": [0.0, duration]},
            "vocals": stem_consumers["vocals"],
            "vocals_statistics": stem_consumers["vocals_statistics"],
            "vocals_source": stem_consumers["vocals_source"],
            "full_mix_vocals": stem_consumers["full_mix_vocals"],
            "full_mix_vocals_statistics": stem_consumers["full_mix_vocals_statistics"],
            "vocal_gate_open": stem_consumers["vocal_gate_open"],
            "stems": stem_consumers["stems"],
            "analysis_sources": {
                "rhythm": {"name": DSPSource.name, "version": DSPSource.version},
                "structure": {"name": DSPSource.name, "version": DSPSource.version},
            },
            "tempo_analysis": {},
            "key": {"key": "C", "mode": "major", "confidence": 0.0},
            "warnings": ["Audio too short for meaningful analysis"],
        }
