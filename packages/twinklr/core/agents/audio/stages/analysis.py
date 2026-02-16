"""Audio analysis pipeline stage.

Wraps AudioAnalyzer for pipeline execution with caching support.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.audio.models import SongBundle
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class AudioAnalysisStage:
    """Pipeline stage for audio analysis with caching.

    Analyzes audio file using AudioAnalyzer, extracting tempo, structure,
    and musical features. Results are cached for subsequent runs.

    Input: str (audio file path)
    Output: SongBundle

    Example:
        >>> stage = AudioAnalysisStage()
        >>> result = await stage.execute(audio_path, context)
        >>> if result.success:
        ...     bundle = result.output
        ...     print(f"Duration: {bundle.timing.duration_ms}ms")
    """

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "audio_analysis"

    async def execute(
        self,
        input: str,
        context: PipelineContext,
    ) -> StageResult[SongBundle]:
        """Analyze audio file.

        Args:
            input: Path to audio file
            context: Pipeline context with app_config and job_config

        Returns:
            StageResult containing SongBundle with analysis results

        Side Effects:
            - Stores "has_lyrics" boolean in context.state
            - Adds "audio_duration_ms" to context.metrics
            - Adds "tempo_bpm" to context.metrics
        """
        from twinklr.core.audio.analyzer import AudioAnalyzer
        from twinklr.core.pipeline.result import failure_result, success_result

        try:
            logger.debug(f"Analyzing audio: {input}")

            # Create analyzer with configs from context
            analyzer = AudioAnalyzer(context.app_config, context.job_config)

            # Analyze with caching (force_reprocess=False by default)
            bundle = await analyzer.analyze(input, force_reprocess=False)

            validation_error = self._validate_meaningful_features(bundle)
            if validation_error is not None:
                logger.error("Audio analysis rejected: %s", validation_error)
                return failure_result(validation_error, stage_name=self.name)

            # Store state for downstream stages
            has_lyrics = bool(
                bundle.lyrics
                and (
                    bundle.lyrics.text is not None
                    or len(bundle.lyrics.words) > 0
                    or len(bundle.lyrics.phrases) > 0
                )
            )
            beats_per_bar_raw = bundle.features.get("assumptions", {}).get("beats_per_bar", 4)
            beats_per_bar = int(beats_per_bar_raw) if isinstance(beats_per_bar_raw, int) else 4
            context.set_state("has_lyrics", has_lyrics)
            context.set_state("audio_bundle", bundle)
            context.set_state("beats_per_bar", beats_per_bar)

            # Track metrics for monitoring
            context.add_metric("audio_duration_ms", bundle.timing.duration_ms)
            tempo = bundle.features.get("tempo_bpm")
            if tempo is not None:
                context.add_metric("tempo_bpm", tempo)

            logger.debug(
                f"Audio analysis complete: {bundle.timing.duration_ms / 1000:.1f}s, "
                f"{tempo} BPM, lyrics={'yes' if has_lyrics else 'no'}"
            )

            return success_result(bundle, stage_name=self.name)

        except Exception as e:
            logger.exception("Audio analysis failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    @staticmethod
    def _validate_meaningful_features(bundle: SongBundle) -> str | None:
        """Validate analysis output is usable for choreography rendering."""
        features = bundle.features
        tempo_raw = features.get("tempo_bpm")
        beats_raw = features.get("beats_s")

        if not isinstance(tempo_raw, (int, float)) or float(tempo_raw) <= 0.0:
            return (
                "Audio analysis did not produce meaningful timing features: tempo_bpm must be > 0.0"
            )

        if not isinstance(beats_raw, list) or len(beats_raw) == 0:
            return "Audio analysis did not produce meaningful timing features: beats_s is empty"

        return None
