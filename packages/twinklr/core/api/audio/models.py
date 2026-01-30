"""API models for audio metadata providers (Phase 3).

Request and response models for AcoustID and MusicBrainz APIs.
"""

from pydantic import BaseModel, ConfigDict, Field


class AcoustIDRecording(BaseModel):
    """AcoustID recording result.

    Single recording match from AcoustID fingerprint lookup.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="AcoustID identifier")
    score: float = Field(ge=0.0, le=1.0, description="Match confidence score")

    # Metadata fields (optional)
    title: str | None = Field(default=None, description="Recording title")
    artists: list[str] = Field(default_factory=list, description="Artist names")
    duration_ms: int | None = Field(default=None, gt=0, description="Duration in milliseconds")

    # MusicBrainz IDs (optional)
    recording_mbid: str | None = Field(default=None, description="MusicBrainz recording ID")
    release_mbid: str | None = Field(default=None, description="MusicBrainz release ID")


class AcoustIDResponse(BaseModel):
    """AcoustID API response.

    Response from AcoustID fingerprint lookup endpoint.
    """

    model_config = ConfigDict(extra="ignore")  # Allow extra fields from API

    status: str = Field(description="Response status ('ok' or 'error')")
    results: list[AcoustIDRecording] = Field(default_factory=list, description="Recording matches")
    error: str | None = Field(default=None, description="Error message if status='error'")


class MusicBrainzRelease(BaseModel):
    """MusicBrainz release (album) information."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="MusicBrainz release ID")
    title: str = Field(description="Release title (album name)")
    date: str | None = Field(default=None, description="Release date (YYYY-MM-DD)")
    country: str | None = Field(default=None, description="Release country code")


class MusicBrainzRecording(BaseModel):
    """MusicBrainz recording information.

    Response from MusicBrainz recording lookup by MBID.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="MusicBrainz recording ID")
    title: str = Field(description="Recording title")

    # Metadata fields (optional)
    artists: list[str] = Field(default_factory=list, description="Artist names")
    length_ms: int | None = Field(default=None, gt=0, description="Length in milliseconds")
    isrc: str | None = Field(default=None, description="ISRC code")

    # Associated releases
    releases: list[MusicBrainzRelease] = Field(
        default_factory=list, description="Releases containing this recording"
    )
