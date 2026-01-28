"""Audio analyzer - extracts musical features from audio files.

This module provides the AudioAnalyzer class which replaces the old
process_song() module function. It follows the manager pattern where
configuration is provided at initialization.

Example:
    analyzer = AudioAnalyzer(app_config, job_config)
    features = analyzer.analyze("song.mp3")
"""

from __future__ import annotations

import logging
from typing import Any

import librosa
import numpy as np

from blinkb0t.core.api.audio.acoustid import AcoustIDClient
from blinkb0t.core.api.audio.musicbrainz import MusicBrainzClient
from blinkb0t.core.api.http import ApiClient, HttpClientConfig

# Import all the analysis modules
from blinkb0t.core.audio.advanced.tension import compute_tension_curve
from blinkb0t.core.audio.cache import (
    load_cached_features,
    save_cached_features,
)
from blinkb0t.core.audio.energy.builds_drops import detect_builds_and_drops
from blinkb0t.core.audio.energy.multiscale import extract_smoothed_energy
from blinkb0t.core.audio.harmonic.chords import detect_chords
from blinkb0t.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from blinkb0t.core.audio.harmonic.key import detect_musical_key, extract_chroma
from blinkb0t.core.audio.harmonic.pitch import extract_pitch_tracking
from blinkb0t.core.audio.lyrics.pipeline import LyricsPipeline, LyricsPipelineConfig
from blinkb0t.core.audio.lyrics.providers.genius import GeniusClient
from blinkb0t.core.audio.lyrics.providers.lrclib import LRCLibClient
from blinkb0t.core.audio.metadata.pipeline import MetadataPipeline, PipelineConfig
from blinkb0t.core.audio.models import LyricsBundle, MetadataBundle, SongBundle, SongTiming
from blinkb0t.core.audio.models.enums import StageStatus
from blinkb0t.core.audio.models.metadata import EmbeddedMetadata
from blinkb0t.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
)
from blinkb0t.core.audio.rhythm.tempo import detect_tempo_changes
from blinkb0t.core.audio.spectral.bands import extract_dynamic_features
from blinkb0t.core.audio.spectral.basic import extract_spectral_features
from blinkb0t.core.audio.spectral.vocals import detect_vocals
from blinkb0t.core.audio.structure.sections import detect_song_sections
from blinkb0t.core.audio.timeline.builder import build_timeline_export
from blinkb0t.core.audio.utils import to_simple_dict
from blinkb0t.core.audio.validation.validator import validate_features
from blinkb0t.core.config.models import AppConfig, JobConfig
from blinkb0t.core.utils.checkpoint import CheckpointManager, CheckpointType

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

    def __init__(self, app_config: AppConfig, job_config: JobConfig):
        """Initialize audio analyzer with configuration.

        Args:
            app_config: Application configuration (audio processing settings)
            job_config: Job configuration (checkpoint settings)
        """
        self.app_config = app_config
        self.job_config = job_config
        self.checkpoint_manager = CheckpointManager(job_config=job_config)

    def analyze(
        self,
        audio_path: str,
        *,
        force_reprocess: bool = False,
    ) -> SongBundle:
        """Analyze audio file to extract musical features and enhancements.

        Returns a SongBundle (v3.0) containing:
        - features: Complete v2.3 features dict (backward compatible)
        - timing: Basic timing information
        - metadata/lyrics/phonemes: Optional enhancements (when enabled)

        Checks checkpoint and cache before reprocessing. Results are saved
        to both checkpoint (per-job) and cache (global).

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            force_reprocess: If True, skip cache and reprocess

        Returns:
            SongBundle with v3.0 schema

        Example:
            analyzer = AudioAnalyzer(app_config, job_config)
            bundle = analyzer.analyze("song.mp3")
            tempo = bundle.features["tempo_bpm"]
            beats = bundle.features["beats_s"]

        Note:
            For backward compatibility, use analyze_dict() to get v2.3 dict.
        """
        # Check checkpoint first (v2.3 dict format for now)
        checkpoint = self.checkpoint_manager.read_checkpoint(CheckpointType.AUDIO)
        if checkpoint:
            logger.debug("Using checkpointed features")
            return self._build_song_bundle(audio_path, checkpoint)

        # Check cache (unless forcing reprocess)
        if not force_reprocess:
            cached = load_cached_features(audio_path, "features", app_config=self.app_config)
            if cached:
                logger.debug("Using cached features")
                self.checkpoint_manager.write_checkpoint(CheckpointType.AUDIO, cached)
                return self._build_song_bundle(audio_path, cached)

        # Process audio
        logger.debug(f"Analyzing audio: {audio_path}")
        features = self._process_audio(audio_path)

        # Save to cache and checkpoint (v2.3 dict format for now)
        save_cached_features(audio_path, "features", features, app_config=self.app_config)
        self.checkpoint_manager.write_checkpoint(CheckpointType.AUDIO, features)

        return self._build_song_bundle(audio_path, features)

    def analyze_dict(
        self,
        audio_path: str,
        *,
        force_reprocess: bool = False,
    ) -> dict[str, Any]:
        """Analyze audio and return v2.3 dict format (backward compatibility).

        This method provides backward compatibility for code expecting the
        old v2.3 dict format. It calls analyze() and extracts the features dict.

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)
            force_reprocess: If True, skip cache and reprocess

        Returns:
            v2.3 features dict (same format as old analyze() method)

        Example:
            analyzer = AudioAnalyzer(app_config, job_config)
            features = analyzer.analyze_dict("song.mp3")  # Returns dict
            tempo = features["tempo_bpm"]

        TODO: Technical debt - Remove after agent pipeline migrated to SongBundle.
        """
        bundle = self.analyze(audio_path, force_reprocess=force_reprocess)
        return to_simple_dict(bundle)

    def _build_song_bundle(self, audio_path: str, features: dict[str, Any]) -> SongBundle:
        """Build SongBundle from v2.3 features dict.

        Args:
            audio_path: Path to audio file
            features: v2.3 features dict

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

        # Extract metadata if enabled (Phase 2)
        metadata_bundle = self._extract_metadata_if_enabled(audio_path)

        # Extract lyrics if enabled (Phase 4)
        lyrics_bundle = self._extract_lyrics_if_enabled(audio_path, duration_ms, metadata_bundle)

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
            metadata=metadata_bundle,  # Phase 2
            lyrics=lyrics_bundle,  # Phase 4
            phonemes=None,  # Phase 6+
        )

    def _extract_metadata_if_enabled(self, audio_path: str) -> MetadataBundle:
        """Extract metadata if feature is enabled (Phase 3).

        Uses the metadata pipeline to orchestrate:
        1. Embedded metadata extraction
        2. Fingerprinting (if enabled)
        3. Provider lookups (AcoustID, MusicBrainz)
        4. Metadata merging

        Args:
            audio_path: Path to audio file

        Returns:
            MetadataBundle (with SKIPPED status if disabled)
        """
        # Check feature flag
        enable_metadata = self.app_config.audio_processing.enhancements.enable_metadata

        if not enable_metadata:
            # Return bundle with SKIPPED status
            return MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.SKIPPED,
                embedded=EmbeddedMetadata(),
            )

        # Phase 3: Use metadata pipeline
        try:
            logger.debug(f"Extracting metadata (Phase 3 pipeline) from {audio_path}")

            # Initialize API clients if needed
            acoustid_client = None
            musicbrainz_client = None

            if (
                self.app_config.audio_processing.enhancements.enable_acoustid
                or self.app_config.audio_processing.enhancements.enable_musicbrainz
            ):
                # Create HTTP client for API calls
                # Note: base_url is required but unused since clients specify full URLs
                http_config = HttpClientConfig(base_url="http://localhost")
                http_client = ApiClient(config=http_config)

                # Initialize AcoustID client if enabled
                if self.app_config.audio_processing.enhancements.enable_acoustid:
                    acoustid_api_key = (
                        self.app_config.audio_processing.enhancements.acoustid_api_key
                    )
                    if acoustid_api_key:
                        acoustid_client = AcoustIDClient(
                            api_key=acoustid_api_key,
                            http_client=http_client,
                        )
                    else:
                        logger.warning(
                            "AcoustID enabled but no API key provided (ACOUSTID_API_KEY)"
                        )

                # Initialize MusicBrainz client if enabled
                if self.app_config.audio_processing.enhancements.enable_musicbrainz:
                    # MusicBrainz requires user agent for rate limiting
                    user_agent = "BlinkB0t/3.0 (https://github.com/blinkb0t)"
                    musicbrainz_client = MusicBrainzClient(
                        http_client=http_client,
                        user_agent=user_agent,
                    )

            # Create pipeline config
            pipeline_config = PipelineConfig(
                enable_acoustid=self.app_config.audio_processing.enhancements.enable_acoustid,
                enable_musicbrainz=self.app_config.audio_processing.enhancements.enable_musicbrainz,
            )

            # Create and run pipeline
            pipeline = MetadataPipeline(
                config=pipeline_config,
                acoustid_client=acoustid_client,
                musicbrainz_client=musicbrainz_client,
            )

            bundle = pipeline.extract(audio_path)
            return bundle

        except Exception as e:
            logger.warning(f"Metadata pipeline failed for {audio_path}: {e}")
            return MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.FAILED,
                embedded=EmbeddedMetadata(),
                warnings=[f"Metadata pipeline failed: {str(e)}"],
            )

    def _extract_lyrics_if_enabled(
        self,
        audio_path: str,
        duration_ms: int,
        metadata_bundle: MetadataBundle,
    ) -> LyricsBundle:
        """Extract lyrics if feature is enabled (Phase 4).

        Uses the lyrics pipeline to orchestrate:
        1. Embedded lyrics extraction (LRC sidecar, SYLT, USLT)
        2. Synced lyrics lookup (LRCLib) if enabled
        3. Plain lyrics lookup (Genius) if enabled

        Args:
            audio_path: Path to audio file
            duration_ms: Song duration in milliseconds
            metadata_bundle: Resolved metadata (for artist/title)

        Returns:
            LyricsBundle (with SKIPPED status if disabled)
        """
        # Check feature flag
        enable_lyrics = self.app_config.audio_processing.enhancements.enable_lyrics

        if not enable_lyrics:
            # Return bundle with SKIPPED status
            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.SKIPPED,
            )

        # Phase 4: Use lyrics pipeline
        try:
            logger.debug(f"Extracting lyrics (Phase 4 pipeline) from {audio_path}")

            # Initialize provider clients if enabled
            providers: dict[str, Any] = {}

            if self.app_config.audio_processing.enhancements.enable_lyrics_lookup:
                # Create HTTP client for API calls
                # Note: base_url is required but unused since clients specify full URLs
                http_config = HttpClientConfig(base_url="http://localhost")
                http_client = ApiClient(config=http_config)

                # LRCLib (always available, no API key needed)
                providers["lrclib"] = LRCLibClient(http_client=http_client)

                # Genius (requires API key)
                genius_token = self.app_config.audio_processing.enhancements.genius_access_token
                if genius_token:
                    providers["genius"] = GeniusClient(
                        http_client=http_client,
                        access_token=genius_token,
                    )
                else:
                    logger.debug("Genius provider skipped (no GENIUS_ACCESS_TOKEN provided)")

            # Create pipeline config
            pipeline_config = LyricsPipelineConfig(
                require_timed_words=self.app_config.audio_processing.enhancements.lyrics_require_timed,
                min_coverage_pct=self.app_config.audio_processing.enhancements.lyrics_min_coverage,
            )

            # Create and run pipeline
            pipeline = LyricsPipeline(config=pipeline_config, providers=providers)

            # Extract artist/title from metadata
            artist = None
            title = None
            if metadata_bundle.resolved:
                artist = metadata_bundle.resolved.artist
                title = metadata_bundle.resolved.title
            elif metadata_bundle.embedded.artist or metadata_bundle.embedded.title:
                artist = metadata_bundle.embedded.artist
                title = metadata_bundle.embedded.title

            bundle = pipeline.resolve(
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
                warnings=[f"Lyrics pipeline failed: {str(e)}"],
            )

    def _process_audio(self, audio_path: str) -> dict[str, Any]:
        """Process audio file (internal implementation).

        Args:
            audio_path: Path to audio file

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
            logger.warning(f"Feature validation warnings: {validation_warnings}")

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
