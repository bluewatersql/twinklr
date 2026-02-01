"""Tests for group template registry system."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.templates.group_templates.library import (
    GroupTemplateRegistry,
    TemplateInfo,
    TemplateNotFoundError,
    _norm_key,
    register_template,
)
from twinklr.core.sequencer.templates.group_templates.models import (
    GroupPlanTemplate,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRecipe,
    LayerRole,
)


def test_norm_key():
    """Test key normalization for case-insensitive lookups."""
    assert _norm_key("Fan Pulse") == "fan_pulse"
    assert _norm_key("fan_pulse") == "fan_pulse"
    assert _norm_key("FAN-PULSE") == "fan_pulse"
    assert _norm_key("  fan__pulse  ") == "fan_pulse"
    assert _norm_key("Fan/Pulse!") == "fan_pulse"


def test_template_info_immutable():
    """Test that TemplateInfo is frozen (immutable)."""
    info = TemplateInfo(
        template_id="test",
        name="Test",
        template_type=GroupTemplateType.SECTION_BACKGROUND,
        visual_intent=GroupVisualIntent.SCENE,
        tags=("tag1",),
        template_version="1.0.0",
    )

    with pytest.raises(AttributeError):
        info.template_id = "changed"  # type: ignore


def test_registry_register_basic():
    """Test basic template registration."""
    registry = GroupTemplateRegistry()

    def make_test_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_template",
            name="Test Template",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            tags=["test"],
        )

    registry.register(make_test_template)

    # Should be registered
    template = registry.get("test_template")
    assert template.template_id == "test_template"
    assert template.name == "Test Template"


def test_registry_register_with_aliases():
    """Test template registration with aliases."""
    registry = GroupTemplateRegistry()

    def make_test_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_bg",
            name="Test Background",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    registry.register(make_test_template, aliases=["test bg", "TestBG"])

    # Should be accessible by ID
    t1 = registry.get("test_bg")
    # Should be accessible by name
    t2 = registry.get("Test Background")
    # Should be accessible by aliases (case-insensitive)
    t3 = registry.get("test bg")
    t4 = registry.get("testbg")

    assert t1.template_id == t2.template_id == t3.template_id == t4.template_id


def test_registry_duplicate_registration_error():
    """Test that duplicate registration raises ValueError."""
    registry = GroupTemplateRegistry()

    def make_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="duplicate",
            name="Duplicate",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    registry.register(make_template)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(make_template)


def test_registry_get_not_found():
    """Test that getting unknown template raises TemplateNotFoundError."""
    registry = GroupTemplateRegistry()

    with pytest.raises(TemplateNotFoundError, match="Unknown template"):
        registry.get("nonexistent")


def test_registry_get_deep_copy():
    """Test that get() returns independent copies."""
    registry = GroupTemplateRegistry()

    def make_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test",
            name="Test",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            layer_recipe=[
                LayerRecipe(
                    layer=LayerRole.BASE,
                    motifs=["test"],
                    visual_intent=GroupVisualIntent.SCENE,
                )
            ],
        )

    registry.register(make_template)

    t1 = registry.get("test")
    t2 = registry.get("test")

    # Modify one
    t1.layer_recipe[0].motifs.append("modified")

    # Other should be unchanged
    assert "modified" not in t2.layer_recipe[0].motifs


def test_registry_get_shallow_copy():
    """Test that get(deep_copy=False) returns shallow copies."""
    registry = GroupTemplateRegistry()

    def make_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test",
            name="Test",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    registry.register(make_template)

    t1 = registry.get("test", deep_copy=False)
    t2 = registry.get("test", deep_copy=False)

    # Should be different instances
    assert t1 is not t2


def test_registry_list_all():
    """Test listing all registered templates."""
    registry = GroupTemplateRegistry()

    def make_bg() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_bg",
            name="Background",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    def make_feature() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_feature",
            name="Feature",
            template_type=GroupTemplateType.SECTION_FEATURE,
            visual_intent=GroupVisualIntent.ICON,
        )

    registry.register(make_bg)
    registry.register(make_feature)

    templates = registry.list_all()
    assert len(templates) == 2
    assert all(isinstance(t, TemplateInfo) for t in templates)

    # Should be sorted by template_type, then name
    assert templates[0].template_id == "test_bg"
    assert templates[1].template_id == "test_feature"


def test_registry_find_by_type():
    """Test finding templates by template_type."""
    registry = GroupTemplateRegistry()

    def make_bg() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_bg",
            name="Background",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    def make_feature() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="test_feature",
            name="Feature",
            template_type=GroupTemplateType.SECTION_FEATURE,
            visual_intent=GroupVisualIntent.ICON,
        )

    registry.register(make_bg)
    registry.register(make_feature)

    results = registry.find(template_type=GroupTemplateType.SECTION_BACKGROUND)
    assert len(results) == 1
    assert results[0].template_id == "test_bg"


def test_registry_find_by_visual_intent():
    """Test finding templates by visual_intent."""
    registry = GroupTemplateRegistry()

    def make_scene() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="scene",
            name="Scene",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    def make_icon() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="icon",
            name="Icon",
            template_type=GroupTemplateType.SECTION_FEATURE,
            visual_intent=GroupVisualIntent.ICON,
        )

    registry.register(make_scene)
    registry.register(make_icon)

    results = registry.find(visual_intent=GroupVisualIntent.ICON)
    assert len(results) == 1
    assert results[0].template_id == "icon"


def test_registry_find_by_tag():
    """Test finding templates by tag (case-insensitive)."""
    registry = GroupTemplateRegistry()

    def make_christmas() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="xmas",
            name="Christmas Scene",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            tags=["holiday_christmas_traditional", "winter"],
        )

    def make_generic() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="generic",
            name="Generic Pattern",
            template_type=GroupTemplateType.PATTERN_LOOP,
            visual_intent=GroupVisualIntent.PATTERN,
            tags=["generic"],
        )

    registry.register(make_christmas)
    registry.register(make_generic)

    results = registry.find(has_tag="holiday_christmas_traditional")
    assert len(results) == 1
    assert results[0].template_id == "xmas"

    # Case insensitive
    results = registry.find(has_tag="WINTER")
    assert len(results) == 1


def test_registry_find_by_name_substring():
    """Test finding templates by name substring (case-insensitive)."""
    registry = GroupTemplateRegistry()

    def make_village() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="village",
            name="Cozy Village Night",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
        )

    def make_santa() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="santa",
            name="Santa Center Moment",
            template_type=GroupTemplateType.SECTION_FEATURE,
            visual_intent=GroupVisualIntent.ICON,
        )

    registry.register(make_village)
    registry.register(make_santa)

    results = registry.find(name_contains="village")
    assert len(results) == 1
    assert results[0].template_id == "village"

    # Case insensitive
    results = registry.find(name_contains="SANTA")
    assert len(results) == 1


def test_registry_find_combined_filters():
    """Test finding templates with multiple filters."""
    registry = GroupTemplateRegistry()

    def make_bg1() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="bg1",
            name="Christmas Background",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            tags=["christmas", "cozy"],
        )

    def make_bg2() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="bg2",
            name="Winter Background",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            tags=["winter"],
        )

    def make_feature() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="feature1",
            name="Christmas Feature",
            template_type=GroupTemplateType.SECTION_FEATURE,
            visual_intent=GroupVisualIntent.ICON,
            tags=["christmas"],
        )

    registry.register(make_bg1)
    registry.register(make_bg2)
    registry.register(make_feature)

    # Find christmas backgrounds only
    results = registry.find(template_type=GroupTemplateType.SECTION_BACKGROUND, has_tag="christmas")
    assert len(results) == 1
    assert results[0].template_id == "bg1"


def test_register_template_decorator():
    """Test the @register_template decorator."""
    # Create a new registry for isolation
    from twinklr.core.sequencer.templates.group_templates.library import REGISTRY

    initial_count = len(REGISTRY.list_all())

    @register_template(aliases=["test decorator"])
    def make_decorated_template() -> GroupPlanTemplate:
        return GroupPlanTemplate(
            template_id="decorated",
            name="Decorated Template",
            template_type=GroupTemplateType.ACCENT,
            visual_intent=GroupVisualIntent.ICON,
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
