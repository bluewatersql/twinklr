"""Metadata merge policy (Phase 3).

Deterministic scoring and merging of embedded metadata + provider candidates.
"""

import logging
import re

from pydantic import BaseModel, Field

from twinklr.core.audio.models.metadata import (
    EmbeddedMetadata,
    MetadataCandidate,
    ResolvedMBIDs,
    ResolvedMetadata,
)

logger = logging.getLogger(__name__)


class MergeConfig(BaseModel):
    """Metadata merge configuration."""

    merge_policy_version: str = "1.0"
    provider_precedence: list[str] = Field(default_factory=lambda: ["musicbrainz", "acoustid"])
    min_confidence_warn: float = 0.55


def normalize_text(s: str | None) -> str:
    """Normalize text for similarity comparison.

    Args:
        s: Text to normalize

    Returns:
        Normalized text (lowercase, stripped, collapsed whitespace, no punctuation)
    """
    if s is None:
        return ""

    # Lowercase
    s = s.lower()

    # Remove punctuation
    s = re.sub(r"[^\w\s]", "", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)

    # Strip
    s = s.strip()

    return s


def token_jaccard(a: str | None, b: str | None) -> float:
    """Compute Jaccard similarity of whitespace tokens.

    Args:
        a: First string
        b: Second string

    Returns:
        Jaccard similarity (0-1), or 0.0 if either is missing (no information)
    """
    # Normalize both strings
    norm_a = normalize_text(a)
    norm_b = normalize_text(b)

    # Handle any empty/None (no information, don't reward)
    if not norm_a or not norm_b:
        return 0.0

    # Tokenize
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())

    # Jaccard = |intersection| / |union|
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    if not union:
        return 0.0

    return len(intersection) / len(union)


def duration_similarity(candidate_ms: int | None, ref_ms: int | None) -> float:
    """Compute duration similarity (0-1 scale).

    Args:
        candidate_ms: Candidate duration in milliseconds
        ref_ms: Reference duration in milliseconds

    Returns:
        Duration similarity (0-1)
    """
    # If either is missing, return 0.5 (neutral, can't compare)
    if candidate_ms is None or ref_ms is None:
        return 0.5

    # Compute delta in seconds
    delta_s = abs(candidate_ms - ref_ms) / 1000.0

    # Similarity = 1 - min(delta_s, 6) / 6
    # Max penalty at 6 seconds difference
    sim = max(0.0, 1.0 - min(delta_s, 6.0) / 6.0)

    return sim


def is_generic_title(title: str | None) -> bool:
    """Check if title is generic (e.g., 'track 1', 'audio 5').

    Args:
        title: Title string

    Returns:
        True if generic
    """
    if title is None:
        return True

    norm = normalize_text(title)

    # Check for patterns: "track \\d+" or "audio \\d+"
    if re.match(r"^track\s+\d+$", norm):
        return True
    if re.match(r"^audio\s+\d+$", norm):
        return True

    return False


def is_generic_artist(artist: str | None) -> bool:
    """Check if artist is generic (e.g., 'unknown', 'unknown artist').

    Args:
        artist: Artist string

    Returns:
        True if generic
    """
    if artist is None:
        return True

    norm = normalize_text(artist)

    # Check for exact matches
    if norm in ("unknown", "unknown artist"):
        return True

    return False


def score_candidate(
    candidate: MetadataCandidate,
    *,
    embedded: EmbeddedMetadata,
    ref_duration_ms: int | None,
    config: MergeConfig,
) -> float:
    """Score candidate against embedded metadata.

    Scoring formula (deterministic):
    - 0.40 * provider_weight (musicbrainz=1.0, acoustid=0.9)
    - 0.20 * title_similarity (token Jaccard)
    - 0.20 * artist_similarity (token Jaccard)
    - 0.15 * duration_similarity
    - 0.05 * stable_id_bonus (MBID +0.10, ISRC +0.05, release MBID +0.03)

    Args:
        candidate: Metadata candidate to score
        embedded: Embedded metadata for comparison
        ref_duration_ms: Reference duration in milliseconds
        config: Merge configuration

    Returns:
        Score (0-1)
    """
    score = 0.0

    # Provider weight (0.40 of total)
    provider_weights = {
        "musicbrainz": 1.0,
        "acoustid": 0.9,
    }
    provider_weight = provider_weights.get(candidate.provider, 0.8)
    score += 0.40 * provider_weight

    # Title similarity (0.20 of total)
    title_sim = token_jaccard(candidate.title, embedded.title)
    score += 0.20 * title_sim

    # Artist similarity (0.20 of total)
    artist_sim = token_jaccard(candidate.artist, embedded.artist)
    score += 0.20 * artist_sim

    # Duration similarity (0.15 of total)
    dur_sim = duration_similarity(candidate.duration_ms, ref_duration_ms)
    score += 0.15 * dur_sim

    # Stable ID bonus (0.05 of total, split among IDs)
    # Bonus values: recording_mbid=0.10, isrc=0.05, release_mbid=0.03
    # Scaled by 0.05 weight factor
    stable_id_bonus = 0.0
    if candidate.mbids.recording_mbid:
        stable_id_bonus += 0.10
    if candidate.isrc:
        stable_id_bonus += 0.05
    if candidate.mbids.release_mbid:
        stable_id_bonus += 0.03

    score += 0.05 * stable_id_bonus

    return score


def merge_metadata(
    embedded: EmbeddedMetadata,
    candidates: list[MetadataCandidate],
    *,
    config: MergeConfig,
    ref_duration_ms: int | None,
) -> ResolvedMetadata | None:
    """Merge embedded + provider metadata deterministically.

    Policy:
    1. Best candidate = max(score), tie-break by provider_precedence
    2. IDs (MBIDs/ISRC): always prefer best candidate if present
    3. Display strings: prefer embedded if non-empty and non-generic
    4. Field confidence: weighted based on source and score
    5. Overall confidence: weighted sum of field confidences

    Args:
        embedded: Embedded metadata
        candidates: Provider candidates
        config: Merge configuration
        ref_duration_ms: Reference duration in milliseconds

    Returns:
        ResolvedMetadata with per-field confidence and provenance
        None if no candidates and embedded is empty
    """
    # Check if we have any data
    has_embedded_data = any(
        [
            embedded.title,
            embedded.artist,
            embedded.album,
        ]
    )

    if not candidates and not has_embedded_data:
        return None

    # Select best candidate if any
    best_candidate: MetadataCandidate | None = None
    if candidates:
        # Sort by score (descending), then by provider precedence
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                -c.score,  # Higher score first
                config.provider_precedence.index(c.provider)
                if c.provider in config.provider_precedence
                else 999,  # Unknown providers last
                c.provider_id,  # Stable tie-break
            ),
        )
        best_candidate = sorted_candidates[0]

    # Merge IDs (always from best candidate if present)
    mbids = best_candidate.mbids if best_candidate else ResolvedMBIDs()
    acoustid_id = best_candidate.acoustid_id if best_candidate else None
    isrc = best_candidate.isrc if best_candidate else None

    # Merge display strings (prefer embedded if non-generic)
    # Title
    title = None
    title_confidence = 0.0
    if embedded.title and not is_generic_title(embedded.title):
        title = embedded.title
        title_confidence = 0.85  # High confidence for non-generic embedded
    elif best_candidate and best_candidate.title:
        title = best_candidate.title
        title_confidence = min(0.95, best_candidate.score)
    elif embedded.title:
        title = embedded.title
        title_confidence = 0.60  # Lower confidence for generic embedded

    # Artist
    artist = None
    artist_confidence = None
    if embedded.artist and not is_generic_artist(embedded.artist):
        artist = embedded.artist
        artist_confidence = 0.85
    elif best_candidate and best_candidate.artist:
        artist = best_candidate.artist
        artist_confidence = min(0.95, best_candidate.score)
    elif embedded.artist:
        artist = embedded.artist
        artist_confidence = 0.60

    # Album
    album = None
    album_confidence = None
    if embedded.album:
        album = embedded.album
        album_confidence = 0.85
    elif best_candidate and best_candidate.album:
        album = best_candidate.album
        album_confidence = min(0.95, best_candidate.score)

    # Duration
    duration_ms = None
    duration_confidence = None
    if best_candidate and best_candidate.duration_ms:
        duration_ms = best_candidate.duration_ms
        # High confidence if within 1s of reference
        if ref_duration_ms:
            delta_ms = abs(duration_ms - ref_duration_ms)
            duration_confidence = 0.95 if delta_ms <= 1000 else 0.70
        else:
            duration_confidence = 0.70

    # Compute overall confidence (weighted sum)
    # Weights: title 0.15, artist 0.15, duration 0.10, recording_mbid 0.35,
    #          release_mbid 0.10, isrc 0.15
    weights: dict[str, float] = {
        "title": 0.15,
        "artist": 0.15,
        "duration": 0.10,
        "recording_mbid": 0.35,
        "release_mbid": 0.10,
        "isrc": 0.15,
    }

    total_confidence = 0.0
    total_weight = 0.0

    if title:
        total_confidence += weights["title"] * title_confidence
        total_weight += weights["title"]

    if artist:
        total_confidence += weights["artist"] * (artist_confidence or 0.0)
        total_weight += weights["artist"]

    if duration_ms:
        total_confidence += weights["duration"] * (duration_confidence or 0.0)
        total_weight += weights["duration"]

    if mbids.recording_mbid:
        mbid_confidence = (
            0.98 if best_candidate and best_candidate.provider == "musicbrainz" else 0.90
        )
        total_confidence += weights["recording_mbid"] * mbid_confidence
        total_weight += weights["recording_mbid"]

    if mbids.release_mbid:
        mbid_confidence = (
            0.98 if best_candidate and best_candidate.provider == "musicbrainz" else 0.90
        )
        total_confidence += weights["release_mbid"] * mbid_confidence
        total_weight += weights["release_mbid"]

    if isrc:
        total_confidence += weights["isrc"] * 0.90
        total_weight += weights["isrc"]

    # Normalize by total weight
    overall_confidence = total_confidence / total_weight if total_weight > 0 else 0.0

    # Warn if confidence is low
    if overall_confidence < config.min_confidence_warn:
        logger.warning(
            f"Low metadata confidence: {overall_confidence:.2f} < {config.min_confidence_warn:.2f}"
        )

    return ResolvedMetadata(
        confidence=overall_confidence,
        title=title,
        title_confidence=title_confidence,
        artist=artist,
        artist_confidence=artist_confidence,
        album=album,
        album_confidence=album_confidence,
        duration_ms=duration_ms,
        duration_confidence=duration_confidence,
        mbids=mbids,
        acoustid_id=acoustid_id,
        isrc=isrc,
    )
