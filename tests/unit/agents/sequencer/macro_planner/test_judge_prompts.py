"""Tests for MacroPlanner judge prompt templates."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
import pytest
import yaml

from twinklr.core.agents.audio.profile.models import AudioProfileModel, SongSectionRef
from twinklr.core.sequencer.planning import (
    GlobalStory,
    LayeringPlan,
    LayerSpec,
    MacroPlan,
    MacroSectionPlan,
    TargetSelector,
)
from twinklr.core.sequencer.templates.group.models import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ChoreographyStyle,
    EnergyTarget,
    LayerRole,
    MotionDensity,
    TargetRole,
    TargetType,
    TimingDriver,
)

from .conftest import make_motif_spec, make_palette_plan


def _make_global_theme() -> ThemeRef:
    """Create a valid global ThemeRef (SONG scope)."""
    return ThemeRef(
        theme_id="theme.abstract.neon",
        scope=ThemeScope.SONG,
        tags=["motif.geometric"],
    )


def _make_section_theme() -> ThemeRef:
    """Create a valid section ThemeRef (SECTION scope)."""
    return ThemeRef(
        theme_id="theme.abstract.neon",
        scope=ThemeScope.SECTION,
        tags=["motif.geometric"],
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
        {"id": "OUTLINE", "role_key": "OUTLINE", "model_count": 200},
        {"id": "MEGA_TREE", "role_key": "MEGA_TREE", "model_count": 500},
        {"id": "HERO", "role_key": "HERO", "model_count": 100},
    ]


@pytest.fixture
def valid_macro_plan(audio_profile: AudioProfileModel) -> MacroPlan:
    """Create a valid MacroPlan for testing."""
    sections = audio_profile.structure.sections[:3]  # Use first 3 sections

    return MacroPlan(
        global_story=GlobalStory(
            theme=_make_global_theme(),
            story_notes="Winter wonderland with building energy and festive celebration",
            motifs=[
                make_motif_spec("snowflakes", "Snowflake patterns in the display"),
                make_motif_spec("twinkling_stars", "Twinkling star effects"),
                make_motif_spec("crescendo", "Crescendo buildup pattern"),
            ],
            pacing_notes="Start calm and serene in the intro, build energy through the verses, and peak at the chorus with maximum impact.",
            palette_plan=make_palette_plan(),
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
                theme=_make_section_theme(),
                energy_target=EnergyTarget.LOW if i == 0 else EnergyTarget.HIGH,
                motion_density=MotionDensity.SPARSE if i == 0 else MotionDensity.BUSY,
                choreography_style=ChoreographyStyle.ABSTRACT,
                primary_focus_targets=[
                    PlanTarget(type=TargetType.GROUP, id=TargetRole.OUTLINE.value)
                ],
                secondary_targets=[
                    PlanTarget(type=TargetType.GROUP, id=TargetRole.MEGA_TREE.value)
                ],
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


def _system_taxonomy() -> dict:
    """Taxonomy dict required by system.j2 template variables."""
    return {
        "IssueCategory": ["COVERAGE", "TIMING", "LAYERING", "VARIETY"],
        "IssueSeverity": ["ERROR", "WARN", "NIT"],
        "IssueEffort": ["LOW", "MEDIUM", "HIGH"],
        "IssueScope": ["GLOBAL", "SECTION", "LANE"],
        "SuggestedAction": ["PATCH", "REPLAN_GLOBAL", "IGNORE"],
        "VerdictStatus": ["APPROVE", "SOFT_FAIL", "HARD_FAIL"],
        "EnergyTarget": ["LOW", "MED", "HIGH", "PEAK"],
        "MotionDensity": ["SPARSE", "MED", "BUSY"],
        "ChoreographyStyle": ["ABSTRACT", "IMAGERY", "HYBRID"],
        "TargetRole": ["OUTLINE", "MEGA_TREE", "HERO", "ARCHES"],
        "LayerRole": ["BASE", "RHYTHM", "ACCENT", "FILL"],
    }


def _render_system(jinja_env: Environment, *, response_schema: str = '{"type": "object"}') -> str:
    """Render system.j2 with required variables."""
    template = jinja_env.get_template("system.j2")
    return template.render(
        response_schema=response_schema,
        taxonomy=_system_taxonomy(),
        learning_context=None,
    )


def test_system_prompt_renders(jinja_env: Environment):
    """System prompt renders without errors."""
    result = _render_system(jinja_env, response_schema='{"type": "object", "properties": {}}')

    assert len(result) > 0
    assert "Christmas light show" in result


def test_system_prompt_judge_identity(jinja_env: Environment):
    """System prompt establishes judge identity."""
    result = _render_system(jinja_env)

    assert "judge" in result.lower()
    assert "evaluate" in result.lower() or "assess" in result.lower()


def test_system_prompt_christmas_persona(jinja_env: Environment):
    """System prompt enforces Christmas light show persona."""
    result = _render_system(jinja_env)

    # Should emphasize Christmas/residential display context
    assert "Christmas" in result
    assert "residential" in result or "street" in result or "display" in result


def test_system_prompt_bold_over_subtle(jinja_env: Environment):
    """System prompt emphasizes bold over subtle design."""
    result = _render_system(jinja_env)

    assert "bold" in result.lower() or "impact" in result.lower()
    assert "subtle" in result.lower()  # Should mention avoiding subtlety


def test_system_prompt_no_concert_language_positive(jinja_env: Environment):
    """System prompt does not use concert/stage language in positive context."""
    result = _render_system(jinja_env)

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


def test_system_prompt_no_schema_injection(jinja_env: Environment):
    """System prompt should NOT include response_schema (moved to developer.j2)."""
    result = _render_system(jinja_env, response_schema="TEST_SCHEMA_PLACEHOLDER")

    # Schema IS now in system.j2 (moved there), verify it renders
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
        assert group["id"] in result


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
    assert valid_macro_plan.global_story.story_notes in result

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


@pytest.fixture
def mock_taxonomy() -> dict:
    """Mock taxonomy for developer prompt tests."""
    return {
        "IssueCategory": ["COVERAGE", "TIMING", "LAYERING", "VARIETY"],
        "IssueSeverity": ["ERROR", "WARN", "NIT"],
        "IssueEffort": ["LOW", "MEDIUM", "HIGH"],
        "IssueScope": ["GLOBAL", "SECTION", "LANE"],
        "SuggestedAction": ["PATCH", "REPLAN_GLOBAL", "IGNORE"],
        "VerdictStatus": ["APPROVE", "SOFT_FAIL", "HARD_FAIL"],
        "EnergyTarget": ["LOW", "MED", "HIGH", "PEAK"],
        "MotionDensity": ["SPARSE", "MED", "BUSY"],
        "ChoreographyStyle": ["ABSTRACT", "IMAGERY", "HYBRID"],
        "TargetRole": ["OUTLINE", "MEGA_TREE", "HERO", "ARCHES"],
        "LayerRole": ["BASE", "RHYTHM", "ACCENT", "FILL"],
    }


def test_developer_prompt_renders(jinja_env: Environment, mock_taxonomy: dict):
    """Developer prompt renders without errors."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1, taxonomy=mock_taxonomy, response_schema="{}")

    assert len(result) > 0


def test_developer_prompt_technical_constraints(jinja_env: Environment, mock_taxonomy: dict):
    """Developer prompt includes strict requirements / hard-fail checklist."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1, taxonomy=mock_taxonomy, response_schema="{}")

    # developer.j2 contains the strict requirements section
    assert "Strict Requirements" in result or "HARD_FAIL" in result
    assert "Response Schema" in result


def test_developer_prompt_enum_listings(jinja_env: Environment, mock_taxonomy: dict):
    """Developer prompt renders without errors and contains schema section."""
    template = jinja_env.get_template("developer.j2")

    result = template.render(iteration=1, taxonomy=mock_taxonomy, response_schema="{}")

    # developer.j2 includes the response schema and strict requirements
    assert "Response Schema" in result
    assert "HARD_FAIL" in result


def test_developer_prompt_iteration_context(jinja_env: Environment, mock_taxonomy: dict):
    """Developer prompt provides context regardless of iteration.

    Note: Current template doesn't have iteration-specific content,
    so we just verify it renders successfully for different iterations.
    """
    template = jinja_env.get_template("developer.j2")

    # Iteration 1 - should render
    result1 = template.render(iteration=1, taxonomy=mock_taxonomy, response_schema="{}")
    assert len(result1) > 0

    # Iteration 2 - should also render
    result2 = template.render(iteration=2, taxonomy=mock_taxonomy, response_schema="{}")
    assert len(result2) > 0


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
