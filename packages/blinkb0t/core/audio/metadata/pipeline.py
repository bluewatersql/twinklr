"""Metadata pipeline orchestration (Phase 3, async in Phase 8).

Orchestrates the full metadata extraction pipeline:
1. Embedded metadata extraction
2. Fingerprinting (chromaprint)
3. AcoustID lookup (async)
4. MusicBrainz lookup (async)
5. Metadata merging
"""

import asyncio
import datetime
import hashlib
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from blinkb0t.core.audio.metadata.embedded_tags import extract_embedded_metadata
from blinkb0t.core.audio.metadata.fingerprint import (
    ChromaprintError,
    compute_chromaprint_fingerprint,
)
from blinkb0t.core.audio.metadata.merge import merge_metadata
from blinkb0t.core.audio.models import MetadataBundle
from blinkb0t.core.audio.models.enums import StageStatus
from blinkb0t.core.audio.models.metadata import (
    EmbeddedMetadata,
    FingerprintInfo,
    MetadataCandidate,
    ResolvedMBIDs,
)

logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    """Configuration for metadata pipeline.

    Args:
        enable_acoustid: Enable AcoustID fingerprint lookup
        enable_musicbrainz: Enable MusicBrainz MBID lookup
        chromaprint_timeout_s: Timeout for chromaprint computation
    """

    model_config = ConfigDict(extra="forbid")

    enable_acoustid: bool = True
    enable_musicbrainz: bool = True
    chromaprint_timeout_s: float = 30.0


class MetadataPipeline:
    """Metadata extraction pipeline (async).

    Orchestrates multi-stage metadata extraction:
    1. Extract embedded metadata from audio file
    2. Compute audio fingerprint (hash + chromaprint)
    3. Query AcoustID (if fingerprint available) - async
    4. Query MusicBrainz (if MBID available) - async with parallelization
    5. Merge all candidates with embedded

    Error Handling:
        - Embedded extraction failure → FAILED status, empty embedded
        - Fingerprint errors → warning, continue without fingerprint
        - Provider errors → warning, continue without that provider
        - Merge errors → warning, use embedded as fallback

    Args:
        config: Pipeline configuration
        acoustid_client: Async AcoustID API client
        musicbrainz_client: Async MusicBrainz API client

    Example:
        >>> pipeline = MetadataPipeline(config, acoustid, musicbrainz)
        >>> bundle = await pipeline.extract("/path/to/audio.mp3")
        >>> print(bundle.resolved.title, bundle.resolved.confidence)
    """

    def __init__(
        self,
        *,
        config: PipelineConfig,
        acoustid_client: Any,
        musicbrainz_client: Any,
    ):
        """Initialize metadata pipeline.

        Args:
            config: Pipeline configuration
            acoustid_client: AcoustID API client
            musicbrainz_client: MusicBrainz API client
        """
        self.config = config
        self.acoustid_client = acoustid_client
        self.musicbrainz_client = musicbrainz_client

    async def extract(self, audio_path: str) -> MetadataBundle:
        """Extract metadata from audio file (async).

        Orchestrates full pipeline:
        1. Embedded metadata
        2. Fingerprinting
        3. Provider lookups (async, parallel MusicBrainz)
        4. Merge

        Args:
            audio_path: Path to audio file

        Returns:
            MetadataBundle with merged metadata
        """
        warnings: list[str] = []
        provenance: dict[str, Any] = {
            "pipeline_version": "4.0.0",  # Phase 8: async
            "extracted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Stage 1: Extract embedded metadata
        try:
            logger.debug(f"Extracting embedded metadata from {audio_path}")
            embedded = extract_embedded_metadata(audio_path)
            stage_status = StageStatus.OK
        except Exception as e:
            logger.warning(f"Embedded metadata extraction failed: {e}")
            embedded = EmbeddedMetadata()
            stage_status = StageStatus.FAILED
            warnings.append(f"Embedded metadata extraction failed: {str(e)}")

        # Stage 2: Compute fingerprint
        fingerprint = self._compute_fingerprint(audio_path, warnings)

        # Stage 3: Query providers (async - Phase 8)
        candidates: list[MetadataCandidate] = []

        # Query AcoustID (if fingerprint available)
        if (
            self.config.enable_acoustid
            and fingerprint is not None
            and fingerprint.chromaprint_fingerprint is not None
        ):
            acoustid_candidates = await self._query_acoustid(fingerprint, warnings)
            candidates.extend(acoustid_candidates)

        # Query MusicBrainz (if MBID available from AcoustID) - parallel (Phase 8)
        if self.config.enable_musicbrainz:
            # Collect MBIDs to query
            mbids_to_query = []
            for candidate in candidates:
                if candidate.provider == "acoustid" and candidate.mbids.recording_mbid:
                    mbids_to_query.append(candidate.mbids.recording_mbid)

            # Query MusicBrainz in parallel for all MBIDs
            if mbids_to_query:
                mb_tasks = [self._query_musicbrainz(mbid, warnings) for mbid in mbids_to_query]
                mb_results = await asyncio.gather(*mb_tasks)

                # Add successful results
                for mb_candidate in mb_results:
                    if mb_candidate:
                        # Avoid duplicate MusicBrainz entries (but allow MB + AcoustID with same MBID)
                        if not any(
                            c.provider == "musicbrainz"
                            and c.mbids.recording_mbid == mb_candidate.mbids.recording_mbid
                            for c in candidates
                        ):
                            candidates.append(mb_candidate)

        # Stage 4: Merge metadata
        resolved = self._merge_metadata(embedded, candidates, warnings)

        # Build bundle
        return MetadataBundle(
            schema_version="3.0.0",
            stage_status=stage_status,
            embedded=embedded,
            fingerprint=fingerprint,
            candidates=candidates,
            resolved=resolved,
            warnings=warnings,
            provenance=provenance,
        )

    def _compute_fingerprint(self, audio_path: str, warnings: list[str]) -> FingerprintInfo | None:
        """Compute audio fingerprint.

        Computes both:
        - Basic audio fingerprint (file hash)
        - Chromaprint fingerprint (for AcoustID)

        Args:
            audio_path: Path to audio file
            warnings: List to append warnings to

        Returns:
            FingerprintInfo or None if basic hash computation fails
        """
        try:
            # Compute basic file hash
            audio_fingerprint = compute_file_hash(audio_path)
        except Exception as e:
            logger.warning(f"File hash computation failed: {e}")
            warnings.append(f"Fingerprint computation failed: {str(e)}")
            return None

        # Compute chromaprint (only if AcoustID is enabled)
        chromaprint_fingerprint = None
        chromaprint_duration_s = None
        chromaprint_duration_bucket = None

        if self.config.enable_acoustid:
            try:
                fingerprint, duration = compute_chromaprint_fingerprint(
                    audio_path, timeout_s=self.config.chromaprint_timeout_s
                )
                chromaprint_fingerprint = fingerprint
                chromaprint_duration_s = duration
                chromaprint_duration_bucket = round(duration, 1)  # Bucket to 0.1s
            except ChromaprintError as e:
                logger.warning(f"Chromaprint fingerprint failed: {e}")
                warnings.append(f"Chromaprint fingerprint failed: {str(e)}")
            except Exception as e:
                logger.warning(f"Chromaprint fingerprint failed: {e}")
                warnings.append(f"Chromaprint fingerprint failed: {str(e)}")

        return FingerprintInfo(
            audio_fingerprint=audio_fingerprint,
            chromaprint_fingerprint=chromaprint_fingerprint,
            chromaprint_duration_s=chromaprint_duration_s,
            chromaprint_duration_bucket=chromaprint_duration_bucket,
        )

    async def _query_acoustid(
        self, fingerprint: FingerprintInfo, warnings: list[str]
    ) -> list[MetadataCandidate]:
        """Query AcoustID with fingerprint (async).

        Args:
            fingerprint: Fingerprint info
            warnings: List to append warnings to

        Returns:
            List of candidates from AcoustID
        """
        try:
            logger.debug("Querying AcoustID (async)")
            response = await self.acoustid_client.lookup(
                fingerprint=fingerprint.chromaprint_fingerprint,
                duration_s=fingerprint.chromaprint_duration_s or 0.0,
            )

            candidates = []
            for result in response.results:
                candidate = MetadataCandidate(
                    provider="acoustid",
                    provider_id=result.id,
                    score=result.score,
                    title=result.title,
                    artist=", ".join(result.artists) if result.artists else None,
                    duration_ms=result.duration_ms,
                    mbids=ResolvedMBIDs(
                        recording_mbid=result.recording_mbid,
                        release_mbid=result.release_mbid,
                    ),
                    acoustid_id=result.id,
                )
                candidates.append(candidate)

            logger.debug(f"AcoustID returned {len(candidates)} candidates")
            return candidates

        except Exception as e:
            logger.warning(f"AcoustID lookup failed: {e}")
            warnings.append(f"AcoustID lookup failed: {str(e)}")
            return []

    async def _query_musicbrainz(self, mbid: str, warnings: list[str]) -> MetadataCandidate | None:
        """Query MusicBrainz by MBID (async).

        Args:
            mbid: MusicBrainz recording ID
            warnings: List to append warnings to

        Returns:
            MetadataCandidate or None if failed
        """
        try:
            logger.debug(f"Querying MusicBrainz for {mbid} (async)")
            recording = await self.musicbrainz_client.lookup_recording(mbid=mbid)

            # Use first release if available
            album = None
            release_mbid = None
            if recording.releases:
                album = recording.releases[0].title
                release_mbid = recording.releases[0].id

            candidate = MetadataCandidate(
                provider="musicbrainz",
                provider_id=recording.id,
                score=0.98,  # MusicBrainz is authoritative
                title=recording.title,
                artist=", ".join(recording.artists) if recording.artists else None,
                album=album,
                duration_ms=recording.length_ms,
                mbids=ResolvedMBIDs(
                    recording_mbid=recording.id,
                    release_mbid=release_mbid,
                ),
                isrc=recording.isrc,
            )

            logger.debug("MusicBrainz lookup succeeded")
            return candidate

        except Exception as e:
            logger.warning(f"MusicBrainz lookup failed for {mbid}: {e}")
            warnings.append(f"MusicBrainz lookup failed: {str(e)}")
            return None

    def _merge_metadata(
        self,
        embedded: EmbeddedMetadata,
        candidates: list[MetadataCandidate],
        warnings: list[str],
    ) -> Any:
        """Merge embedded and provider metadata.

        Args:
            embedded: Embedded metadata
            candidates: Provider candidates
            warnings: List to append warnings to

        Returns:
            ResolvedMetadata
        """
        try:
            logger.debug(f"Merging embedded with {len(candidates)} candidates")
            from blinkb0t.core.audio.metadata.merge import MergeConfig

            config = MergeConfig()
            resolved = merge_metadata(embedded, candidates, config=config, ref_duration_ms=None)

            # Warn if low confidence
            if resolved and resolved.confidence < 0.55:
                warnings.append(f"Low confidence merged metadata: {resolved.confidence:.2f}")

            return resolved

        except Exception as e:
            logger.warning(f"Metadata merge failed: {e}")
            warnings.append(f"Metadata merge failed: {str(e)}")

            # Fallback to embedded as resolved
            from blinkb0t.core.audio.metadata.merge import MergeConfig

            config = MergeConfig()
            return merge_metadata(embedded, [], config=config, ref_duration_ms=None)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file.

    Args:
        file_path: Path to file

    Returns:
        Hex-encoded SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
