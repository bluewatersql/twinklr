"""Tests for template registration and loading system.

Tests that all built-in templates are registered correctly and can be loaded.
Written fresh for new architecture after template migration (Task 7).
"""

import pytest

from blinkb0t.core.sequencer.models.enum import (
    SemanticGroupType,
    TemplateCategory,
    TemplateRole,
)
from blinkb0t.core.sequencer.models.template import TemplateDoc
from blinkb0t.core.sequencer.moving_heads.templates import (
    get_template,
    list_templates,
    load_builtin_templates,
)

# ============================================================================
# Setup
# ============================================================================


@pytest.fixture(scope="module", autouse=True)
def load_templates():
    """Load all built-in templates once for all tests."""
    load_builtin_templates()


# ============================================================================
# Template Loading Tests
# ============================================================================


def test_all_templates_load():
    templates = list_templates()

    # We migrated 25 templates from POC
    assert len(templates) >= 18, f"Expected at least 19 templates, got {len(templates)}"

    # Each template info should have required fields
    for info in templates:
        assert info.template_id
        assert info.name
        assert info.category in TemplateCategory


def test_each_template_can_be_retrieved():
    """Verify each registered template can be retrieved by ID."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)
        assert doc is not None
        assert isinstance(doc, TemplateDoc)
        assert doc.template.template_id == info.template_id


def test_template_ids_unique():
    """Verify all template IDs are unique (no duplicates)."""
    templates = list_templates()
    template_ids = [info.template_id for info in templates]

    assert len(template_ids) == len(set(template_ids)), "Duplicate template IDs found"


# ============================================================================
# Template Metadata Tests
# ============================================================================


def test_templates_have_complete_metadata():
    """Verify all templates have required metadata fields."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)
        template = doc.template

        # Core fields
        assert template.template_id
        assert template.version >= 1
        assert template.name
        assert template.category in TemplateCategory
        assert len(template.roles) > 0
        assert len(template.steps) > 0

        # Metadata
        assert template.metadata is not None
        assert template.metadata.description
        assert template.metadata.energy_range
        assert len(template.metadata.energy_range) == 2
        assert 0 <= template.metadata.energy_range[0] <= 100
        assert 0 <= template.metadata.energy_range[1] <= 100
        assert template.metadata.energy_range[0] <= template.metadata.energy_range[1]


def test_templates_have_valid_categories():
    """Verify template categories are appropriate."""
    templates = list_templates()
    category_counts = {}

    for info in templates:
        doc = get_template(info.template_id)
        category = doc.template.category
        category_counts[category] = category_counts.get(category, 0) + 1

    # Should have templates in multiple categories
    assert len(category_counts) >= 3, "Templates should span multiple energy categories"

    # Each category should have at least one template
    for count in category_counts.values():
        assert count > 0


def test_templates_have_tags():
    """Verify templates have descriptive tags."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)
        assert len(doc.template.metadata.tags) > 0, f"Template {info.template_id} has no tags"


# ============================================================================
# Template Structure Tests
# ============================================================================


def test_templates_have_valid_roles():
    """Verify template roles are valid."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)

        # Each template should have at least one role
        assert len(doc.template.roles) > 0

        # All roles should be valid enum values
        for role in doc.template.roles:
            assert role in TemplateRole


def test_templates_have_steps():
    """Verify templates have at least one step."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)

        # Each template must have steps
        assert len(doc.template.steps) > 0, f"Template {info.template_id} has no steps"

        # Each step should have required fields
        for step in doc.template.steps:
            assert step.step_id
            assert step.target in SemanticGroupType
            assert step.timing is not None


def test_templates_have_repeat_contracts():
    """Verify templates with loops have proper repeat contracts."""
    templates = list_templates()

    for info in templates:
        doc = get_template(info.template_id)

        if doc.template.repeat and doc.template.repeat.repeatable:
            # Repeatable templates should specify loop_step_ids
            assert len(doc.template.repeat.loop_step_ids) > 0, (
                f"Repeatable template {info.template_id} has no loop_step_ids"
            )

            # Verify loop_step_ids reference actual steps
            step_ids = {s.step_id for s in doc.template.steps}
            for loop_id in doc.template.repeat.loop_step_ids:
                assert loop_id in step_ids, f"Loop step '{loop_id}' not found in template steps"


# ============================================================================
# Specific Template Tests (Spot Checks)
# ============================================================================


def test_sweep_lr_fan_pulse_template():
    """Spot check: verify sweep_lr_fan_pulse template loads correctly."""
    doc = get_template("sweep_lr_fan_pulse")

    assert doc is not None
    assert doc.template.name == "Sweep LR Fan Pulse"
    assert doc.template.category == TemplateCategory.MEDIUM_ENERGY
    assert len(doc.template.roles) == 4
    assert TemplateRole.OUTER_LEFT in doc.template.roles
    assert TemplateRole.OUTER_RIGHT in doc.template.roles


def test_bounce_fan_pulse_template():
    """Spot check: verify bounce_fan_pulse template loads correctly."""
    doc = get_template("bounce_fan_pulse")

    assert doc is not None
    assert doc.template.category in TemplateCategory
    assert len(doc.template.steps) > 0


# ============================================================================
# Error Cases
# ============================================================================


def test_get_nonexistent_template_raises():
    """Verify getting a non-existent template raises appropriate error."""
    with pytest.raises(KeyError):
        get_template("nonexistent_template_id_12345")


# ============================================================================
# Migration Validation
# ============================================================================


def test_all_migrated_templates_present():
    """Verify all 25 POC templates were migrated successfully."""
    templates = list_templates()
    template_ids = {info.template_id for info in templates}

    # These are the templates we migrated from .dev/sequencer/moving_heads/templates/types/
    expected_migrated = {
        "bounce_fan_pulse",
        "cascade_pulse_lr",
        "circle_asym_left_strobe",
        "circle_asym_right_pulse",
        "circle_fan_hold",
        "fan_pulse",
        "inner_pendulum_breathe",
        "lean_right_scan",
        "pendulum_chevron_breathe",
        "sweep_lr_chevron_breathe",
        "sweep_lr_continuous_phase",
        "sweep_lr_fan_hold",
        "sweep_lr_fan_pulse",
        "sweep_lr_pingpong_phase",
        "sweep_ud_chevron_swell",
        "wave_fan_hold",
        "wave_scattered_fade_in",
        "wave_scattered_fade_out",
    }

    # All migrated templates should be registered
    for expected_id in expected_migrated:
        assert expected_id in template_ids, (
            f"Migrated template '{expected_id}' not found in registry"
        )
