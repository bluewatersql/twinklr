"""Tests for asset template models."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.templates.assets.enums import (
    AssetTemplateType,
    BackgroundMode,
    MatrixAspect,
)
from twinklr.core.sequencer.templates.assets.models import (
    AssetTemplate,
    GIFDefaults,
    MatrixDefaults,
    PNGDefaults,
    PromptParts,
    PromptPolicy,
)


class TestPromptParts:
    """Test PromptParts model."""

    def test_create_minimal(self):
        """Test creating with only required subject."""
        parts = PromptParts(subject="Night sky with stars")
        assert parts.subject == "Night sky with stars"
        assert parts.preamble is None

    def test_create_complete(self):
        """Test creating with all fields."""
        parts = PromptParts(
            preamble="Create a background",
            subject="Night sky with stars",
            style_block="Simple, clean",
            composition="Centered",
            background="Deep blue",
            lighting="Soft ambient",
            constraints="No text",
            output_intent="Suitable for flat mapping",
        )
        assert parts.subject == "Night sky with stars"
        assert parts.preamble == "Create a background"

    def test_subject_required(self):
        """Test subject is required."""
        with pytest.raises(ValidationError):
            PromptParts()

    def test_subject_min_length(self):
        """Test subject must be at least 3 chars."""
        with pytest.raises(ValidationError):
            PromptParts(subject="ab")

    def test_frozen(self):
        """Test PromptParts is frozen."""
        parts = PromptParts(subject="Test")
        with pytest.raises(ValidationError):
            parts.subject = "Modified"


class TestPromptPolicy:
    """Test PromptPolicy model."""

    def test_create_with_defaults(self):
        """Test creating with default values."""
        policy = PromptPolicy()
        assert policy.require_high_contrast is True
        assert policy.require_no_text is True
        assert policy.require_seam_safe is False

    def test_create_custom(self):
        """Test creating with custom values."""
        policy = PromptPolicy(require_seam_safe=True, require_high_contrast=False)
        assert policy.require_seam_safe is True
        assert policy.require_high_contrast is False


class TestMatrixDefaults:
    """Test MatrixDefaults model."""

    def test_create_with_defaults(self):
        """Test creating with default values."""
        defaults = MatrixDefaults()
        assert defaults.base_size == 256
        assert defaults.aspect == MatrixAspect.SQUARE
        assert defaults.even_dimensions is True

    def test_create_custom(self):
        """Test creating with custom values."""
        defaults = MatrixDefaults(base_size=512, aspect=MatrixAspect.HD)
        assert defaults.base_size == 512
        assert defaults.aspect == MatrixAspect.HD

    def test_base_size_positive(self):
        """Test base_size must be positive."""
        with pytest.raises(ValidationError):
            MatrixDefaults(base_size=0)


class TestPNGDefaults:
    """Test PNGDefaults model."""

    def test_create_with_defaults(self):
        """Test creating with default values."""
        defaults = PNGDefaults()
        assert defaults.background == BackgroundMode.TRANSPARENT

    def test_create_opaque(self):
        """Test creating with opaque background."""
        defaults = PNGDefaults(background=BackgroundMode.OPAQUE)
        assert defaults.background == BackgroundMode.OPAQUE


class TestGIFDefaults:
    """Test GIFDefaults model."""

    def test_create_with_defaults(self):
        """Test creating with default values."""
        defaults = GIFDefaults()
        assert defaults.background == BackgroundMode.TRANSPARENT
        assert defaults.fps == 12
        assert defaults.seconds == 2.0
        assert defaults.loop is True

    def test_create_custom(self):
        """Test creating with custom values."""
        defaults = GIFDefaults(fps=24, seconds=5.0, loop=False)
        assert defaults.fps == 24
        assert defaults.seconds == 5.0
        assert defaults.loop is False

    def test_fps_bounds(self):
        """Test fps must be between 1 and 60."""
        with pytest.raises(ValidationError):
            GIFDefaults(fps=0)
        with pytest.raises(ValidationError):
            GIFDefaults(fps=61)

    def test_seconds_bounds(self):
        """Test seconds must be between 0 and 10."""
        with pytest.raises(ValidationError):
            GIFDefaults(seconds=0.0)
        with pytest.raises(ValidationError):
            GIFDefaults(seconds=10.1)


class TestAssetTemplate:
    """Test AssetTemplate model."""

    def test_create_minimal_png(self):
        """Test creating minimal PNG template."""
        template = AssetTemplate(
            template_id="test_png",
            name="Test PNG",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Night sky"),
            png_defaults=PNGDefaults(),
        )
        assert template.template_id == "test_png"
        assert template.template_type == AssetTemplateType.PNG_OPAQUE
        assert template.schema_version == "asset_template.v1"

    def test_create_minimal_gif(self):
        """Test creating minimal GIF template."""
        template = AssetTemplate(
            template_id="test_gif",
            name="Test GIF",
            template_type=AssetTemplateType.GIF_OVERLAY,
            prompt_parts=PromptParts(subject="Snowfall"),
            gif_defaults=GIFDefaults(),
        )
        assert template.template_id == "test_gif"
        assert template.template_type == AssetTemplateType.GIF_OVERLAY

    def test_create_complete(self):
        """Test creating complete template."""
        template = AssetTemplate(
            template_id="atpl_plate_night_sky",
            name="Night Sky - Simple",
            template_type=AssetTemplateType.PNG_OPAQUE,
            tags=["night", "sky", "background"],
            prompt_parts=PromptParts(
                preamble="Create a background",
                subject="Night sky with stars",
                style_block="Simple, clean",
            ),
            prompt_policy=PromptPolicy(require_high_contrast=True),
            negative_hints=["text", "logos", "watermarks"],
            matrix_defaults=MatrixDefaults(base_size=512),
            png_defaults=PNGDefaults(background=BackgroundMode.OPAQUE),
            template_version="1.0.0",
            author="twinklr",
        )
        assert len(template.tags) == 3
        assert len(template.negative_hints) == 3

    def test_template_id_pattern(self):
        """Test template_id must match pattern."""
        # Valid
        AssetTemplate(
            template_id="test123",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
        )

        # Invalid (uppercase)
        with pytest.raises(ValidationError):
            AssetTemplate(
                template_id="Test_123",
                name="Test",
                template_type=AssetTemplateType.PNG_OPAQUE,
                prompt_parts=PromptParts(subject="Test"),
                png_defaults=PNGDefaults(),
            )

    def test_png_requires_png_defaults(self):
        """Test PNG types require png_defaults."""
        with pytest.raises(ValidationError, match="requires png_defaults"):
            AssetTemplate(
                template_id="test",
                name="Test",
                template_type=AssetTemplateType.PNG_OPAQUE,
                prompt_parts=PromptParts(subject="Test"),
                # Missing png_defaults
            )

    def test_gif_requires_gif_defaults(self):
        """Test GIF types require gif_defaults."""
        with pytest.raises(ValidationError, match="requires gif_defaults"):
            AssetTemplate(
                template_id="test",
                name="Test",
                template_type=AssetTemplateType.GIF_OVERLAY,
                prompt_parts=PromptParts(subject="Test"),
                # Missing gif_defaults
            )

    def test_tags_normalized(self):
        """Test tags are normalized and deduped."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            tags=["Night", "SKY", "night", "  stars  "],
        )
        # Should be lowercase, sorted, deduped
        assert template.tags == ["night", "sky", "stars"]

    def test_negative_hints_normalized(self):
        """Test negative hints are normalized and deduped."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            negative_hints=["text", "text", "  logos  ", "watermarks"],
        )
        # Should be deduped, sorted
        assert template.negative_hints == ["logos", "text", "watermarks"]

    def test_extra_forbid(self):
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError):
            AssetTemplate(
                template_id="test",
                name="Test",
                template_type=AssetTemplateType.PNG_OPAQUE,
                prompt_parts=PromptParts(subject="Test"),
                png_defaults=PNGDefaults(),
                unknown_field="value",  # type: ignore
            )
