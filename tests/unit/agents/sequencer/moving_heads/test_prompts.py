"""Tests for moving heads prompt packs."""

from pathlib import Path

import pytest

from twinklr.core.agents.prompts import PromptPackLoader, PromptRenderer

PROMPTS_BASE = (
    Path(__file__).parent.parent.parent.parent.parent.parent
    / "packages"
    / "twinklr"
    / "core"
    / "agents"
    / "sequencer"
    / "moving_heads"
    / "prompts"
)


@pytest.fixture
def prompt_loader():
    """Create prompt loader."""
    return PromptPackLoader(base_path=PROMPTS_BASE)


@pytest.fixture
def renderer():
    """Create prompt renderer."""
    return PromptRenderer()


def test_planner_prompts_exist():
    """Test planner prompt files exist."""
    planner_dir = PROMPTS_BASE / "planner"
    assert planner_dir.exists()
    assert (planner_dir / "system.j2").exists()
    assert (planner_dir / "developer.j2").exists()
    assert (planner_dir / "user.j2").exists()


def test_judge_prompts_exist():
    """Test judge prompt files exist."""
    judge_dir = PROMPTS_BASE / "judge"
    assert judge_dir.exists()
    assert (judge_dir / "system.j2").exists()
    assert (judge_dir / "developer.j2").exists()
    assert (judge_dir / "user.j2").exists()


def test_load_planner_prompts(prompt_loader):
    """Test loading planner prompts."""
    prompts = prompt_loader.load("planner")

    assert "system" in prompts
    assert "developer" in prompts
    assert "user" in prompts
    assert len(prompts["system"]) > 0
    assert len(prompts["developer"]) > 0
    assert len(prompts["user"]) > 0


def test_load_judge_prompts(prompt_loader):
    """Test loading judge prompts."""
    prompts = prompt_loader.load("judge")

    assert "system" in prompts
    assert "developer" in prompts
    assert "user" in prompts
    assert len(prompts["system"]) > 0
    assert len(prompts["developer"]) > 0
    assert len(prompts["user"]) > 0


def test_render_planner_user_prompt(prompt_loader, renderer):
    """Test rendering planner user prompt with variables (V2 format)."""
    prompts = prompt_loader.load("planner")

    # V2 context format (direct variables, not nested context)
    variables = {
        "iteration": 0,  # Initial planning
        "song_title": "Test Song",
        "song_artist": "Test Artist",
        "genre": None,
        "tempo": 120.0,
        "time_signature": "4/4",
        "total_bars": 32,
        "fixture_count": 4,
        "fixture_groups": ["front", "back"],
        "available_templates": ["template1", "template2"],
        "sections": [
            {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
            {"section_id": "verse", "name": "verse", "start_bar": 9, "end_bar": 24},
        ],
        "audio_profile": None,
        "lyric_context": None,
        "response_schema": "{}",
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should contain rendered content
    assert "intro" in rendered
    assert "120" in rendered  # tempo
    assert "4 moving heads" in rendered


def test_render_planner_with_feedback(prompt_loader, renderer):
    """Test rendering planner prompt with feedback (refinement mode)."""
    prompts = prompt_loader.load("planner")

    # V2 context with iteration > 0 (refinement mode)
    variables = {
        "iteration": 1,  # Refinement mode
        "song_title": "Test Song",
        "song_artist": None,
        "tempo": 120.0,
        "time_signature": "4/4",
        "total_bars": 32,
        "fixture_count": 4,
        "feedback": "- Needs more variety in verse\n- Chorus energy too low",
        "revision_focus": None,
        "response_schema": "{}",
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should include refinement context
    assert "Refinement Request" in rendered
    assert "variety" in rendered.lower() or "energy" in rendered.lower()


def test_render_judge_user_prompt(prompt_loader, renderer):
    """Test rendering judge user prompt (V2 format)."""
    prompts = prompt_loader.load("judge")

    # V2 context format
    variables = {
        "plan": {"sections": [{"section_name": "intro", "template_id": "sweep"}]},
        "sections": [
            {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
        ],
        "total_bars": 32,
        "tempo": 120.0,
        "time_signature": "4/4",
        "available_templates": ["sweep", "circle"],
        "iteration": 0,
        "previous_feedback": [],
        "previous_issues": [],
        "audio_profile": None,
        "response_schema": "{}",
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should contain plan
    assert "intro" in rendered
    assert "Evaluation" in rendered


def test_render_judge_with_iteration(prompt_loader, renderer):
    """Test rendering judge prompt with iteration info."""
    prompts = prompt_loader.load("judge")

    # V2 context format with iteration > 0
    variables = {
        "plan": {"sections": []},
        "sections": [
            {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
        ],
        "total_bars": 32,
        "tempo": 120.0,
        "time_signature": "4/4",
        "available_templates": ["sweep"],
        "iteration": 2,  # Will display as "iteration 3"
        "previous_feedback": ["Fix timing", "Add variety"],
        "previous_issues": [],
        "audio_profile": None,
        "response_schema": "{}",
    }

    rendered = renderer.render(prompts["user"], variables)

    # Should show iteration context
    assert "iteration 3" in rendered.lower()
    assert "Fix timing" in rendered


def test_all_prompts_have_required_keys(prompt_loader):
    """Test all prompt packs have required prompts."""
    for pack_name in ["planner", "judge"]:
        prompts = prompt_loader.load(pack_name)

        # All should have system, developer, and user
        assert "system" in prompts, f"{pack_name} missing system prompt"
        assert "developer" in prompts, f"{pack_name} missing developer prompt"
        assert "user" in prompts, f"{pack_name} missing user prompt"

        # Should be non-empty
        assert len(prompts["system"]) > 100, f"{pack_name} system prompt too short"
        assert len(prompts["developer"]) > 100, f"{pack_name} developer prompt too short"
        assert len(prompts["user"]) > 100, f"{pack_name} user prompt too short"


def test_prompts_contain_key_concepts():
    """Test prompts contain domain-specific concepts."""
    loader = PromptPackLoader(base_path=PROMPTS_BASE)

    # Planner should mention templates, choreography
    planner = loader.load("planner")
    assert "template" in planner["system"].lower() or "template" in planner["developer"].lower()
    assert "choreography" in planner["system"].lower()

    # Judge should mention evaluation, quality
    judge = loader.load("judge")
    judge_system = judge["system"].lower()
    assert "evaluat" in judge_system or "judge" in judge_system

    # Developer prompts should mention technical details
    planner_dev = planner["developer"].lower()
    assert "schema" in planner_dev or "json" in planner_dev

    judge_dev = judge["developer"].lower()
    assert "schema" in judge_dev or "json" in judge_dev


# =============================================================================
# V2 Prompt Tests
# =============================================================================


class TestV2PlannerPrompts:
    """Tests for V2 iteration-aware planner prompts."""

    @pytest.fixture
    def v2_context_iteration_0(self):
        """V2 context for iteration 0 (initial planning)."""
        return {
            "iteration": 0,
            "song_title": "Need A Favor",
            "song_artist": "Jelly Roll",
            "genre": None,  # Optional
            "tempo": 120.0,
            "time_signature": "4/4",
            "total_bars": 90,
            "fixture_count": 4,
            "fixture_groups": [],
            "available_templates": ["sweep_lr_fan_pulse", "circle_fan_hold"],
            "sections": [
                {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
                {"section_id": "verse_1", "name": "verse", "start_bar": 9, "end_bar": 24},
            ],
            "audio_profile": None,
            "lyric_context": None,
            "response_schema": "{}",
        }

    @pytest.fixture
    def v2_context_iteration_1(self, v2_context_iteration_0):
        """V2 context for iteration 1 (refinement)."""
        ctx = v2_context_iteration_0.copy()
        ctx["iteration"] = 1
        ctx["feedback"] = "- Increase variety in verse sections\n- Add more energy to chorus"
        ctx["revision_focus"] = ["VARIETY: Verse sections need more template variety"]
        return ctx

    def test_planner_user_refinement_prompt_exists(self):
        """Test refinement prompt file exists."""
        refinement_path = PROMPTS_BASE / "planner" / "user_refinement.j2"
        assert refinement_path.exists(), "user_refinement.j2 should exist"

    def test_render_planner_initial_iteration(
        self, prompt_loader, renderer, v2_context_iteration_0
    ):
        """Test planner user prompt renders full context on iteration 0."""
        prompts = prompt_loader.load("planner")
        rendered = renderer.render(prompts["user"], v2_context_iteration_0)

        # Should contain full context
        assert "Need A Favor" in rendered
        assert "sweep_lr_fan_pulse" in rendered
        assert "Section" in rendered  # Section table header
        assert "intro" in rendered

    def test_render_planner_refinement_iteration(
        self, prompt_loader, renderer, v2_context_iteration_1
    ):
        """Test planner user prompt renders minimal context on iteration 1+."""
        prompts = prompt_loader.load("planner")
        rendered = renderer.render(prompts["user"], v2_context_iteration_1)

        # Should contain refinement context
        assert "Refinement Request" in rendered
        assert "Iteration 2" in rendered  # iteration 1 + 1 = 2
        assert "Feedback to Address" in rendered or "feedback" in rendered.lower()

        # Should NOT contain full template list (token optimization)
        # Full template list is only in iteration 0

    def test_render_planner_developer_with_learning_context(self, prompt_loader, renderer):
        """Test planner developer prompt includes learning context."""
        prompts = prompt_loader.load("planner")
        variables = {
            "response_schema": '{"type": "object"}',
            "learning_context": "Based on 5 recent issues:\n- VARIETY: 60% occurrence",
        }

        rendered = renderer.render(prompts["developer"], variables)

        assert "Learning Context" in rendered
        assert "VARIETY" in rendered

    def test_render_planner_developer_without_learning_context(self, prompt_loader, renderer):
        """Test planner developer prompt works without learning context."""
        prompts = prompt_loader.load("planner")
        variables = {
            "response_schema": '{"type": "object"}',
            "learning_context": None,  # Explicitly None
        }

        rendered = renderer.render(prompts["developer"], variables)

        assert "Learning Context" not in rendered
        assert "Response Schema" in rendered


class TestV2JudgePrompts:
    """Tests for V2 judge prompts with JudgeVerdict schema."""

    @pytest.fixture
    def v2_judge_context(self):
        """V2 context for judge evaluation."""
        return {
            "plan": {
                "sections": [
                    {"section_name": "intro", "start_bar": 1, "end_bar": 8, "template_id": "sweep"}
                ],
                "overall_strategy": "Build energy progressively",
            },
            "sections": [
                {"section_id": "intro", "name": "intro", "start_bar": 1, "end_bar": 8},
            ],
            "total_bars": 90,
            "tempo": 120.0,
            "time_signature": "4/4",
            "available_templates": ["sweep", "circle"],
            "iteration": 0,
            "previous_feedback": [],
            "previous_issues": [],
            "audio_profile": None,
            "response_schema": '{"type": "object"}',
        }

    def test_render_judge_user_prompt(self, prompt_loader, renderer, v2_judge_context):
        """Test judge user prompt renders with V2 context."""
        prompts = prompt_loader.load("judge")
        rendered = renderer.render(prompts["user"], v2_judge_context)

        assert "intro" in rendered
        assert "sweep" in rendered
        assert "Evaluation" in rendered

    def test_render_judge_user_with_iteration(self, prompt_loader, renderer, v2_judge_context):
        """Test judge user prompt shows iteration context."""
        ctx = v2_judge_context.copy()
        ctx["iteration"] = 2
        ctx["previous_feedback"] = ["Fix timing overlap", "Add variety"]
        ctx["previous_issues"] = [
            {"issue_id": "TIMING_OVERLAP", "severity": "ERROR", "message": "Sections overlap"}
        ]

        prompts = prompt_loader.load("judge")
        rendered = renderer.render(prompts["user"], ctx)

        assert "iteration 3" in rendered.lower()  # iteration 2 + 1
        assert "Fix timing overlap" in rendered
        assert "TIMING_OVERLAP" in rendered

    def test_judge_developer_references_judge_verdict(self, prompt_loader):
        """Test judge developer prompt references JudgeVerdict (not JudgeResponse)."""
        prompts = prompt_loader.load("judge")
        developer = prompts["developer"]

        # Should reference JudgeVerdict
        assert "JudgeVerdict" in developer
        # Should have VerdictStatus enum values
        assert "APPROVE" in developer
        assert "SOFT_FAIL" in developer
        assert "HARD_FAIL" in developer

    def test_judge_developer_with_learning_context(self, prompt_loader, renderer):
        """Test judge developer prompt includes learning context."""
        prompts = prompt_loader.load("judge")
        variables = {
            "response_schema": '{"type": "object"}',
            "learning_context": "Based on 10 recent issues:\n- TIMING: 40% occurrence",
        }

        rendered = renderer.render(prompts["developer"], variables)

        assert "Learning Context" in rendered
        assert "TIMING" in rendered
