"""Tests for asset template prompt builder."""

from twinklr.core.sequencer.templates.assets.enums import AssetTemplateType, BackgroundMode
from twinklr.core.sequencer.templates.assets.models import (
    AssetTemplate,
    PNGDefaults,
    PromptParts,
    PromptPolicy,
)
from twinklr.core.sequencer.templates.assets.prompt_builder import (
    build_negative_prompt,
    build_prompt,
    policy_to_constraint_text,
)


class TestPolicyToConstraintText:
    """Test policy_to_constraint_text function."""

    def test_all_flags_true(self):
        """Test all policy flags enabled."""
        policy = PromptPolicy(
            require_high_contrast=True,
            require_low_detail=True,
            require_clean_edges=True,
            require_no_text=True,
            require_no_logos=True,
            require_no_watermarks=True,
            require_seam_safe=True,
        )
        lines = policy_to_constraint_text(policy)
        assert len(lines) == 7
        assert "High contrast required" in lines
        assert "CRITICAL: Seamless tiling required (tileable on all edges)" in lines

    def test_selective_flags(self):
        """Test selective policy flags."""
        policy = PromptPolicy(
            require_high_contrast=False,
            require_low_detail=False,
            require_no_text=True,
            require_seam_safe=True,
        )
        lines = policy_to_constraint_text(policy)
        assert "High contrast required" not in lines
        assert "CRITICAL: No text, letters, or words" in lines
        assert "CRITICAL: Seamless tiling required (tileable on all edges)" in lines

    def test_no_flags(self):
        """Test no policy flags enabled."""
        policy = PromptPolicy(
            require_high_contrast=False,
            require_low_detail=False,
            require_clean_edges=False,
            require_no_text=False,
            require_no_logos=False,
            require_no_watermarks=False,
            require_seam_safe=False,
        )
        lines = policy_to_constraint_text(policy)
        assert len(lines) == 0


class TestBuildPrompt:
    """Test build_prompt function."""

    def test_minimal_prompt(self):
        """Test building prompt with minimal parts."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Night sky with stars"),
            png_defaults=PNGDefaults(),
        )
        prompt = build_prompt(template)
        assert "Night sky with stars" in prompt
        assert isinstance(prompt, str)

    def test_complete_prompt(self):
        """Test building prompt with all parts."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(
                preamble="Create a Christmas light show background",
                subject="Night sky with subtle gradient and scattered stars",
                style_block="Simple, clean, low detail",
                composition="Centered, balanced, no focal point",
                background="Deep blue gradient from midnight blue to navy",
                lighting="Soft ambient starlight, no harsh highlights",
                constraints="Additional constraint",
                output_intent="Suitable for flat matrix mapping as static background layer",
            ),
            prompt_policy=PromptPolicy(require_high_contrast=True, require_no_text=True),
            negative_hints=["text", "logos", "watermarks"],
            png_defaults=PNGDefaults(background=BackgroundMode.OPAQUE),
        )
        prompt = build_prompt(template)

        # Check all parts present
        assert "Create a Christmas light show background" in prompt
        assert "Night sky with subtle gradient" in prompt
        assert "Simple, clean, low detail" in prompt
        assert "Centered, balanced" in prompt
        assert "Deep blue gradient" in prompt
        assert "Soft ambient starlight" in prompt
        assert "Additional constraint" in prompt
        assert "High contrast required" in prompt
        assert "CRITICAL: No text, letters, or words" in prompt
        assert "Avoid: logos, text, watermarks" in prompt  # Sorted!
        assert "Suitable for flat matrix mapping" in prompt

    def test_prompt_section_order(self):
        """Test prompt sections appear in correct order."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(
                preamble="PREAMBLE",
                subject="SUBJECT",
                style_block="STYLE",
                composition="COMPOSITION",
                background="BACKGROUND",
                lighting="LIGHTING",
                constraints="CONSTRAINTS",
                output_intent="OUTPUT",
            ),
            png_defaults=PNGDefaults(),
        )
        prompt = build_prompt(template)

        # Check order
        preamble_pos = prompt.find("PREAMBLE")
        subject_pos = prompt.find("SUBJECT")
        style_pos = prompt.find("STYLE")
        composition_pos = prompt.find("COMPOSITION")
        background_pos = prompt.find("BACKGROUND")
        lighting_pos = prompt.find("LIGHTING")
        output_pos = prompt.find("OUTPUT")

        assert preamble_pos < subject_pos
        assert subject_pos < style_pos
        assert style_pos < composition_pos
        assert composition_pos < background_pos
        assert background_pos < lighting_pos
        assert lighting_pos < output_pos

    def test_omits_empty_parts(self):
        """Test empty parts are omitted."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(
                subject="Subject only",
                # All other parts None/empty
            ),
            png_defaults=PNGDefaults(),
        )
        prompt = build_prompt(template)
        # Should only contain subject and policy constraints (which are enabled by default)
        lines = prompt.split("\n\n")
        # Policy adds constraints, so check it's not too long
        assert len(prompt) < 250  # Increased threshold to account for default policy

    def test_deterministic(self):
        """Test prompt building is deterministic."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test subject", style_block="Test style"),
            png_defaults=PNGDefaults(),
        )
        prompt1 = build_prompt(template)
        prompt2 = build_prompt(template)
        assert prompt1 == prompt2


class TestBuildNegativePrompt:
    """Test build_negative_prompt function."""

    def test_empty_hints(self):
        """Test building negative prompt with no hints."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            negative_hints=[],
        )
        neg_prompt = build_negative_prompt(template)
        assert neg_prompt == ""

    def test_single_hint(self):
        """Test building negative prompt with single hint."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            negative_hints=["text"],
        )
        neg_prompt = build_negative_prompt(template)
        assert neg_prompt == "text"

    def test_multiple_hints(self):
        """Test building negative prompt with multiple hints."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            negative_hints=["logos", "text", "watermarks"],  # Will be sorted
        )
        neg_prompt = build_negative_prompt(template)
        # Should be comma-separated and sorted
        assert neg_prompt == "logos, text, watermarks"

    def test_deterministic(self):
        """Test negative prompt building is deterministic."""
        template = AssetTemplate(
            template_id="test",
            name="Test",
            template_type=AssetTemplateType.PNG_OPAQUE,
            prompt_parts=PromptParts(subject="Test"),
            png_defaults=PNGDefaults(),
            negative_hints=["text", "logos"],
        )
        neg1 = build_negative_prompt(template)
        neg2 = build_negative_prompt(template)
        assert neg1 == neg2
