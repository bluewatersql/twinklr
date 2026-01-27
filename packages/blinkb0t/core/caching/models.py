"""Models for cache system.

Provides cache key, metadata, and configuration models.
"""

from pydantic import BaseModel, Field


class CacheKey(BaseModel):
    """
    Stable identifier for a cache entry.

    Uniquely identifies a cached computation based on:
    - Step identity (id + version)
    - Input fingerprint (SHA256 of canonicalized inputs)
    """

    step_id: str = Field(description="Stable step identifier (e.g., 'audio.features')")
    step_version: str = Field(description="Step version string (bump on logic/schema changes)")
    input_fingerprint: str = Field(description="SHA256 hex digest of canonicalized inputs")

    def __str__(self) -> str:
        return f"{self.step_id}:{self.step_version}:{self.input_fingerprint[:12]}"


class CacheMeta(BaseModel):
    """
    Metadata committed after artifact write (commit marker).

    Presence of meta.json indicates a complete, valid cache entry.
    """

    step_id: str
    step_version: str
    input_fingerprint: str
    created_at: float = Field(description="Unix timestamp (seconds)")
    artifact_model: str = Field(description="Fully-qualified artifact model class name")
    artifact_schema_version: int | None = Field(
        default=None, description="Optional schema version from artifact model"
    )
    compute_ms: float | None = Field(
        default=None, description="Computation duration in milliseconds"
    )
    artifact_bytes: int | None = Field(default=None, description="Artifact JSON size in bytes")


class CacheOptions(BaseModel):
    """
    Per-call cache behavior configuration.
    """

    enabled: bool = Field(default=True, description="Global cache toggle for this call")
    force: bool = Field(
        default=False,
        description="Ignore cache and recompute (still stores if enabled)",
    )
    ttl_seconds: float | None = Field(
        default=None,
        description="Optional TTL (rarely needed for deterministic steps)",
    )
