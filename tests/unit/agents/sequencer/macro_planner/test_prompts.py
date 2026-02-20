"""Tests for MacroPlanner prompt templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest
import yaml

from twinklr.core.agents.audio.profile.models import AudioProfileModel


@pytest.fixture
def jinja_env() -> Environment:
    """Create Jinja2 environment for prompt templates."""
    prompts_dir = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
    )

    env = Environment(
        loader=FileSystemLoader(prompts_dir),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


@pytest.fixture
def audio_profile() -> AudioProfileModel:
    """Load audio profile fixture."""
    import json

    fixture_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "fixtures"
        / "audio_profile"
        / "audio_profile_model.json"
    )
    with fixture_path.open() as f:
        data = json.load(f)
    return AudioProfileModel(**data)


@pytest.fixture
def display_groups() -> list:
    """Create mock display groups."""
    return [
        {"id": "OUTLINE", "role_key": "OUTLINE", "group_type": "outline", "model_count": 200},
        {
            "id": "MEGA_TREE",
            "role_key": "MEGA_TREE",
            "group_type": "mega_tree",
            "model_count": 300,
        },
        {"id": "ARCHES", "role_key": "ARCHES", "group_type": "arches", "model_count": 150},
    ]


# ============================================================================
# Task 1.3.1: System Prompt Tests
# ============================================================================


def test_system_prompt_renders(jinja_env: Environment):
    """System prompt renders without errors."""
    template = jinja_env.get_template("planner/system.j2")

    output = template.render()

    assert output
    assert len(output) > 100
    # Schema should NOT be in system prompt (it's in developer.j2)
    # Just verify the prompt renders and has substantial content


def test_system_prompt_christmas_identity(jinja_env: Environment):
    """System prompt enforces Christmas light show identity."""
    template = jinja_env.get_template("planner/system.j2")
    output = template.render(response_schema="schema")

    # Must contain Christmas/light show identity
    assert "Christmas light show" in output or "Christmas light" in output
    assert "designer" in output.lower()

    # Must NOT be concert/stage production
    assert "NOT" in output or "not" in output
    if "concert" in output.lower():
        # If concert mentioned, must be negated
        idx = output.lower().index("concert")
        surrounding = output.lower()[max(0, idx - 30) : idx]
        assert "not" in surrounding or "NOT" in surrounding


def test_system_prompt_main_character_energy(jinja_env: Environment):
    """System prompt includes 'main character energy' concept."""
    template = jinja_env.get_template("planner/system.j2")
    output = template.render(response_schema="schema")

    # Check for main character concept
    assert "main character" in output.lower() or "lights ARE the show" in output


def test_system_prompt_bold_over_subtle(jinja_env: Environment):
    """System prompt emphasizes bold over subtle."""
    template = jinja_env.get_template("planner/system.j2")
    output = template.render(response_schema="schema")

    assert "bold" in output.lower()
    assert "subtle" in output.lower()


def test_system_prompt_strategy_vs_execution(jinja_env: Environment):
    """System prompt clarifies strategy vs execution."""
    template = jinja_env.get_template("planner/system.j2")
    output = template.render(response_schema="schema")

    # Should mention WHAT/WHY vs HOW
    assert "WHAT" in output or "what" in output
    assert "WHY" in output or "why" in output or "HOW" in output or "how" in output


def test_system_prompt_no_forbidden_terms(jinja_env: Environment):
    """System prompt avoids forbidden concert/stage terms in positive context."""
    template = jinja_env.get_template("planner/system.j2")
    output = template.render(response_schema="schema")

    # These terms should only appear if negated
    forbidden_positive = ["nightclub"]

    for term in forbidden_positive:
        if term in output.lower():
            # Find context around term (larger window)
            idx = output.lower().index(term)
            context = output.lower()[max(0, idx - 50) : idx + len(term) + 10]
            # Should have "NOT" or "not" nearby
            assert "not" in context, f"Term '{term}' used without negation: ...{context}..."


# ============================================================================
# Task 1.3.2: User Prompt Tests
# ============================================================================


def test_user_prompt_renders(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User prompt renders without errors."""
    template = jinja_env.get_template("planner/user.j2")

    output = template.render(audio_profile=audio_profile, display_groups=display_groups)

    assert output
    assert len(output) > 200


def test_user_prompt_includes_song_info(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User prompt includes song information."""
    template = jinja_env.get_template("planner/user.j2")
    output = template.render(audio_profile=audio_profile, display_groups=display_groups)

    # Check for song identity fields
    assert audio_profile.song_identity.title in output or "Untitled" in output
    assert str(audio_profile.song_identity.bpm) in output or "bpm" in output.lower()


def test_user_prompt_includes_sections(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User prompt lists all song sections."""
    template = jinja_env.get_template("planner/user.j2")
    output = template.render(audio_profile=audio_profile, display_groups=display_groups)

    # Check that sections are listed
    assert "Song Structure" in output or "Structure" in output
    # Check first few sections are mentioned
    for section in audio_profile.structure.sections[:3]:
        assert section.section_id in output or section.name in output


def test_user_prompt_includes_display_groups(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User prompt lists display groups."""
    template = jinja_env.get_template("planner/user.j2")
    output = template.render(audio_profile=audio_profile, display_groups=display_groups)

    # Check display groups are listed
    assert "OUTLINE" in output
    assert "MEGA_TREE" in output
    assert "ARCHES" in output


def test_user_prompt_no_iteration_feedback(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User prompt without iteration doesn't show feedback section."""
    template = jinja_env.get_template("planner/user.j2")
    output = template.render(audio_profile=audio_profile, display_groups=display_groups)

    # Should NOT show iteration feedback
    assert "Iteration" not in output or "iteration" not in output.lower()
    assert "Feedback" not in output or "feedback" not in output.lower()


def test_user_prompt_with_iteration_feedback(
    jinja_env: Environment, audio_profile: AudioProfileModel, display_groups: list
):
    """User refinement prompt with iteration shows feedback section."""
    # For iteration > 0, we use user_refinement.j2
    template = jinja_env.get_template("planner/user_refinement.j2")
    output = template.render(
        audio_profile=audio_profile,
        display_groups=display_groups,
        iteration=2,
        revision_request={"priority": "SOFT_FAIL", "focus_areas": ["energy contrast"]},
        feedback="Add more energy contrast between sections",
    )

    # Should show iteration and revision context
    assert "2" in output  # Iteration number
    assert "energy contrast" in output.lower() or "SOFT_FAIL" in output


# ============================================================================
# Task 1.3.3: Developer Prompt & Pack Tests
# ============================================================================


def test_developer_prompt_renders(jinja_env: Environment):
    """Developer prompt renders without errors."""
    template = jinja_env.get_template("planner/developer.j2")

    output = template.render()

    assert output
    assert len(output) > 50


def test_developer_prompt_includes_constraints(jinja_env: Environment):
    """Developer prompt includes technical constraints."""
    template = jinja_env.get_template("planner/developer.j2")
    output = template.render()

    # Should mention key constraints
    assert "BASE" in output
    assert "NORMAL" in output or "ADD" in output
    assert "5" in output or "max" in output.lower()


def test_developer_prompt_lists_enums(jinja_env: Environment):
    """Developer prompt lists enum values."""
    template = jinja_env.get_template("planner/developer.j2")
    output = template.render()

    # Should list key enums
    assert "LayerRole" in output or "RHYTHM" in output
    assert "EnergyTarget" in output or "LOW" in output or "HIGH" in output
    assert "TargetType" in output or "group" in output or "zone" in output


def test_pack_yaml_valid():
    """Pack YAML is valid and complete."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "planner"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        pack_data = yaml.safe_load(f)

    # Check required fields
    assert pack_data["pack_id"] == "macro_planner.v2"
    assert "version" in pack_data
    assert "templates" in pack_data

    # Check all templates listed
    templates = pack_data["templates"]
    assert "system" in templates
    assert "user" in templates
    assert "developer" in templates

    # Check template files match
    assert templates["system"] == "system.j2"
    assert templates["user"] == "user.j2"
    assert templates["developer"] == "developer.j2"


def test_pack_yaml_documents_variables():
    """Pack YAML documents required and optional variables."""
    pack_path = (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "sequencer"
        / "macro_planner"
        / "prompts"
        / "planner"
        / "pack.yaml"
    )

    with pack_path.open() as f:
        pack_data = yaml.safe_load(f)

    # Check variables section
    assert "variables" in pack_data
    variables = pack_data["variables"]

    # Check required variables
    assert "required" in variables
    required = variables["required"]
    assert "audio_profile" in required
    assert "display_groups" in required
    assert "response_schema" in required

    # Check optional variables
    assert "optional" in variables
    optional = variables["optional"]
    assert "iteration" in optional
    assert "feedback" in optional
