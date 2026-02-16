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

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.vocabulary import BackgroundMode


class AssetCategory(str, Enum):
    """Classification of generated assets.

    Determines the generation backend and output format.

    Attributes:
        IMAGE_TEXTURE: Tileable texture for LED matrix projection (opaque PNG).
        IMAGE_CUTOUT: Transparent overlay / icon (transparent PNG).
        IMAGE_PLATE: Background plate (opaque PNG, v1.1).
        TEXT_BANNER: Song title or enriched text overlay (transparent PNG, PIL).
        TEXT_LYRIC: Lyric-aligned text with timing (transparent PNG, PIL).
        SHADER: Procedural effect spec (JSON, v1.1).
    """

    IMAGE_TEXTURE = "image_texture"
    IMAGE_CUTOUT = "image_cutout"
    IMAGE_PLATE = "image_plate"
    TEXT_BANNER = "text_banner"
    TEXT_LYRIC = "text_lyric"
    SHADER = "shader"

    def is_image(self) -> bool:
        """Whether this category is an image type (generated via OpenAI Images API).

        Returns:
            True for IMAGE_TEXTURE, IMAGE_CUTOUT, IMAGE_PLATE.
        """
        return self in {
            AssetCategory.IMAGE_TEXTURE,
            AssetCategory.IMAGE_CUTOUT,
            AssetCategory.IMAGE_PLATE,
        }

    def is_text(self) -> bool:
        """Whether this category is a text type (rendered via PIL).

        Returns:
            True for TEXT_BANNER, TEXT_LYRIC.
        """
        return self in {AssetCategory.TEXT_BANNER, AssetCategory.TEXT_LYRIC}


class AssetStatus(str, Enum):
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
        matched_template_id: Builtin template ID if matched, None if custom.
        text_content: The text to render (text_banner / text_lyric only).
        text_timing_ms: Timing reference for lyric alignment (text_lyric only).
        prompt: Enriched prompt for image generation (set by LLM enricher).
        negative_prompt: Negative prompt for image generation.
        token_budget: Per-spec token limit for enrichment.
        narrative_subject: What to depict (narrative assets only).
        narrative_description: Rich visual description from directive (narrative assets only).
        color_guidance: Color/palette hints from narrative (narrative assets only).
        mood: Emotional tone (narrative assets only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity
    spec_id: str = Field(min_length=1)
    category: AssetCategory
    format: str = "png"

    # Source context
    motif_id: str | None = None
    theme_id: str = Field(min_length=1)
    palette_id: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(min_length=1, description="Sections referencing this asset")
    scene_context: list[str] = Field(default_factory=list)

    # Generation parameters — default 1024x1024 (largest square supported by gpt-image-1.5).
    # Prefer large source images: renderer can safely downsize, cannot safely upscale.
    width: int = Field(default=1024, gt=0)
    height: int = Field(default=1024, gt=0)
    background: BackgroundMode = BackgroundMode.TRANSPARENT

    # Tags
    style_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)

    # Builtin match
    matched_template_id: str | None = None

    # Text-specific fields (only for text_banner / text_lyric)
    text_content: str | None = None
    text_timing_ms: int | None = None

    # Enriched prompt (set by LLM enricher, image specs only)
    prompt: str | None = None
    negative_prompt: str | None = None

    # Budget
    token_budget: int | None = None

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
        embedding: Future: prompt embedding for similarity search.
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
    embedding: list[float] | None = None

    # Error (FAILED only)
    error: str | None = None


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

    def find_by_prompt_hash(self, prompt_hash: str) -> CatalogEntry | None:
        """Find entry by exact prompt hash (for cache reuse).

        Args:
            prompt_hash: SHA-256 hash of the generation prompt.

        Returns:
            First matching CatalogEntry, or None.
        """
        for entry in self.entries:
            if entry.prompt_hash == prompt_hash and entry.status != AssetStatus.FAILED:
                return entry
        return None

    def find_by_spec_id(
        self, spec_id: str, width: int, height: int
    ) -> CatalogEntry | None:
        """Find entry by deterministic spec_id and dimensions.

        Used for pre-enrichment reuse: matches assets by their stable
        identity (spec_id derived from motif_id + category) without
        requiring the enriched prompt to match.

        Args:
            spec_id: Deterministic spec identifier.
            width: Expected output width.
            height: Expected output height.

        Returns:
            First matching non-failed CatalogEntry, or None.
        """
        for entry in self.entries:
            if (
                entry.spec.spec_id == spec_id
                and entry.spec.width == width
                and entry.spec.height == height
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
