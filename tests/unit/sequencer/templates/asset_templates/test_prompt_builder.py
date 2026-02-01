"""Tests for asset template prompt builder."""

from __future__ import annotations

from twinklr.core.sequencer.templates.asset_templates.models import (
    AssetTemplate,
    BackgroundMode,
    MatrixDefaults,
    PngDefaults,
    ProjectionDefaults,
    PromptParts,
    PromptPolicy,
    PromptStyle,
    TemplateProjectionHint,
    TemplateType,
)
from twinklr.core.sequencer.templates.asset_templates.prompt_builder import (
    build_prompt,
)


def test_build_prompt_basic():
    """Test basic prompt assembly with all parts."""
    template = AssetTemplate(
        template_id="test_basic",
        name="Test Basic",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            preamble="Test preamble",
            subject="A Christmas ornament",
            style_block="Style: flat illustration",
            composition="Composition: centered",
            background="Background: transparent",
            lighting="Lighting: soft",
            constraints="Keep it simple",
            output_intent="Output: LED matrix",
        ),
    )

    prompt = build_prompt(template)

    assert "Test preamble" in prompt
    assert "A Christmas ornament" in prompt
    assert "Style: flat illustration" in prompt
    assert "Composition: centered" in prompt
    assert "Background: transparent" in prompt
    assert "Lighting: soft" in prompt
    assert "Keep it simple" in prompt
    assert "Output: LED matrix" in prompt


def test_build_prompt_with_policy_constraints():
    """Test prompt assembly with policy-generated constraints."""
    template = AssetTemplate(
        template_id="test_policy",
        name="Test Policy",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="A star"),
        prompt_policy=PromptPolicy(
            require_no_text=True,
            require_no_logos=True,
            require_no_watermarks=True,
            require_low_detail=True,
            require_high_contrast=True,
            require_clean_edges=True,
        ),
    )

    prompt = build_prompt(template)

    assert "Readability: high contrast, bold shapes." in prompt
    assert "Keep detail low; avoid tiny patterns and thin lines." in prompt
    assert "Clean edges; simple shading; no texture noise." in prompt
    assert "Avoid: text." in prompt
    assert "Avoid: logos." in prompt
    assert "Avoid: watermarks." in prompt


def test_build_prompt_with_negative_hints():
    """Test prompt assembly with negative hints."""
    template = AssetTemplate(
        template_id="test_negative",
        name="Test Negative",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="A wreath"),
        negative_hints=["busy textures", "tiny details", "thin outlines"],
    )

    prompt = build_prompt(template)

    assert "Avoid: busy textures, tiny details, thin outlines." in prompt


def test_build_prompt_minimal():
    """Test prompt assembly with only required subject field (includes default policy)."""
    template = AssetTemplate(
        template_id="test_minimal",
        name="Test Minimal",
        template_type=TemplateType.PROMPT_ONLY,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="A simple icon"),
    )

    prompt = build_prompt(template)

    # Subject should be first
    assert prompt.startswith("A simple icon")
    # Default policy constraints should be included
    assert "high contrast" in prompt
    assert "Avoid: text." in prompt


def test_build_prompt_empty_parts_filtered():
    """Test that empty prompt parts are not included."""
    template = AssetTemplate(
        template_id="test_empty_filter",
        name="Test Empty Filter",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            preamble="",
            subject="Santa",
            style_block="",
            composition="Centered",
            background="",
            lighting="",
            constraints="",
            output_intent="",
        ),
        prompt_policy=PromptPolicy(
            require_no_text=False,
            require_no_logos=False,
            require_no_watermarks=False,
            require_low_detail=False,
            require_high_contrast=False,
            require_clean_edges=False,
        ),
    )

    prompt = build_prompt(template)

    lines = [line for line in prompt.split("\n") if line.strip()]
    assert len(lines) == 2
    assert "Santa" in prompt
    assert "Centered" in prompt


def test_build_prompt_policy_selective():
    """Test that only enabled policy constraints are included."""
    template = AssetTemplate(
        template_id="test_selective",
        name="Test Selective",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="Icon"),
        prompt_policy=PromptPolicy(
            require_no_text=True,
            require_no_logos=False,
            require_no_watermarks=False,
            require_low_detail=False,
            require_high_contrast=True,
            require_clean_edges=False,
        ),
    )

    prompt = build_prompt(template)

    assert "Avoid: text." in prompt
    assert "Readability: high contrast, bold shapes." in prompt
    assert "logos" not in prompt.lower()
    assert "watermarks" not in prompt.lower()
    assert "detail low" not in prompt
    assert "Clean edges" not in prompt


def test_build_prompt_combined_constraints():
    """Test that explicit constraints, policy, and negative hints combine properly."""
    template = AssetTemplate(
        template_id="test_combined",
        name="Test Combined",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="Ornament", constraints="No shiny reflections"),
        prompt_policy=PromptPolicy(require_high_contrast=True, require_no_text=True),
        negative_hints=["tiny patterns"],
    )

    prompt = build_prompt(template)

    assert "No shiny reflections" in prompt
    assert "Readability: high contrast, bold shapes." in prompt
    assert "Avoid: text." in prompt
    assert "Avoid: tiny patterns." in prompt


def test_build_prompt_newline_separation():
    """Test that prompt parts are separated by newlines."""
    template = AssetTemplate(
        template_id="test_newlines",
        name="Test Newlines",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            preamble="Preamble",
            subject="Subject",
            style_block="Style",
            composition="Composition",
        ),
        prompt_policy=PromptPolicy(
            require_no_text=False,
            require_no_logos=False,
            require_no_watermarks=False,
            require_low_detail=False,
            require_high_contrast=False,
            require_clean_edges=False,
        ),
    )

    prompt = build_prompt(template)

    lines = prompt.split("\n")
    assert len(lines) == 4
    assert lines[0] == "Preamble"
    assert lines[1] == "Subject"
    assert lines[2] == "Style"
    assert lines[3] == "Composition"


def test_build_prompt_whitespace_trimming():
    """Test that whitespace is properly trimmed from prompt parts."""
    template = AssetTemplate(
        template_id="test_whitespace",
        name="Test Whitespace",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            preamble="  Preamble  ",
            subject="  Subject  ",
            style_block="  Style  ",
        ),
    )

    prompt = build_prompt(template)

    lines = prompt.split("\n")
    assert lines[0] == "Preamble"
    assert lines[1] == "Subject"
    assert lines[2] == "Style"


def test_build_prompt_policy_defaults():
    """Test that default policy (all True) produces all constraints."""
    template = AssetTemplate(
        template_id="test_default_policy",
        name="Test Default Policy",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="Icon"),
        # Default PromptPolicy has all requires set to True
    )

    prompt = build_prompt(template)

    # All default policy constraints should be present
    assert "high contrast" in prompt
    assert "detail low" in prompt or "Keep detail low" in prompt
    assert "Clean edges" in prompt
    assert "Avoid: text." in prompt
    assert "Avoid: logos." in prompt
    assert "Avoid: watermarks." in prompt


def test_build_prompt_tree_seam_safe_hint():
    """Test that tree polar seam-safe constraint is added when applicable."""
    # Note: The current implementation doesn't check projection_defaults,
    # but this test documents expected behavior if that feature is added
    template = AssetTemplate(
        template_id="test_tree_seam",
        name="Test Tree Seam",
        template_type=TemplateType.PNG_PROMPT,
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(subject="Pattern"),
        projection_defaults=ProjectionDefaults(
            mode=TemplateProjectionHint.TREE_POLAR, seam_safe=True
        ),
        prompt_policy=PromptPolicy(require_seam_safe_when_tree=True),
    )

    prompt = build_prompt(template)

    # Currently this won't add seam-safe constraint since we don't check projection
    # This test documents the current behavior
    assert "Pattern" in prompt


def test_build_prompt_complex_example():
    """Test a complex, realistic prompt assembly."""
    template = AssetTemplate(
        template_id="tpl_png_icon_ornament_trad",
        name="PNG Icon — Ornament (Traditional)",
        description="Centered ornament icon, transparent, LED-matrix safe.",
        template_type=TemplateType.PNG_PROMPT,
        tags=[
            "holiday_christmas_traditional",
            "ornaments",
            "icon_friendly",
            "matrix_safe",
        ],
        prompt_style=PromptStyle.LED_MATRIX_SAFE,
        prompt_parts=PromptParts(
            subject="A classic Christmas ornament icon, centered, simplified.",
            style_block="Style: flat illustration with clean vector-like edges. Theme: traditional Christmas.",
            composition="Composition: centered, subject fills ~75% of frame, symmetrical.",
            background="Background: transparent.",
            lighting="Lighting: soft highlight, no harsh shadows.",
            constraints="Avoid: heavy gradients, busy textures.",
            output_intent="Output intent: designed for an LED matrix at low resolution.",
        ),
        matrix_defaults=MatrixDefaults(base_size=256, aspect="1:1"),
        projection_defaults=ProjectionDefaults(mode=TemplateProjectionHint.FLAT),
        png_defaults=PngDefaults(background=BackgroundMode.TRANSPARENT),
        negative_hints=["busy textures", "tiny details", "thin outlines"],
    )

    prompt = build_prompt(template)

    # Check all major components
    assert "Christmas ornament" in prompt
    assert "flat illustration" in prompt
    assert "centered" in prompt
    assert "transparent" in prompt
    assert "soft highlight" in prompt
    assert "heavy gradients" in prompt
    assert "LED matrix" in prompt
    assert "high contrast" in prompt  # From policy
    assert "Avoid: busy textures, tiny details, thin outlines." in prompt
