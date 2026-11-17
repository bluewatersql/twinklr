"""Tests for moving heads prompt packs."""

from itertools import pairwise
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
        "revision_request": {
            "priority": "SOFT_FAIL",
            "focus_areas": ["variety", "energy"],
            "specific_fixes": ["Needs more variety in verse", "Chorus energy too low"],
            "avoid": [],
        },
        "revision_focus": [],
        "preserve_elements": [],
        "response_schema": "{}",
    }

    # Use load_with_refinement to get the refinement template for iteration > 0
    prompts = prompt_loader.load_with_refinement("planner", variables)
    rendered = renderer.render(prompts["user"], variables)

    # Should include refinement context
    assert "SOFT_FAIL" in rendered or "variety" in rendered.lower() or "energy" in rendered.lower()


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
        ctx["revision_request"] = {
            "priority": "SOFT_FAIL",
            "focus_areas": ["variety", "energy"],
            "specific_fixes": [
                "Increase variety in verse sections",
                "Add more energy to chorus",
            ],
            "avoid": [],
        }
        ctx["revision_focus"] = []
        ctx["preserve_elements"] = []
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
        # Use load_with_refinement to get the refinement template for iteration > 0
        prompts = prompt_loader.load_with_refinement("planner", v2_context_iteration_1)
        rendered = renderer.render(prompts["user"], v2_context_iteration_1)

        # Should contain refinement context (priority and focus areas)
        assert (
            "SOFT_FAIL" in rendered or "variety" in rendered.lower() or "energy" in rendered.lower()
        )

        # Should NOT contain full template list (token optimization)
        # Full template list is only in iteration 0

    def test_refinement_reports_what_repair_changed(
        self, prompt_loader, renderer, v2_context_iteration_1
    ):
        """The repairs of the last plan reach the next planning prompt, one per line."""
        context = {
            **v2_context_iteration_1,
            "plan_repairs": [
                "section 'chorus_1': moment cue 'ghost' dropped: no lyric moment cue has id 'ghost'"
            ],
        }
        prompts = prompt_loader.load_with_refinement("planner", context)
        rendered = renderer.render(prompts["user"], context)

        assert "What Deterministic Repair Changed" in rendered
        assert "- section 'chorus_1': moment cue 'ghost' dropped" in rendered
        quiet = renderer.render(prompts["user"], v2_context_iteration_1)
        assert "What Deterministic Repair Changed" not in quiet

    def test_initial_prompt_shows_each_section_palette_colours(
        self, prompt_loader, renderer, v2_context_iteration_0
    ):
        macro_section = {
            "section_id": "intro",
            "energy_target": "LOW",
            "motion_density": "SPARSE",
            "choreography_style": "HYBRID",
            "palette_id": "core.christmas_traditional",
            "palette_colors": [{"hex": "#C8102E", "name": "red"}, {"hex": "#00843D", "name": None}],
            "motif_ids": [],
            "coordination_intent": "UNIFIED",
            "notes": "Open warmly.",
        }
        context = {
            **v2_context_iteration_0,
            "macro_plan": [macro_section],
            "macro_palette_arc": [],
            "macro_motif_continuity": [],
            "macro_focal_arc": [],
        }
        rendered = renderer.render(prompt_loader.load("planner")["user"], context)

        assert "- **intro**: #C8102E red, #00843D (`core.christmas_traditional`)\n" in rendered

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
        ctx["previous_verdicts"] = [
            {
                "status": "SOFT_FAIL",
                "score": 6.2,
                "confidence": 0.9,
                "feedback_for_planner": "Fix timing overlap and add variety",
                "iteration": 1,
            }
        ]
        ctx["previous_feedback"] = ["Fix timing overlap", "Add variety"]
        ctx["previous_issues"] = [
            {"issue_id": "TIMING_OVERLAP", "severity": "ERROR", "message": "Sections overlap"}
        ]

        prompts = prompt_loader.load("judge")
        rendered = renderer.render(prompts["user"], ctx)

        assert "iteration 3" in rendered.lower()  # iteration 2 + 1
        assert "SOFT_FAIL" in rendered
        assert "score 6.2" in rendered
        assert "Fix timing overlap" in rendered
        assert "TIMING_OVERLAP" in rendered

    def test_judge_history_block_renders(self, prompt_loader, renderer, v2_judge_context):
        """Iteration two renders the actual prior verdict summary and issue."""
        ctx = v2_judge_context.copy()
        ctx.update(
            {
                "iteration": 1,
                "previous_verdicts": [
                    {
                        "status": "HARD_FAIL",
                        "score": 4.5,
                        "confidence": 0.8,
                        "feedback_for_planner": "Repair the chorus timing.",
                        "iteration": 0,
                    }
                ],
                "previous_feedback": ["Repair the chorus timing."],
                "previous_issues": [
                    {
                        "issue_id": "CHORUS_TIMING",
                        "severity": "ERROR",
                        "message": "The chorus starts outside its bar range.",
                    }
                ],
                "previous_revision_requests": [
                    {
                        "focus_areas": ["Timing"],
                        "specific_fixes": ["Move the chorus start to bar 9"],
                    }
                ],
            }
        )

        rendered = renderer.render(prompt_loader.load("judge")["user"], ctx)

        assert "Prior Verdicts" in rendered
        assert "HARD_FAIL" in rendered
        assert "Repair the chorus timing." in rendered
        assert "CHORUS_TIMING" in rendered
        assert "Prior Revision Requests" in rendered
        assert "Move the chorus start to bar 9" in rendered

    def test_judge_developer_renders_configured_thresholds(self, prompt_loader, renderer) -> None:
        """The prompt uses the same thresholds the controller enforces."""
        rendered = renderer.render(
            prompt_loader.load("judge")["developer"],
            {
                "response_schema": "{}",
                "learning_context": "",
                "approval_score_threshold": 8.5,
                "soft_fail_score_threshold": 5.0,
            },
        )

        assert "8.5" in rendered
        assert "5.0" in rendered

    def test_judge_developer_references_judge_verdict(self, prompt_loader):
        """Test judge developer prompt references JudgeVerdict (not JudgeResponse)."""
        prompts = prompt_loader.load("judge")
        developer = prompts["developer"]

        # Should reference JudgeVerdict
        assert "JudgeVerdict" in developer
        # Status values come only from the injected schema, not a drifting literal list.
        assert "schema-defined approval status" in developer
        assert "APPROVE | SOFT_FAIL | HARD_FAIL" not in developer

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


# =============================================================================
# Song-first instructions (the planner answers the song; null needs a reason)
# =============================================================================


def _pack_text(name: str) -> str:
    return "\n".join(path.read_text() for path in sorted((PROMPTS_BASE / name).glob("*.j2")))


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_the_planner_is_told_to_answer_the_song_in_every_section() -> None:
    developer = _flat((PROMPTS_BASE / "planner" / "developer.j2").read_text())
    user = _flat((PROMPTS_BASE / "planner" / "user.j2").read_text())

    for instruction in (
        "Every section answers the song.",
        "Set `intensity` from its energy target, a palette-role `color` from its palette, "
        "and answer every high- and medium-emphasis lyric moment cue and every drop and hit "
        "with an event chosen to fit the section (see Proportion).",
        "**Proportion.** Answering the song is not making the show busy. Accents are "
        "punctuation: give each section a few, spaced so each one lands, and save strobes "
        "and the highest intensity for the builds and the peak, so the biggest moment is the "
        "biggest thing in the show. In a quiet section answer a medium-emphasis cue with a "
        "colour or gobo change or a soft pulse, not a strobe. Hold a colour across a section "
        "and change it where the palette or the mood turns. Contrast makes the chorus land: "
        "a restrained verse is part of answering the song.",
        "Choose `as_authored` for `intensity`, `color` or `gobo` only when you can say in "
        "`reasoning` why the template's own look already answers this moment;",
        "Every other action sets `color` and `gobo` to `none`.",
        "Intensity that stays flat across a clear change of energy ignores the song.",
        "Answer every high- and medium-emphasis cue of a section",
        "`section_role`: what the section does in the song",
        "`energy_level`: 0-100, how much energy this section's light answers with",
    ):
        assert instruction in developer, instruction
    for target, intensities in (
        ("LOW", "`SLOW` or `SMOOTH`"),
        ("MED", "`SMOOTH` or `FAST`"),
        ("HIGH", "`FAST` or `DRAMATIC`"),
        ("PEAK", "`DRAMATIC` or `INTENSE`"),
    ):
        assert f"an energy target of `{target}`: {intensities}" in developer, target
    for mode, boundary in (
        ("snap", "into a drop"),
        ("fade_via_black", "into a quiet bridge or outro"),
        ("crossfade", "between related sections"),
        ("morph", "between related sections"),
        ("sweep", "on builds and lifts"),
    ):
        line = next(item for item in developer.split("- `") if item.startswith(f"{mode}`"))
        assert boundary in line, mode
    assert "Answer every high- and medium-emphasis lyric moment cue" in user
    assert "keep a restrained verse restrained so the chorus lands" in user
    assert "A section that keeps the authored look (`as_authored`) needs a reason there." in user


def test_the_judge_penalises_a_plan_that_ignores_the_song() -> None:
    developer = _flat((PROMPTS_BASE / "judge" / "developer.j2").read_text())

    for instruction in (
        "a high-emphasis lyric moment cue with no event (unanswered)",
        "intensity that stays flat across a clear change of energy target",
        "colour that ignores the section's palette",
        "a plan whose sections are mostly `as_authored` or empty",
        "cannot score above the soft-fail band",
        "a plan that is busy rather than responsive: strobes or the highest intensity in "
        "low-energy sections, accents too dense to read, colour changes faster than the "
        "music changes, no contrast between verse and chorus.",
        "**Reward** plans whose `reasoning` cites the lyrics (cue ids and text), the energy "
        "targets and the palette colours",
    ):
        assert instruction in developer, instruction
    assert "Lyric Moment Cues" in (PROMPTS_BASE / "judge" / "user.j2").read_text()


@pytest.mark.parametrize("pack", ["planner", "judge"])
def test_no_pack_nudges_the_model_toward_leaving_the_song_unanswered(pack: str) -> None:
    text = _flat(_pack_text(pack)).lower()

    for nudge in (
        "valid, deliberate choice",
        "leaving it null is",
        "leave a field null (or a list empty) wherever",
        "unless a choice serves the music",
        "left as authored where",
        "as authored where the template already serves",
        "null, or an empty list, means",
        "that is valid, not missing",
    ):
        assert nudge not in text, nudge


class TestPlannerUserPromptRendering:
    """The first planning prompt, rendered from production variables, reads cleanly:
    one template per line, readable macro arcs, no empty headings, and it ends with
    the sections to plan (2026-11-17 live probe 2 found each of these broken)."""

    @staticmethod
    def _render(
        hints: object = None,
        sections: list | None = None,
        rig_offer: object = None,
        head_focal_roles: dict[str, str] | None = None,
        beat_grid: object = None,
    ) -> str:
        from tests.unit.agents.sequencer.moving_heads.test_orchestrator import (
            create_test_audio_profile,
            create_test_macro_plan,
        )
        from twinklr.core.agents.sequencer.moving_heads.context import (
            FixtureContext,
            MovingHeadPlanningContext,
        )
        from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
            build_planner_variables,
        )

        profile = create_test_audio_profile()
        if hints is not None:
            profile = profile.model_copy(update={"planner_hints": hints})
        templates = ["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"]
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=templates,
            macro_plan=create_test_macro_plan(profile),
            rig_offer=rig_offer,
            head_focal_roles=head_focal_roles,
            beat_grid=beat_grid,
            template_descriptions=[
                {
                    "template_id": template_id,
                    "name": template_id,
                    "description": f"The {template_id} look.",
                    "energy_range": [20, 80],
                    "tags": ["sweep"],
                    "recommended_sections": ["verse"],
                }
                for template_id in templates
            ],
        )
        variables = {**build_planner_variables(context), "response_schema": "{}"}
        if sections is not None:
            sections.extend(variables["sections"])
        loader = PromptPackLoader(base_path=PROMPTS_BASE)
        return PromptRenderer().render(loader.load("planner")["user"], variables)

    def test_the_rig_offer_says_what_this_rig_shows(self) -> None:
        from tests.support import moving_heads as m

        rendered = self._render(rig_offer=m.tagged_offer())
        section = rendered[rendered.index("## What This Rig Can Show") :]
        section = section[: section.index("\n## ", 5)]

        for line in (
            "- **Colours shown faithfully**: red, blue, white, warm_white, cool_white\n",
            "- **Colours shown approximately**, as the nearest wheel colour: magenta as red, "
            "cyan as blue, orange as red, purple as blue, amber as red, uv as blue\n",
            "- **Colours this rig cannot show** (they keep the template's colour): green, "
            "yellow, lime\n",
            "  - `intro`, `verse_1`, `chorus_1`, `outro` (`core.christmas_traditional`): "
            "PALETTE_PRIMARY #E53935 → red; PALETTE_ACCENT #43A047 → not shown; "
            "PALETTE_WARM #E53935 → red (same wheel colour as PALETTE_PRIMARY); "
            "PALETTE_COOL #43A047 → not shown; PALETTE_NEUTRAL #FFFFFF → white\n",
            "- **Gobos**: on every head: open, stars, dots; not shown: circles, triangles, "
            "diamonds, clouds, prism, shatter, flame, water, foliage, abstract\n",
            "  - `closed` / `open`: the heads go dark from the beat until `open`, another "
            "shutter event or the section's end\n",
            "  - Strobes: `strobe_slow` 2 flashes a beat, `strobe_medium` 4 flashes a beat, "
            "`strobe_fast` 8 flashes a beat, from the beat until the next shutter event or the "
            "section's end\n",
            "  - `pulse`: lit for the first half of every beat, dark for the second\n",
            "  - `hit` (a dimmer accent): every head: full on the beat and easing back",
            "- **A wheel change** takes 160 ms of darkness (about 0.4 beat). Where the heads "
            "play straight from one section into the next and its colour or gobo changes, "
            "they go dark for that long just before the new section's first beat",
            "a dark or pale palette colour\nplays as its wheel colour",
        ):
            assert line in section, line
        assert "more than half a beat" not in section

    def test_on_a_variable_grid_the_prompt_says_how_many_boundaries_a_dip_fits(self) -> None:
        """The render decides per boundary: with bars alternating 500 and 300 ms beats,
        the 160 ms change fits half the beat before two of the three section boundaries
        (the median beat would claim every one)."""
        from tests.support import moving_heads as m

        rendered = self._render(
            rig_offer=m.tagged_offer(), beat_grid=m.bars_grid(*([500.0, 300.0] * 29))
        )

        assert (
            "- **A wheel change** takes 160 ms of darkness (about 0.4 beat). It fits half "
            "the beat before 2 of this song's 3 section boundaries (the shortest half beat "
            "is 150 ms). Where it fits"
        ) in rendered
        assert "the change waits for the section's first dark moment long enough" in rendered

    def test_a_rig_without_a_dimmer_is_told_intensity_cannot_pulse(self) -> None:
        from tests.support import moving_heads as m

        full = self._render(rig_offer=m.tagged_offer())
        none = self._render(rig_offer=m.tagged_offer().model_copy(update={"hit": "none"}))
        some = self._render(rig_offer=m.tagged_offer().model_copy(update={"hit": "some"}))

        assert "- **Intensity**" not in full
        assert (
            "- **Intensity**: no head has a dimmer axis, so `DRAMATIC` and `INTENSE` cannot "
            "pulse here: every head plays its template's own level. Give emphasis with events "
            "or colour instead.\n"
        ) in none
        assert "- **Intensity**: only some heads have a dimmer axis;" in some

    def test_the_show_planner_is_told_how_the_focal_role_shapes_intensity(self) -> None:
        roles = {"intro": "REST", "verse_1": "SUPPORT", "chorus_1": "LEAD", "outro": "REST"}
        rendered = self._render(head_focal_roles=roles)

        assert "**The moving heads' focal role** (deterministic code applies it" in rendered
        assert "LEAD plays one step up the intensity ladder" in rendered
        assert "REST at most the template's own level" in rendered
        for section_id, role in roles.items():
            assert f"- `{section_id}`: {role}\n" in rendered
        assert "focal role**" not in self._render()

    def test_an_untagged_rig_is_told_no_colour_or_gobo_is_offered(self) -> None:
        from tests.support import moving_heads as m

        rendered = self._render(rig_offer=m.untagged_offer())

        assert (
            "the rig's colour wheel offers no colour (no state is tagged),\n  so every "
            "`color` keeps the template's own colour"
        ) in rendered
        assert "so no gobo\n  is offered" in rendered
        assert "## What This Rig Can Show" not in self._render()

    def test_each_template_is_on_its_own_line(self) -> None:
        rendered = self._render()
        lines = [line for line in rendered.splitlines() if line.startswith("- `")]
        for template_id in ("sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"):
            (line,) = [line for line in lines if line.startswith(f"- `{template_id}`:")]
            assert line.endswith("Recommended sections: verse")

    def test_macro_arcs_are_readable_lines_not_python_dicts(self) -> None:
        rendered = self._render()
        assert "{'" not in rendered and "[{" not in rendered
        assert "- from `intro`: palette `core.christmas_traditional`, entered by HOLD\n" in rendered
        assert "- `pulse` in intro, verse_1, chorus_1, outro (RESTATE):" in rendered
        assert "- `intro`: lead group `MEGA_TREE`\n" in rendered

    def test_an_empty_directives_heading_is_omitted(self) -> None:
        from twinklr.core.agents.audio.profile.models import PlannerHints, SectionObjectives

        quiet = self._render(PlannerHints(avoid_patterns=["Strobing in the intro"]))
        assert "Section Planning Directives" not in quiet
        assert "### Patterns to Avoid\n- Strobing in the intro" in quiet
        directed = self._render(
            PlannerHints(
                section_objectives=[
                    SectionObjectives(section_id="intro", objectives=["Open softly."])
                ]
            )
        )
        assert "### Section Planning Directives\n\n**intro**:\n- Open softly." in directed

    def test_the_prompt_ends_with_every_section_to_plan_over_its_bars(self) -> None:
        sections: list = []
        rendered = self._render(sections=sections)
        tail = rendered[rendered.index("## Return") :]
        assert tail.rstrip().endswith("how the light follows this song.")
        bullets = [line for line in tail.splitlines() if line.startswith("- `")]
        assert bullets == [
            f"- `{s['section_id']}`: bars {s['start_bar']}-{s['end_bar']}" for s in sections
        ]
        assert [s["section_id"] for s in sections] == ["intro", "verse_1", "chorus_1", "outro"]
        # Inclusive and contiguous: each section starts the bar after the last one ends.
        assert all(b["start_bar"] == a["end_bar"] + 1 for a, b in pairwise(sections))
