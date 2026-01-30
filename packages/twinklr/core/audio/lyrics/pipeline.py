"""Lyrics resolution pipeline (Phase 4 + Phase 5, async in Phase 8).

Orchestrates stage gating: embedded → synced → plain → whisperx_align → whisperx_transcribe.
"""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.audio.lyrics.embedded import extract_embedded_lyrics, parse_lrc_content
from blinkb0t.core.audio.lyrics.providers.models import LyricsQuery
from blinkb0t.core.audio.lyrics.quality import compute_quality_metrics
from blinkb0t.core.audio.lyrics.whisperx_models import WhisperXConfig
from blinkb0t.core.audio.lyrics.whisperx_service import WhisperXService
from blinkb0t.core.audio.models import StageStatus
from blinkb0t.core.audio.models.lyrics import LyricsBundle, LyricsSource, LyricsSourceKind

logger = logging.getLogger(__name__)


class LyricsPipelineConfig(BaseModel):
    """Configuration for lyrics pipeline."""

    model_config = ConfigDict(extra="forbid")

    require_timed_words: bool = Field(
        default=False, description="Require word-level timing (not just text)"
    )
    min_coverage_pct: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum coverage for quality"
    )
    mismatch_threshold: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Mismatch ratio threshold for warnings"
    )
    whisperx_config: WhisperXConfig = Field(
        default_factory=WhisperXConfig, description="WhisperX configuration"
    )


class LyricsPipeline:
    """Lyrics resolution pipeline (async).

    Stage gating order:
    1. Embedded extraction (LRC sidecar, SYLT, USLT)
    2. Synced lookup (LRCLib) - async (Phase 8)
    3. Plain lookup (Genius) - async (Phase 8)
    4. WhisperX align-only (if require_timed_words and lyrics_text exists)
    5. WhisperX transcribe (if no lyrics or align fails)
    """

    # Base confidence by source (from spec)
    BASE_CONFIDENCE = {
        LyricsSourceKind.EMBEDDED: 0.70,
        LyricsSourceKind.LOOKUP_SYNCED: 0.80,
        LyricsSourceKind.LOOKUP_PLAIN: 0.75,
        LyricsSourceKind.WHISPERX_ALIGN: 0.85,
        LyricsSourceKind.WHISPERX_TRANSCRIBE: 0.80,
    }

    def __init__(
        self,
        *,
        config: LyricsPipelineConfig,
        providers: dict[str, Any],
        whisperx_service: WhisperXService | None = None,
    ):
        """Initialize pipeline.

        Args:
            config: Pipeline configuration
            providers: Dict of provider name -> async client instances
            whisperx_service: Optional WhisperX service for align/transcribe
        """
        self.config = config
        self.providers = providers
        self.whisperx_service = whisperx_service

    async def resolve(
        self,
        *,
        audio_path: str,
        duration_ms: int,
        artist: str | None = None,
        title: str | None = None,
    ) -> LyricsBundle:
        """Resolve lyrics through stage gating (async).

        Args:
            audio_path: Path to audio file
            duration_ms: Song duration in milliseconds
            artist: Artist name for provider lookup
            title: Track title for provider lookup

        Returns:
            LyricsBundle with resolved lyrics and status
        """
        warnings: list[str] = []

        # Stage 1: Try embedded extraction
        text, phrases, words, embed_warnings = extract_embedded_lyrics(audio_path, duration_ms)
        warnings.extend(embed_warnings)

        if text:
            return self._finalize_bundle(
                text=text,
                phrases=phrases,
                words=words,
                source_kind=LyricsSourceKind.EMBEDDED,
                provider_confidence=None,
                duration_ms=duration_ms,
                warnings=warnings,
                provider="embedded",
            )

        # Stage 2: Try synced lookup (if metadata available)
        if artist or title:
            logger.debug(f"Trying synced lookup for artist='{artist}', title='{title}'")
            synced_bundle = await self._try_synced_lookup(
                artist=artist,
                title=title,
                duration_ms=duration_ms,
                warnings=warnings,
            )
            if synced_bundle:
                logger.debug(f"Found synced lyrics from {synced_bundle.source}")
                return synced_bundle

            # Stage 3: Try plain lookup
            logger.debug(f"Trying plain lookup for artist='{artist}', title='{title}'")
            plain_bundle = await self._try_plain_lookup(
                artist=artist,
                title=title,
                duration_ms=duration_ms,
                warnings=warnings,
            )
            if plain_bundle:
                logger.debug(f"Found plain lyrics from {plain_bundle.source}")
                # Check if we need word timing but don't have it
                if self.config.require_timed_words and not plain_bundle.words:
                    # Stage 4: Try WhisperX align to add timing to plain text
                    if self.whisperx_service:
                        align_bundle = self._try_whisperx_align(
                            audio_path=audio_path,
                            lyrics_text=plain_bundle.text or "",
                            duration_ms=duration_ms,
                            warnings=warnings,
                        )
                        if align_bundle:
                            return align_bundle
                # Plain text is sufficient (or align failed)
                return plain_bundle

        # Stage 5: Try WhisperX transcribe (no lyrics from any source)
        if self.whisperx_service:
            transcribe_bundle = self._try_whisperx_transcribe(
                audio_path=audio_path,
                duration_ms=duration_ms,
                warnings=warnings,
            )
            if transcribe_bundle:
                return transcribe_bundle

        # No lyrics found
        logger.debug(
            f"No lyrics found from any source (embedded/synced/plain/whisperx). "
            f"Warnings: {len(warnings)}"
        )
        return LyricsBundle(
            schema_version="1.0.0",
            stage_status=StageStatus.SKIPPED,
            warnings=warnings,
        )

    async def _try_synced_lookup(
        self,
        *,
        artist: str | None,
        title: str | None,
        duration_ms: int,
        warnings: list[str],
    ) -> LyricsBundle | None:
        """Try to get synced lyrics from providers (async).

        Args:
            artist: Artist name
            title: Track title
            duration_ms: Song duration
            warnings: List to append warnings to

        Returns:
            LyricsBundle if found, None otherwise
        """
        lrclib_client = self.providers.get("lrclib")
        if not lrclib_client:
            return None

        try:
            query = LyricsQuery(artist=artist, title=title, duration_ms=duration_ms)
            candidates = await lrclib_client.search(query)

            # Filter to synced candidates and select best
            synced = [c for c in candidates if c.kind == "SYNCED" and c.lrc]
            if not synced:
                return None

            best = max(synced, key=lambda c: c.confidence)

            # Parse LRC content
            phrases = parse_lrc_content(best.lrc, duration_ms=duration_ms)

            text = best.text
            return self._finalize_bundle(
                text=text,
                phrases=phrases,
                words=[],
                source_kind=LyricsSourceKind.LOOKUP_SYNCED,
                provider_confidence=best.confidence,
                duration_ms=duration_ms,
                warnings=warnings,
                provider=best.provider,
                provider_id=best.provider_id,
            )

        except Exception as e:
            logger.warning(f"Synced lookup failed: {e}")
            warnings.append(f"Synced lookup error: {e}")
            return None

    async def _try_plain_lookup(
        self,
        *,
        artist: str | None,
        title: str | None,
        duration_ms: int,
        warnings: list[str],
    ) -> LyricsBundle | None:
        """Try to get plain lyrics from providers (async).

        Args:
            artist: Artist name
            title: Track title
            duration_ms: Song duration
            warnings: List to append warnings to

        Returns:
            LyricsBundle if found, None otherwise
        """
        genius_client = self.providers.get("genius")
        if not genius_client:
            return None

        try:
            query = LyricsQuery(artist=artist, title=title)
            logger.debug(f"Calling Genius API with query: {query}")
            candidates = await genius_client.search(query)
            logger.debug(f"Genius returned {len(candidates)} candidates")

            if not candidates:
                logger.debug("Genius search returned no candidates")
                return None

            # Select best confidence
            best = max(candidates, key=lambda c: c.confidence)
            logger.debug(f"Selected best candidate with confidence {best.confidence}")

            return self._finalize_bundle(
                text=best.text,
                phrases=[],
                words=[],
                source_kind=LyricsSourceKind.LOOKUP_PLAIN,
                provider_confidence=best.confidence,
                duration_ms=duration_ms,
                warnings=warnings,
                provider=best.provider,
                provider_id=best.provider_id,
            )

        except Exception as e:
            import traceback

            logger.error(f"Plain lookup failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            warnings.append(f"Plain lookup error: {e}")
            return None

    def _finalize_bundle(
        self,
        *,
        text: str,
        phrases: list,
        words: list,
        source_kind: str,
        provider_confidence: float | None,
        duration_ms: int,
        warnings: list[str],
        provider: str,
        provider_id: str | None = None,
    ) -> LyricsBundle:
        """Finalize bundle with quality metrics and confidence scoring.

        Args:
            text: Lyrics text
            phrases: Phrase-level timing
            words: Word-level timing
            source_kind: Source type
            provider_confidence: Provider's confidence (if external)
            duration_ms: Song duration
            warnings: Warnings list
            provider: Provider name (if external)
            provider_id: Provider ID (if external)

        Returns:
            Finalized LyricsBundle
        """
        # Compute quality metrics (only if we have words)
        quality = None
        if words:
            quality = compute_quality_metrics(words=words, duration_ms=duration_ms)

        # Compute confidence with penalties
        base_conf = self.BASE_CONFIDENCE.get(source_kind, 0.5)

        # Start with provider confidence if available, otherwise base
        confidence = provider_confidence if provider_confidence is not None else base_conf

        # Apply quality penalties (if quality available)
        if quality:
            # Penalty for low coverage
            if quality.coverage_pct < self.config.min_coverage_pct:
                confidence -= 0.10

            # Penalty for overlap violations (cap at -0.20)
            overlap_penalty = min(quality.overlap_violations * 0.05, 0.20)
            confidence -= overlap_penalty

            # Penalty for out of bounds (cap at -0.20)
            oob_penalty = min(quality.out_of_bounds_violations * 0.05, 0.20)
            confidence -= oob_penalty

            # Penalty for large gaps
            if quality.large_gaps_count > 8:
                confidence -= 0.05

        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        # Build source
        source = LyricsSource(
            kind=source_kind,
            confidence=confidence,
            provider=provider,
            provider_id=provider_id,
        )

        # Determine sufficiency
        is_sufficient = True

        if self.config.require_timed_words:
            # Need timed words with good coverage
            if not words:
                is_sufficient = False
            elif quality and quality.coverage_pct < self.config.min_coverage_pct:
                is_sufficient = False

        # Determine stage status
        # Use OK for success, even if insufficient (but add warnings)
        stage_status = StageStatus.OK
        if not is_sufficient:
            warnings.append("Lyrics do not meet sufficiency requirements")

        return LyricsBundle(
            schema_version="1.0.0",
            stage_status=stage_status,
            text=text,
            phrases=phrases,
            words=words,
            source=source,
            quality=quality,
            warnings=warnings,
        )

    def _try_whisperx_align(
        self,
        *,
        audio_path: str,
        lyrics_text: str,
        duration_ms: int,
        warnings: list[str],
    ) -> LyricsBundle | None:
        """Try WhisperX align-only (add timing to existing lyrics).

        Args:
            audio_path: Path to audio file
            lyrics_text: Reference lyrics text
            duration_ms: Song duration
            warnings: List to append warnings to

        Returns:
            LyricsBundle if successful, None otherwise
        """
        if not self.whisperx_service:
            return None

        try:
            logger.debug(f"WhisperX align: {audio_path}")
            result = self.whisperx_service.align(
                audio_path=audio_path,
                lyrics_text=lyrics_text,
                config=self.config.whisperx_config,
            )

            # Check mismatch ratio
            if result.mismatch_ratio > self.config.mismatch_threshold:
                warnings.append(
                    f"WhisperX align mismatch ratio {result.mismatch_ratio:.3f} "
                    f"exceeds threshold {self.config.mismatch_threshold}"
                )

            # Compute quality metrics
            quality = compute_quality_metrics(words=result.words, duration_ms=duration_ms)

            # Compute confidence with penalties
            base_conf = self.BASE_CONFIDENCE[LyricsSourceKind.WHISPERX_ALIGN]
            confidence = base_conf

            # Mismatch penalty
            if result.mismatch_ratio > self.config.mismatch_threshold:
                confidence -= 0.10

            # Quality penalties
            if quality.coverage_pct < self.config.min_coverage_pct:
                confidence -= 0.10
            overlap_penalty = min(quality.overlap_violations * 0.05, 0.20)
            confidence -= overlap_penalty
            oob_penalty = min(quality.out_of_bounds_violations * 0.05, 0.20)
            confidence -= oob_penalty
            if quality.large_gaps_count > 8:
                confidence -= 0.05

            # Clamp [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            source = LyricsSource(
                kind=LyricsSourceKind.WHISPERX_ALIGN,
                provider="whisperx",
                confidence=confidence,
            )

            # Determine sufficiency
            is_sufficient = True
            if self.config.require_timed_words:
                if not result.words:
                    is_sufficient = False
                elif quality.coverage_pct < self.config.min_coverage_pct:
                    is_sufficient = False

            if not is_sufficient:
                warnings.append("WhisperX align result does not meet sufficiency requirements")

            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.OK,
                text=lyrics_text,  # Original text
                phrases=[],
                words=result.words,
                source=source,
                quality=quality,
                warnings=warnings,
            )

        except Exception as e:
            logger.warning(f"WhisperX align failed: {e}")
            warnings.append(f"WhisperX align error: {e}")
            return None

    def _try_whisperx_transcribe(
        self,
        *,
        audio_path: str,
        duration_ms: int,
        warnings: list[str],
    ) -> LyricsBundle | None:
        """Try WhisperX transcribe (generate lyrics from audio).

        Args:
            audio_path: Path to audio file
            duration_ms: Song duration
            warnings: List to append warnings to

        Returns:
            LyricsBundle if successful, None otherwise
        """
        if not self.whisperx_service:
            return None

        try:
            logger.debug(f"WhisperX transcribe: {audio_path}")
            result = self.whisperx_service.transcribe(
                audio_path=audio_path,
                config=self.config.whisperx_config,
            )

            # Compute quality metrics
            quality = None
            if result.words:
                quality = compute_quality_metrics(words=result.words, duration_ms=duration_ms)

            # Compute confidence with penalties
            base_conf = self.BASE_CONFIDENCE[LyricsSourceKind.WHISPERX_TRANSCRIBE]
            confidence = base_conf

            # Quality penalties (if available)
            if quality:
                if quality.coverage_pct < self.config.min_coverage_pct:
                    confidence -= 0.10
                overlap_penalty = min(quality.overlap_violations * 0.05, 0.20)
                confidence -= overlap_penalty
                oob_penalty = min(quality.out_of_bounds_violations * 0.05, 0.20)
                confidence -= oob_penalty
                if quality.large_gaps_count > 8:
                    confidence -= 0.05

            # Clamp [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            source = LyricsSource(
                kind=LyricsSourceKind.WHISPERX_TRANSCRIBE,
                provider="whisperx",
                confidence=confidence,
            )

            # Determine sufficiency
            is_sufficient = True
            if self.config.require_timed_words:
                if not result.words:
                    is_sufficient = False
                elif quality and quality.coverage_pct < self.config.min_coverage_pct:
                    is_sufficient = False

            if not is_sufficient:
                warnings.append("WhisperX transcribe result does not meet sufficiency requirements")

            return LyricsBundle(
                schema_version="1.0.0",
                stage_status=StageStatus.OK,
                text=result.text,
                phrases=[],
                words=result.words,
                source=source,
                quality=quality,
                warnings=warnings,
            )

        except Exception as e:
            logger.warning(f"WhisperX transcribe failed: {e}")
            warnings.append(f"WhisperX transcribe error: {e}")
            return None
