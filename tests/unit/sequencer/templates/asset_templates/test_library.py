"""Tests for asset template registry system."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.templates.asset_templates.library import (
    AssetTemplateRegistry,
    TemplateInfo,
    TemplateNotFoundError,
    _norm_key,
    register_template,
)
from twinklr.core.sequencer.templates.asset_templates.models import (
    AssetTemplate,
    PromptParts,
    PromptStyle,
    TemplateType,
)


def test_norm_key():
    """Test key normalization for case-insensitive lookups."""
    assert _norm_key("Ornament Icon") == "ornament_icon"
    assert _norm_key("ornament_icon") == "ornament_icon"
    assert _norm_key("ORNAMENT-ICON") == "ornament_icon"
    assert _norm_key("  ornament__icon  ") == "ornament_icon"
    assert _norm_key("Ornament/Icon!") == "ornament_icon"


def test_template_info_immutable():
    """Test that TemplateInfo is frozen (immutable)."""
    info = TemplateInfo(
        template_id="test",
        name="Test",
        template_type=TemplateType.PNG_PROMPT,
        tags=("tag1",),
        template_version="1.0.0",
    )

    with pytest.raises(AttributeError):
        info.template_id = "changed"  # type: ignore


def test_registry_register_basic():
    """Test basic template registration."""
    registry = AssetTemplateRegistry()

    def make_test_template() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_template",
            name="Test Template",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test subject"),
            tags=["test"],
        )

    registry.register(make_test_template)

    # Should be registered
    template = registry.get("test_template")
    assert template.template_id == "test_template"
    assert template.name == "Test Template"


def test_registry_register_with_aliases():
    """Test template registration with aliases."""
    registry = AssetTemplateRegistry()

    def make_test_template() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_icon",
            name="Test Icon",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    registry.register(make_test_template, aliases=["test icon", "TestIcon"])

    # Should be accessible by ID
    t1 = registry.get("test_icon")
    # Should be accessible by name
    t2 = registry.get("Test Icon")
    # Should be accessible by aliases (case-insensitive)
    t3 = registry.get("test icon")
    t4 = registry.get("testicon")

    assert t1.template_id == t2.template_id == t3.template_id == t4.template_id


def test_registry_duplicate_registration_error():
    """Test that duplicate registration raises ValueError."""
    registry = AssetTemplateRegistry()

    def make_template() -> AssetTemplate:
        return AssetTemplate(
            template_id="duplicate",
            name="Duplicate",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    registry.register(make_template)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(make_template)


def test_registry_get_not_found():
    """Test that getting unknown template raises TemplateNotFoundError."""
    registry = AssetTemplateRegistry()

    with pytest.raises(TemplateNotFoundError, match="Unknown template"):
        registry.get("nonexistent")


def test_registry_get_deep_copy():
    """Test that get() returns independent copies."""
    registry = AssetTemplateRegistry()

    def make_template() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_copy",
            name="Test",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["test"],
        )

    registry.register(make_template)

    t1 = registry.get("test_copy")
    t2 = registry.get("test_copy")

    # Modify one
    t1.tags.append("modified")

    # Other should be unchanged
    assert "modified" not in t2.tags


def test_registry_list_all():
    """Test listing all registered templates."""
    registry = AssetTemplateRegistry()

    def make_png() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_png",
            name="PNG Template",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    def make_gif() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_gif",
            name="GIF Template",
            template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    registry.register(make_png)
    registry.register(make_gif)

    templates = registry.list_all()
    assert len(templates) == 2
    assert all(isinstance(t, TemplateInfo) for t in templates)

    # Should be sorted by template_type, then name
    assert templates[0].template_id == "test_gif"
    assert templates[1].template_id == "test_png"


def test_registry_find_by_type():
    """Test finding templates by template_type."""
    registry = AssetTemplateRegistry()

    def make_png() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_png",
            name="PNG",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    def make_gif() -> AssetTemplate:
        return AssetTemplate(
            template_id="test_gif",
            name="GIF",
            template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    registry.register(make_png)
    registry.register(make_gif)

    results = registry.find(template_type=TemplateType.PNG_PROMPT)
    assert len(results) == 1
    assert results[0].template_id == "test_png"


def test_registry_find_by_tag():
    """Test finding templates by tag (case-insensitive)."""
    registry = AssetTemplateRegistry()

    def make_christmas() -> AssetTemplate:
        return AssetTemplate(
            template_id="xmas_icon",
            name="Christmas Icon",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["holiday_christmas_traditional", "icon"],
        )

    def make_generic() -> AssetTemplate:
        return AssetTemplate(
            template_id="generic",
            name="Generic",
            template_type=TemplateType.PROMPT_ONLY,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["generic"],
        )

    registry.register(make_christmas)
    registry.register(make_generic)

    results = registry.find(has_tag="holiday_christmas_traditional")
    assert len(results) == 1
    assert results[0].template_id == "xmas_icon"

    # Case insensitive
    results = registry.find(has_tag="ICON")
    assert len(results) == 1


def test_registry_find_by_name_substring():
    """Test finding templates by name substring (case-insensitive)."""
    registry = AssetTemplateRegistry()

    def make_ornament() -> AssetTemplate:
        return AssetTemplate(
            template_id="ornament",
            name="Ornament Icon",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    def make_santa() -> AssetTemplate:
        return AssetTemplate(
            template_id="santa",
            name="Santa Cutout",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    registry.register(make_ornament)
    registry.register(make_santa)

    results = registry.find(name_contains="ornament")
    assert len(results) == 1
    assert results[0].template_id == "ornament"

    # Case insensitive
    results = registry.find(name_contains="SANTA")
    assert len(results) == 1


def test_registry_find_combined_filters():
    """Test finding templates with multiple filters."""
    registry = AssetTemplateRegistry()

    def make_png1() -> AssetTemplate:
        return AssetTemplate(
            template_id="png1",
            name="Christmas PNG",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["christmas", "icon"],
        )

    def make_png2() -> AssetTemplate:
        return AssetTemplate(
            template_id="png2",
            name="Winter PNG",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["winter"],
        )

    def make_gif() -> AssetTemplate:
        return AssetTemplate(
            template_id="gif1",
            name="Christmas GIF",
            template_type=TemplateType.GIF_FROM_PNG_OVERLAY,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
            tags=["christmas"],
        )

    registry.register(make_png1)
    registry.register(make_png2)
    registry.register(make_gif)

    # Find christmas PNGs only
    results = registry.find(template_type=TemplateType.PNG_PROMPT, has_tag="christmas")
    assert len(results) == 1
    assert results[0].template_id == "png1"


def test_register_template_decorator():
    """Test the @register_template decorator."""
    # Create a new registry for isolation
    from twinklr.core.sequencer.templates.asset_templates.library import REGISTRY

    initial_count = len(REGISTRY.list_all())

    @register_template(aliases=["test decorator"])
    def make_decorated_template() -> AssetTemplate:
        return AssetTemplate(
            template_id="decorated",
            name="Decorated Template",
            template_type=TemplateType.PNG_PROMPT,
            prompt_style=PromptStyle.LED_MATRIX_SAFE,
            prompt_parts=PromptParts(subject="Test"),
        )

    # Should be registered
    final_count = len(REGISTRY.list_all())
    assert final_count == initial_count + 1

    # Should be accessible
    template = REGISTRY.get("decorated")
    assert template.name == "Decorated Template"

    # Should be accessible by alias
    template2 = REGISTRY.get("test decorator")
    assert template2.template_id == "decorated"
