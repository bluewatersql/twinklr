"""Tests for MacroPlanner agent specifications."""

from twinklr.core.agents.sequencer.macro_planner.specs import (
    MACRO_JUDGE_SPEC,
    MACRO_PLANNER_SPEC,
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.spec import AgentMode

# ============================================================================
# Meaningful Configuration Tests (not trivial field checks)
# ============================================================================


def test_planner_temperature_appropriate_for_creative_work():
    """MacroPlanner has appropriate temperature for strategic creative work."""
    assert MACRO_PLANNER_SPEC.temperature >= 0.5  # Creative enough
    assert MACRO_PLANNER_SPEC.temperature <= 0.9  # Not too random


def test_judge_temperature_lower_for_consistent_evaluation():
    """MacroJudge has lower temperature for consistent evaluation."""
    assert MACRO_JUDGE_SPEC.temperature < 0.5  # More deterministic
    assert MACRO_JUDGE_SPEC.temperature >= 0.0


def test_planner_more_creative_than_judge():
    """Planner has higher temperature than judge."""
    assert MACRO_PLANNER_SPEC.temperature > MACRO_JUDGE_SPEC.temperature


def test_planner_conversational_judge_oneshot():
    """Planner is conversational, judge is oneshot."""
    assert MACRO_PLANNER_SPEC.mode == AgentMode.CONVERSATIONAL
    assert MACRO_JUDGE_SPEC.mode == AgentMode.ONESHOT


# ============================================================================
# Factory Function Tests
# ============================================================================


def test_get_planner_spec_custom_model():
    """get_planner_spec accepts custom model."""
    spec = get_planner_spec(model="gpt-4")
    assert spec.model == "gpt-4"


def test_get_planner_spec_custom_temperature():
    """get_planner_spec accepts custom temperature."""
    spec = get_planner_spec(temperature=0.9)
    assert spec.temperature == 0.9


def test_get_judge_spec_custom_model():
    """get_judge_spec accepts custom model."""
    spec = get_judge_spec(model="gpt-4")
    assert spec.model == "gpt-4"


def test_get_judge_spec_custom_temperature():
    """get_judge_spec accepts custom temperature."""
    spec = get_judge_spec(temperature=0.2)
    assert spec.temperature == 0.2


# ============================================================================
# Taxonomy Injection Tests
# ============================================================================


def test_planner_spec_includes_taxonomy():
    """Planner spec auto-injects taxonomy in default_variables."""
    assert "taxonomy" in MACRO_PLANNER_SPEC.default_variables
    taxonomy = MACRO_PLANNER_SPEC.default_variables["taxonomy"]
    assert isinstance(taxonomy, dict)


def test_judge_spec_includes_taxonomy():
    """Judge spec auto-injects taxonomy in default_variables."""
    assert "taxonomy" in MACRO_JUDGE_SPEC.default_variables
    taxonomy = MACRO_JUDGE_SPEC.default_variables["taxonomy"]
    assert isinstance(taxonomy, dict)


def test_planner_taxonomy_includes_all_enums():
    """Planner taxonomy includes all required enum classes."""
    taxonomy = MACRO_PLANNER_SPEC.default_variables["taxonomy"]

    expected_classes = [
        "LayerRole",
        "BlendMode",
        "TimingDriver",
        "TargetRole",
        "EnergyTarget",
        "ChoreographyStyle",
        "MotionDensity",
    ]

    for class_name in expected_classes:
        assert class_name in taxonomy, f"Missing {class_name} in planner taxonomy"
        assert isinstance(taxonomy[class_name], list), f"{class_name} should be a list"
        assert len(taxonomy[class_name]) > 0, f"{class_name} should not be empty"


def test_planner_taxonomy_values_are_strings():
    """Planner taxonomy enum values are all strings."""
    taxonomy = MACRO_PLANNER_SPEC.default_variables["taxonomy"]

    for class_name, values in taxonomy.items():
        for value in values:
            assert isinstance(value, str), f"{class_name} value {value} should be string"


def test_custom_spec_can_override_taxonomy():
    """Custom spec creation can override taxonomy if needed."""
    custom_taxonomy = {"LayerRole": ["CUSTOM_ROLE"]}
    spec = get_planner_spec()

    # Specs are frozen, so we verify the factory pattern allows customization
    # by creating a new spec with custom default_variables
    from twinklr.core.agents.spec import AgentSpec

    custom_spec = AgentSpec(
        name=spec.name,
        prompt_pack=spec.prompt_pack,
        response_model=spec.response_model,
        mode=spec.mode,
        model=spec.model,
        temperature=spec.temperature,
        max_schema_repair_attempts=spec.max_schema_repair_attempts,
        default_variables={"taxonomy": custom_taxonomy},
    )

    assert custom_spec.default_variables["taxonomy"] == custom_taxonomy
