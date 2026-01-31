"""Tests for MacroPlanner agent specifications."""

from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.agents.sequencer.macro_planner.specs import (
    MACRO_JUDGE_SPEC,
    MACRO_PLANNER_SPEC,
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode

# ============================================================================
# Planner Spec Tests
# ============================================================================


def test_macro_planner_spec_defined():
    """MacroPlanner spec is defined and importable."""
    assert MACRO_PLANNER_SPEC is not None


def test_macro_planner_spec_name():
    """MacroPlanner has correct name."""
    assert MACRO_PLANNER_SPEC.name == "macro_planner"


def test_macro_planner_spec_response_model():
    """MacroPlanner uses MacroPlan as response model."""
    assert MACRO_PLANNER_SPEC.response_model == MacroPlan


def test_macro_planner_spec_mode():
    """MacroPlanner uses conversational mode for iteration."""
    assert MACRO_PLANNER_SPEC.mode == AgentMode.CONVERSATIONAL


def test_macro_planner_spec_prompt_pack():
    """MacroPlanner references correct prompt pack."""
    assert "macro_planner" in MACRO_PLANNER_SPEC.prompt_pack
    assert "planner" in MACRO_PLANNER_SPEC.prompt_pack


def test_macro_planner_spec_temperature():
    """MacroPlanner has appropriate temperature for strategic creative work."""
    assert MACRO_PLANNER_SPEC.temperature >= 0.5  # Creative enough
    assert MACRO_PLANNER_SPEC.temperature <= 0.9  # Not too random


def test_macro_planner_spec_repair_attempts():
    """MacroPlanner has reasonable repair attempts."""
    assert MACRO_PLANNER_SPEC.max_schema_repair_attempts >= 2
    assert MACRO_PLANNER_SPEC.max_schema_repair_attempts <= 5


def test_macro_planner_spec_model():
    """MacroPlanner uses appropriate model."""
    assert MACRO_PLANNER_SPEC.model is not None
    assert len(MACRO_PLANNER_SPEC.model) > 0


# ============================================================================
# Judge Spec Tests
# ============================================================================


def test_macro_judge_spec_defined():
    """MacroJudge spec is defined and importable."""
    assert MACRO_JUDGE_SPEC is not None


def test_macro_judge_spec_name():
    """MacroJudge has correct name."""
    assert MACRO_JUDGE_SPEC.name == "macro_judge"


def test_macro_judge_spec_response_model():
    """MacroJudge uses JudgeVerdict as response model."""
    assert MACRO_JUDGE_SPEC.response_model == JudgeVerdict


def test_macro_judge_spec_mode():
    """MacroJudge uses oneshot mode (no conversation needed)."""
    assert MACRO_JUDGE_SPEC.mode == AgentMode.ONESHOT


def test_macro_judge_spec_prompt_pack():
    """MacroJudge references correct prompt pack."""
    assert (
        "macro_planner" in MACRO_JUDGE_SPEC.prompt_pack or "judge" in MACRO_JUDGE_SPEC.prompt_pack
    )


def test_macro_judge_spec_temperature():
    """MacroJudge has lower temperature for consistent evaluation."""
    assert MACRO_JUDGE_SPEC.temperature < 0.5  # More deterministic
    assert MACRO_JUDGE_SPEC.temperature >= 0.0


def test_macro_judge_spec_repair_attempts():
    """MacroJudge has reasonable repair attempts."""
    assert MACRO_JUDGE_SPEC.max_schema_repair_attempts >= 1
    assert MACRO_JUDGE_SPEC.max_schema_repair_attempts <= 5


# ============================================================================
# Factory Function Tests
# ============================================================================


def test_get_planner_spec_defaults():
    """get_planner_spec returns spec with default values."""
    spec = get_planner_spec()

    assert spec.name == "macro_planner"
    assert spec.response_model == MacroPlan
    assert spec.mode == AgentMode.CONVERSATIONAL


def test_get_planner_spec_custom_model():
    """get_planner_spec accepts custom model."""
    spec = get_planner_spec(model="gpt-4")

    assert spec.model == "gpt-4"


def test_get_planner_spec_custom_temperature():
    """get_planner_spec accepts custom temperature."""
    spec = get_planner_spec(temperature=0.9)

    assert spec.temperature == 0.9


def test_get_planner_spec_custom_token_budget():
    """get_planner_spec accepts custom token budget."""
    spec = get_planner_spec(token_budget=10000)

    assert spec.token_budget == 10000


def test_get_judge_spec_defaults():
    """get_judge_spec returns spec with default values."""
    spec = get_judge_spec()

    assert spec.name == "macro_judge"
    assert spec.response_model == JudgeVerdict
    assert spec.mode == AgentMode.ONESHOT


def test_get_judge_spec_custom_model():
    """get_judge_spec accepts custom model."""
    spec = get_judge_spec(model="gpt-4")

    assert spec.model == "gpt-4"


def test_get_judge_spec_custom_temperature():
    """get_judge_spec accepts custom temperature."""
    spec = get_judge_spec(temperature=0.2)

    assert spec.temperature == 0.2


def test_get_judge_spec_custom_token_budget():
    """get_judge_spec accepts custom token budget."""
    spec = get_judge_spec(token_budget=5000)

    assert spec.token_budget == 5000


# ============================================================================
# Comparison Tests
# ============================================================================


def test_specs_are_distinct():
    """Planner and Judge specs are different objects."""
    assert MACRO_PLANNER_SPEC is not MACRO_JUDGE_SPEC
    assert MACRO_PLANNER_SPEC.name != MACRO_JUDGE_SPEC.name


def test_planner_more_creative_than_judge():
    """Planner has higher temperature than judge."""
    assert MACRO_PLANNER_SPEC.temperature > MACRO_JUDGE_SPEC.temperature


def test_planner_conversational_judge_oneshot():
    """Planner is conversational, judge is oneshot."""
    assert MACRO_PLANNER_SPEC.mode == AgentMode.CONVERSATIONAL
    assert MACRO_JUDGE_SPEC.mode == AgentMode.ONESHOT


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


def test_judge_taxonomy_includes_all_enums():
    """Judge taxonomy includes all required enum classes."""
    taxonomy = MACRO_JUDGE_SPEC.default_variables["taxonomy"]

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
        assert class_name in taxonomy, f"Missing {class_name} in judge taxonomy"
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
