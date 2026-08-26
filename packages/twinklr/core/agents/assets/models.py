"""Asset creation pipeline models.

Defines the core data models for the asset creation pipeline:
- AssetCategory: Classification of generated assets
- AssetStatus: Generation outcome
- AssetSpec: Declarative specification for an asset to generate
- EnrichedPrompt: LLM response model for prompt enrichment
- ImageResult: Result from image/text generation
- CatalogEntry: Provenance + reuse metadata for one generated asset
- AssetCatalog: Persistent catalog of all generated assets
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.vocabulary import BackgroundMode


class AssetCategory(StrEnum):
    """Classification of generated assets.

    Determines the generation backend and output format.

    Attributes:
        IMAGE_TEXTURE: Tileable texture for LED matrix projection (opaque PNG).
        IMAGE_CUTOUT: Transparent overlay / icon (transparent PNG).
        TEXT_BANNER: Song title or enriched text overlay (transparent PNG, PIL).
    """

    IMAGE_TEXTURE = "image_texture"
    IMAGE_CUTOUT = "image_cutout"
    TEXT_BANNER = "text_banner"

    def is_image(self) -> bool:
        """Whether this category is an image type (generated via OpenAI Images API).

        Returns:
            True for IMAGE_TEXTURE and IMAGE_CUTOUT.
        """
        return self in {
            AssetCategory.IMAGE_TEXTURE,
            AssetCategory.IMAGE_CUTOUT,
        }

    def is_text(self) -> bool:
        """Whether this category is a text type (rendered via PIL).

        Returns:
            True for TEXT_BANNER.
        """
        return self == AssetCategory.TEXT_BANNER


class AssetStatus(StrEnum):
    """Generation outcome for an asset.

    Attributes:
        CREATED: Successfully generated in this run.
        CACHED: Reused from a previous run (prompt_hash match).
        FAILED: Generation failed (see CatalogEntry.error).
    """

    CREATED = "created"
    CACHED = "cached"
    FAILED = "failed"


class AssetSpec(BaseModel):
    """Declarative specification for an asset to generate.

    Produced by the deterministic request extractor from GroupPlanSet.
    Two sources: effect assets (from motifs) and narrative assets (from directives).

    Attributes:
        spec_id: Deterministic identifier for this spec.
        category: Asset category (determines generation backend).
        format: Output format (default PNG for all image/text assets).
        motif_id: Motif identifier (None for narrative/text assets).
        theme_id: Theme context from the plan.
        palette_id: Color palette from the plan.
        target_roles: Which display roles use this asset.
        section_ids: Which sections reference this asset.
        scene_context: Planning notes + lyric narrative for contextual interpretation.
        width: Output width in pixels (default 1024 — prefer large, downsize at render).
        height: Output height in pixels (default 1024).
        background: Background mode (transparent or opaque).
        style_tags: Style tags for generation guidance.
        content_tags: Content tags describing the subject.
        text_content: The text to render (text_banner only).
        prompt: Enriched prompt for image generation (set by LLM enricher).
        negative_prompt: Negative prompt for image generation.
        narrative_subject: What to depict (narrative assets only).
        narrative_description: Rich visual description from directive (narrative assets only).
        color_guidance: Color/palette hints from narrative (narrative assets only).
        mood: Emotional tone (narrative assets only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity
    spec_id: str = Field(min_length=1)
    category: AssetCategory

    # Source context
    motif_id: str | None = None
    theme_id: str = Field(min_length=1)
    palette_id: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(min_length=1, description="Sections referencing this asset")
    scene_context: list[str] = Field(default_factory=list)

    # Generation parameters — default 1024x1024 (largest square supported by the Images API).
    # Prefer large source images: renderer can safely downsize, cannot safely upscale.
    width: int = Field(default=1024, gt=0)
    height: int = Field(default=1024, gt=0)
    background: BackgroundMode = BackgroundMode.TRANSPARENT

    # Tags
    style_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)

    # Text-specific field (text_banner only)
    text_content: str | None = None

    # Enriched prompt (set by LLM enricher, image specs only)
    prompt: str | None = None
    negative_prompt: str | None = None

    # Narrative asset fields (None for effect/motif-driven assets)
    narrative_subject: str | None = None
    narrative_description: str | None = None
    color_guidance: str | None = None
    mood: str | None = None

    # Resolved palette colors (from palette registry, shared by effect + narrative)
    palette_colors: list[dict[str, str]] = Field(
        default_factory=list,
        description='Resolved color stops: [{"hex": "#E53935", "name": "christmas_red"}, ...]',
    )

    # Song context for narrative anchoring (narrative assets only)
    song_title: str | None = None


class EnrichedPrompt(BaseModel):
    """LLM response model for prompt enrichment.

    Produced by the asset_prompt_enricher agent for image specs.

    Attributes:
        prompt: Rich image generation prompt (3-8 sentences).
        negative_prompt: Comma-separated avoid list.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=20, description="Rich image generation prompt")
    negative_prompt: str = Field(min_length=5, description="Comma-separated negative prompt")


class ImageGenerationUsage(BaseModel):
    """Provider-reported token usage for one generated image, when available."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    input_text_tokens: int | None = Field(default=None, ge=0)
    input_image_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    output_text_tokens: int | None = Field(default=None, ge=0)
    output_image_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ImageGenerationCost(BaseModel):
    """Cost derived only from complete, internally consistent reported usage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pricing_as_of: str
    model_snapshot: str
    text_input_usd_per_million: float = Field(ge=0.0)
    image_input_usd_per_million: float = Field(ge=0.0)
    image_output_usd_per_million: float = Field(ge=0.0)
    actual_image_usd: float = Field(ge=0.0)


class ImageResult(BaseModel):
    """Result from a single image or text generation.

    Returned by both OpenAIImageClient and TextRenderer.

    Attributes:
        file_path: Path to generated file (relative to assets/ root).
        content_hash: SHA-256 of file contents.
        file_size_bytes: File size in bytes.
        width: Image width in pixels.
        height: Image height in pixels.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    file_path: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    file_size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    usage: ImageGenerationUsage | None = None


class CatalogEntry(BaseModel):
    """Provenance + reuse metadata for one generated asset.

    Stored in the persistent AssetCatalog.

    Attributes:
        asset_id: Stable identifier (matches spec_id).
        spec: Full AssetSpec for provenance and similarity matching.
        file_path: Relative path within assets/ directory.
        content_hash: SHA-256 of file contents.
        status: Generation outcome.
        width: Image width in pixels.
        height: Image height in pixels.
        has_alpha: Whether image has alpha channel.
        file_size_bytes: File size in bytes.
        created_at: ISO timestamp of generation.
        source_plan_id: Which GroupPlanSet produced this.
        generation_model: Which image/text model was used.
        prompt_hash: SHA-256 of generation prompt (for exact-match cache).
        error: Error message (only for FAILED status).
    """

    model_config = ConfigDict(extra="forbid")

    # Identity
    asset_id: str = Field(min_length=1)
    spec: AssetSpec

    # File
    file_path: str = Field(min_length=1)
    content_hash: str
    status: AssetStatus

    # Image properties
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    has_alpha: bool = False
    file_size_bytes: int = Field(ge=0)

    # Provenance
    created_at: str
    source_plan_id: str
    generation_model: str

    # Reuse
    prompt_hash: str
    image_usage: ImageGenerationUsage | None = None
    image_cost: ImageGenerationCost | None = None

    # Error (FAILED only)
    error: str | None = None


class ImageRequestBudgetSummary(BaseModel):
    """Auditable pre-call reservation for one guarded image batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_requests: int = Field(ge=0)
    authorized_requests: int = Field(ge=0)
    skipped_requests: int = Field(ge=0)
    reservation_usd_per_request: float = Field(ge=0.0)
    reserved_usd: float = Field(ge=0.0)
    usage_reported_requests: int = Field(default=0, ge=0)
    actual_image_usd: float | None = Field(default=None, ge=0.0)
    actual_cost_status: Literal[
        "unavailable", "reported_within_estimate", "reported_exceeds_estimate"
    ] = "unavailable"
    estimate_exceeded: bool | None = None

    def with_actual_cost(
        self,
        actual_image_usd: float | None,
        *,
        usage_reported_requests: int,
    ) -> ImageRequestBudgetSummary:
        """Attach trustworthy actual cost without releasing the original reservation."""
        if actual_image_usd is None:
            return self.model_copy(
                update={
                    "usage_reported_requests": usage_reported_requests,
                    "actual_image_usd": None,
                    "actual_cost_status": "unavailable",
                    "estimate_exceeded": None,
                }
            )
        exceeded = actual_image_usd > self.reserved_usd
        return self.model_copy(
            update={
                "usage_reported_requests": usage_reported_requests,
                "actual_image_usd": actual_image_usd,
                "actual_cost_status": (
                    "reported_exceeds_estimate" if exceeded else "reported_within_estimate"
                ),
                "estimate_exceeded": exceeded,
            }
        )


class ImageRequestBudgetPolicy(BaseModel):
    """Authorize requests only when their full conservative reservation fits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_requests: Literal[1] = 1
    estimated_usd_per_request: float = Field(ge=0.20)

    def authorize(self, requested_requests: int) -> ImageRequestBudgetSummary:
        """Reserve before any await; absent cost metadata never releases funds."""
        requested = max(0, requested_requests)
        authorized = min(requested, self.max_requests)
        reserved = Decimal(authorized) * Decimal(str(self.estimated_usd_per_request))
        return ImageRequestBudgetSummary(
            requested_requests=requested,
            authorized_requests=authorized,
            skipped_requests=requested - authorized,
            reservation_usd_per_request=self.estimated_usd_per_request,
            reserved_usd=float(reserved),
        )


class AssetRunSummary(BaseModel):
    """Observable result of one guarded asset-creation run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    created: int = 0
    cached: int = 0
    failed: int = 0
    skipped: int = 0
    dry_run: bool = False
    estimated_image_usd: float = Field(default=0.0, ge=0.0)
    would_generate: list[str] = Field(default_factory=list)
    request_budget: ImageRequestBudgetSummary


class AssetCatalog(BaseModel):
    """Persistent catalog of all generated assets.

    Accumulates across runs. Supports lookup by asset_id, motif_id,
    and prompt_hash for exact-match reuse.

    Attributes:
        schema_version: Catalog schema version.
        catalog_id: Unique catalog identifier.
        entries: All catalog entries.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["asset-catalog.v2"] = "asset-catalog.v2"
    catalog_id: str = Field(min_length=1)
    entries: list[CatalogEntry] = Field(default_factory=list)

    @property
    def total_created(self) -> int:
        """Count of entries with CREATED status."""
        return sum(1 for e in self.entries if e.status == AssetStatus.CREATED)

    @property
    def total_cached(self) -> int:
        """Count of entries with CACHED status."""
        return sum(1 for e in self.entries if e.status == AssetStatus.CACHED)

    @property
    def total_failed(self) -> int:
        """Count of entries with FAILED status."""
        return sum(1 for e in self.entries if e.status == AssetStatus.FAILED)

    def get(self, asset_id: str) -> CatalogEntry | None:
        """Look up entry by asset_id.

        Args:
            asset_id: Asset identifier to find.

        Returns:
            CatalogEntry if found, None otherwise.
        """
        for entry in self.entries:
            if entry.asset_id == asset_id:
                return entry
        return None

    def find_by_motif(self, motif_id: str) -> list[CatalogEntry]:
        """Find all entries for a given motif.

        Args:
            motif_id: Motif identifier to search for.

        Returns:
            List of matching CatalogEntry objects.
        """
        return [e for e in self.entries if e.spec.motif_id == motif_id]

    def find_by_prompt_hash(self, prompt_hash: str, source_plan_id: str) -> CatalogEntry | None:
        """Find entry by exact prompt hash within one plan/song identity.

        Args:
            prompt_hash: SHA-256 hash of the generation prompt.

        Returns:
            First matching CatalogEntry, or None.
        """
        for entry in self.entries:
            if (
                entry.prompt_hash == prompt_hash
                and entry.source_plan_id == source_plan_id
                and entry.status != AssetStatus.FAILED
            ):
                return entry
        return None

    def successful_entries(self) -> list[CatalogEntry]:
        """Return all non-failed entries (CREATED or CACHED).

        Returns:
            List of successful CatalogEntry objects.
        """
        return [e for e in self.entries if e.status in {AssetStatus.CREATED, AssetStatus.CACHED}]

    def merge(self, new_entries: list[CatalogEntry]) -> None:
        """Merge new entries into catalog, updating existing by asset_id.

        Args:
            new_entries: Entries to add or update.
        """
        existing = {e.asset_id: i for i, e in enumerate(self.entries)}
        for entry in new_entries:
            if entry.asset_id in existing:
                self.entries[existing[entry.asset_id]] = entry
            else:
                self.entries.append(entry)
                existing[entry.asset_id] = len(self.entries) - 1

    def build_index(self) -> dict[str, CatalogEntry]:
        """Build a fast-lookup index of successful entries by asset_id.

        Used by the CompositionEngine to resolve asset overlays.
        Only includes entries with CREATED or CACHED status (not FAILED).

        Returns:
            Dict mapping asset_id → CatalogEntry for all successful entries.
        """
        return {e.asset_id: e for e in self.entries if e.status != AssetStatus.FAILED}
