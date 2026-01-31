"""Tests for MacroPlanner judge prompt templates."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import pytest
import yaml

from twinklr.core.agents.audio.profile.models import AudioProfileModel, SongSectionRef
from twinklr.core.agents.sequencer.macro_planner.models import (
    GlobalStory,
    LayeringPlan,
    LayerSpec,
    MacroPlan,
    MacroSectionPlan,
    TargetSelector,
)
from twinklr.core.agents.taxonomy import (
    BlendMode,
    ChoreographyStyle,
    EnergyTarget,
    LayerRole,
    MotionDensity,
    TargetRole,
    TimingDriver,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def audio_profile() -> AudioProfileModel:
    """Load valid audio profile fixture."""
    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "audio_profile"
        / "audio_profile_model.json"
    )
    with fixture_path.open() as f:
        data = json.load(f)
    return AudioProfileModel.model_validate(data)


@pytest.fixture
def display_groups() -> list[dict]:
    """Mock display groups."""
    return [
        {"role_key": "OUTLINE", "model_count": 200},
        {"role_key": "MEGA_TREE", "model_count": 500},
        {"role_key": "HERO", "model_count": 100},
    ]


@pytest.fixture
def valid_macro_plan(audio_profile: AudioProfileModel) -> MacroPlan:
    """Create a valid MacroPlan for testing."""
    sections = audio_profile.structure.sections[:3]  # Use first 3 sections

    return MacroPlan(
        global_story=GlobalStory(
            theme="Winter wonderland with building energy and festive celebration",
            motifs=["Snowflakes", "Twinkling stars", "Crescendo"],
            pacing_notes="Start calm and serene in the intro, build energy through the verses, and peak at the chorus with maximum impact.",
            color_story="Cool blue for serenity, warm white for transitions, festive red for high-energy moments",
        ),
        layering_plan=LayeringPlan(
            layers=[
                LayerSpec(
                    layer_index=0,
                    layer_role=LayerRole.BASE,
                    blend_mode=BlendMode.NORMAL,
                    usage_notes="Foundation with outline and tree providing consistent structure",
                    target_selector=TargetSelector(
                        roles=[TargetRole.OUTLINE, TargetRole.MEGA_TREE]
                    ),
                    timing_driver=TimingDriver.BARS,
                ),
                LayerSpec(
                    layer_index=1,
                    layer_role=LayerRole.RHYTHM,
                    blend_mode=BlendMode.ADD,
                    usage_notes="Beat-driven accents providing rhythmic emphasis",
                    target_selector=TargetSelector(roles=[TargetRole.HERO]),
                    timing_driver=TimingDriver.BEATS,
                ),
            ],
            strategy_notes="Two-layer approach: stable BASE for structure, RHYTHM layer for beat-driven accents",
        ),
        section_plans=[
            MacroSectionPlan(
                section=SongSectionRef(
                    section_id=sec.section_id,
                    name=sec.name,
                    start_ms=sec.start_ms,
                    end_ms=sec.end_ms,
                ),
                energy_target=EnergyTarget.LOW if i == 0 else EnergyTarget.HIGH,
                motion_density=MotionDensity.SPARSE if i == 0 else MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.ABSTRACT,
                primary_focus_targets=[TargetRole.OUTLINE.value],
                secondary_targets=[TargetRole.MEGA_TREE.value],
                notes="This section should emphasize serene twinkling patterns with minimal motion for maximum impact.",
            )
            for i, sec in enumerate(sections)
        ],
        asset_requirements=["snowflake_sparkle.png"],
    )


@pytest.fixture
def jinja_env() -> Environment:
    """Create Jinja2 environment for rendering templates."""
    template_dir = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
    )
    return Environment(loader=FileSystemLoader(template_dir), autoescape=False)


# ============================================================================
# System Prompt Tests
# ============================================================================


def test_system_prompt_renders(jinja_env: Environment):
    """System prompt renders without errors."""
    template = jinja_env.get_template("system.j2")

    # Mock response schema (would come from Pydantic)
    response_schema = '{"type": "object", "properties": {}}'

    result = template.render(response_schema=response_schema)

    assert len(result) > 0
    assert "Christmas light show" in result


def test_system_prompt_judge_identity(jinja_env: Environment):
    """System prompt establishes judge identity."""
    template = jinja_env.get_template("system.j2")
    response_schema = '{"type": "object"}'

    result = template.render(response_schema=response_schema)

    assert "judge" in result.lower()
    assert "evaluate" in result.lower() or "assess" in result.lower()


def test_system_prompt_christmas_persona(jinja_env: Environment):
    """System prompt enforces Christmas light show persona."""
    template = jinja_env.get_template("system.j2")
    response_schema = '{"type": "object"}'

    result = template.render(response_schema=response_schema)

    # Should emphasize Christmas/residential display context
    assert "Christmas" in result
    assert "residential" in result or "street" in result or "display" in result


def test_system_prompt_bold_over_subtle(jinja_env: Environment):
    """System prompt emphasizes bold over subtle design."""
    template = jinja_env.get_template("system.j2")
    response_schema = '{"type": "object"}'

    result = template.render(response_schema=response_schema)

    assert "bold" in result.lower() or "impact" in result.lower()
    assert "subtle" in result.lower()  # Should mention avoiding subtlety


def test_system_prompt_no_concert_language_positive(jinja_env: Environment):
    """System prompt does not use concert/stage language in positive context."""
    template = jinja_env.get_template("system.j2")
    response_schema = '{"type": "object"}'

    result = template.render(response_schema=response_schema)

    # Check for forbidden terms NOT preceded by negation
    forbidden = ["concert", "stage production", "nightclub"]
    for term in forbidden:
        if term in result.lower():
            # Find context around term (50 chars before)
            idx = result.lower().find(term)
            context = result[max(0, idx - 50) : idx + len(term) + 10].lower()
            # Should be preceded by NOT/never/avoid
            assert any(neg in context for neg in ["not", "never", "avoid", "think"]), (
                f"Found '{term}' without negation context: {context}"
            )


def test_system_prompt_schema_injection(jinja_env: Environment):
    """System prompt includes schema injection placeholder."""
    template = jinja_env.get_template("system.j2")
    response_schema = "TEST_SCHEMA_PLACEHOLDER"

    result = template.render(response_schema=response_schema)

    assert "TEST_SCHEMA_PLACEHOLDER" in result


# ============================================================================
# User Prompt Tests
# ============================================================================


def test_user_prompt_renders(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt renders without errors."""
    template = jinja_env.get_template("user.j2")

    result = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )

    assert len(result) > 0


def test_user_prompt_song_information(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt includes song information."""
    template = jinja_env.get_template("user.j2")

    result = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )

    assert audio_profile.song_identity.title in result
    assert (
        str(audio_profile.song_identity.bpm) in result
        or f"{audio_profile.song_identity.bpm:.1f}" in result
    )


def test_user_prompt_song_structure(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt includes song structure sections."""
    template = jinja_env.get_template("user.j2")

    result = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )

    # Check for first section
    first_section = audio_profile.structure.sections[0]
    assert first_section.name in result


def test_user_prompt_display_groups(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt includes display groups."""
    template = jinja_env.get_template("user.j2")

    result = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )

    for group in display_groups:
        assert group["role_key"] in result


def test_user_prompt_macro_plan_content(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt includes MacroPlan content."""
    template = jinja_env.get_template("user.j2")

    result = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )

    # Check global story
    assert valid_macro_plan.global_story.theme in result

    # Check layers
    for layer in valid_macro_plan.layering_plan.layers:
        assert str(layer.layer_index) in result
        assert layer.layer_role.value in result


def test_user_prompt_iteration_awareness(
    jinja_env: Environment,
    audio_profile: AudioProfileModel,
    display_groups: list[dict],
    valid_macro_plan: MacroPlan,
):
    """User prompt shows iteration awareness."""
    template = jinja_env.get_template("user.j2")

    # Iteration 1
    result1 = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=1,
    )
    assert "Iteration 1" in result1 or "Initial" in result1 or "first" in result1.lower()

    # Iteration 2
    result2 = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        macro_plan=valid_macro_plan,
        iteration=2,
    )
    assert "Iteration 2" in result2 or "refined" in result2.lower()


# ============================================================================
# Developer Prompt Tests
# ============================================================================


def test_developer_prompt_renders(jinja_env: Environment):
    """Developer prompt renders without errors."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1)

    assert len(result) > 0


def test_developer_prompt_technical_constraints(jinja_env: Environment):
    """Developer prompt includes technical constraints."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1)

    assert "macro-plan.v2" in result  # Schema version
    assert "10.0" in result  # Score range
    assert "0.0" in result  # Min score/confidence


def test_developer_prompt_enum_listings(jinja_env: Environment):
    """Developer prompt lists all relevant enums."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1)

    # Check for enum names (should be listed)
    assert "EnergyTarget" in result
    assert "ChoreographyStyle" in result
    assert "MotionDensity" in result
    assert "TargetRole" in result
    assert "LayerRole" in result


def test_developer_prompt_iteration_context(jinja_env: Environment):
    """Developer prompt provides iteration-specific context."""
    template = jinja_env.get_template("developer.j2")

    # Iteration 1
    result1 = template.render(iteration=1)
    assert "first" in result1.lower() or "iteration 1" in result1.lower()

    # Iteration 2
    result2 = template.render(iteration=2)
    assert "iteration 2" in result2.lower() or "previous" in result2.lower()


# ============================================================================
# Pack YAML Tests
# ============================================================================


def test_pack_yaml_valid():
    """pack.yaml is valid YAML and loadable."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        data = yaml.safe_load(f)

    assert data is not None
    assert isinstance(data, dict)


def test_pack_yaml_structure():
    """pack.yaml has required structure."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        data = yaml.safe_load(f)

    assert "pack_id" in data
    assert "version" in data
    assert "agent_type" in data
    assert "templates" in data
    assert "variables" in data


def test_pack_yaml_templates_complete():
    """pack.yaml lists all required templates."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        data = yaml.safe_load(f)

    templates = data["templates"]
    assert "system" in templates
    assert "user" in templates
    assert "developer" in templates

    assert templates["system"] == "system.j2"
    assert templates["user"] == "user.j2"
    assert templates["developer"] == "developer.j2"


def test_pack_yaml_variables_documented():
    """pack.yaml documents all required variables."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        data = yaml.safe_load(f)

    variables = data["variables"]
    var_names = [v["name"] for v in variables]

    assert "audio_profile" in var_names
    assert "display_groups" in var_names
    assert "macro_plan" in var_names
    assert "iteration" in var_names


def test_pack_yaml_agent_type():
    """pack.yaml has correct agent type."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "judge"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        data = yaml.safe_load(f)

    assert data["agent_type"] == "judge"
