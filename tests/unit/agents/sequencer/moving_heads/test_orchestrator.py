"""Tests for V2 MovingHead orchestrator."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support import moving_heads as m
from tests.support.moving_heads import plan_section
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    Contrast,
    CreativeGuidance,
    EnergyPoint,
    EnergyProfile,
    LyricProfile,
    MacroEnergy,
    MotionDensity,
    PlannerHints,
    SectionEnergyProfile,
    SongIdentity,
    SongSectionRef,
    Structure,
)
from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
)
from twinklr.core.agents.sequencer.macro_planner.context import PlanningContext
from twinklr.core.agents.sequencer.macro_planner.orchestrator import MacroPlannerOrchestrator
from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
    TemplateDescription,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanColor,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
    MovingHeadPlannerOrchestrator,
    build_judge_variables,
    build_planner_variables,
    normalize_plan,
)
from twinklr.core.agents.shared.judge.controller import IterationContext
from twinklr.core.agents.shared.judge.models import JudgeVerdict, VerdictStatus
from twinklr.core.sequencer.planning import (
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    MacroPlan,
    MacroSection,
    MotifEvolution,
    MotifThread,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)
from twinklr.core.sequencer.templates.group.models import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    TargetType,
)


def create_test_audio_profile() -> AudioProfileModel:
    """Create a minimal audio profile for testing."""
    sections = [
        SongSectionRef(section_id="intro", name="intro", start_ms=0, end_ms=15000),
        SongSectionRef(section_id="verse_1", name="verse", start_ms=15000, end_ms=45000),
        SongSectionRef(section_id="chorus_1", name="chorus", start_ms=45000, end_ms=75000),
        SongSectionRef(section_id="outro", name="outro", start_ms=75000, end_ms=90000),
    ]

    song_identity = SongIdentity(
        title="Test Song",
        artist="Test Artist",
        duration_ms=90000,
        bpm=120.0,
        time_signature="4/4",
    )

    structure = Structure(sections=sections, structure_confidence=0.9)

    section_profiles = [
        SectionEnergyProfile(
            section_id=sec.section_id,
            start_ms=sec.start_ms,
            end_ms=sec.end_ms,
            energy_curve=[
                EnergyPoint(t_ms=sec.start_ms),
                EnergyPoint(t_ms=(sec.start_ms + sec.end_ms) // 2),
                EnergyPoint(t_ms=sec.end_ms - 1),
            ],
            mean_energy=0.55,
            peak_energy=0.6,
        )
        for sec in sections
    ]

    energy_profile = EnergyProfile(
        macro_energy=MacroEnergy.MED,
        section_profiles=section_profiles,
        peaks=[],
    )

    lyric_profile = LyricProfile(
        has_plain_lyrics=False,
        has_timed_words=False,
        has_phonemes=False,
        lyric_confidence=0.0,
        phoneme_confidence=0.0,
    )

    creative_guidance = CreativeGuidance(
        recommended_layer_count=2,
        recommended_contrast=Contrast.MED,
        recommended_motion_density=MotionDensity.MED,
    )

    return AudioProfileModel(
        song_identity=song_identity,
        structure=structure,
        energy_profile=energy_profile,
        lyric_profile=lyric_profile,
        creative_guidance=creative_guidance,
        planner_hints=PlannerHints(),
    )


def create_test_macro_plan(profile: AudioProfileModel) -> MacroPlan:
    """Create a valid full macro contract for cache/prompt seam tests."""
    target = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    sections = [
        MacroSection(
            section=section,
            energy_target=EnergyTarget.MED,
            motion_density=MotionDensity.MED,
            choreography_style=ChoreographyStyle.HYBRID,
            palette_role=PaletteRoleRef(stop_id="main", override=None),
            theme=ThemeRef(
                theme_id="theme.abstract.neon",
                scope=ThemeScope.SECTION,
                tags=[],
                palette_id=None,
            ),
            motif_ids=["pulse"],
            focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
            call_response_pairs=[],
            coordination_intent=CoordinationMode.UNIFIED,
            notes="Typed moving-head macro guidance for this song section.",
        )
        for section in profile.structure.sections
    ]
    return MacroPlan(
        sections=sections,
        palette_arc=[
            PaletteStop(
                stop_id="main",
                palette=PaletteRef(
                    palette_id="core.christmas_traditional",
                    role=None,
                    intensity=None,
                    variant=None,
                ),
                applies_from_section_id=sections[0].section.section_id,
                transition=PaletteTransition.HOLD,
            )
        ],
        motif_continuity=[
            MotifThread(
                motif_id="pulse",
                section_ids=[item.section.section_id for item in sections],
                evolution=MotifEvolution.RESTATE,
                description="A recurring whole-song pulse motif.",
            )
        ],
        focal_arc=[
            FocalAssignment(section_id=item.section.section_id, lead_target=target)
            for item in sections
        ],
    )


@pytest.fixture
def planning_context() -> MovingHeadPlanningContext:
    """Create a test planning context."""
    return MovingHeadPlanningContext(
        audio_profile=create_test_audio_profile(),
        fixtures=FixtureContext(count=4, groups=[{"id": "front", "fixtures": [1, 2]}]),
        available_templates=["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"],
    )


REASON = "Answers the section's energy and its lyric hook with one fitting accent."
STRATEGY = "The heads follow the song's energy and answer its lyric hooks in palette colour."


def _answered(*args: Any, **fields: Any) -> PlanSection:
    """`plan_section` with a reason, as the validator requires."""
    return plan_section(*args, **{"reasoning": REASON, **fields})


def _event(bar: int, beat: int, action: str, cue_id: str | None = None) -> dict[str, object]:
    return {
        "bar": bar,
        "beat": beat,
        "moment_cue_id": cue_id,
        "action": action,
        "color": None,
        "gobo": None,
    }


@pytest.fixture
def valid_plan() -> ChoreographyPlan:
    """Create a valid choreography plan."""
    return ChoreographyPlan(
        sections=[
            _answered("intro", 1, 8, "sweep_lr_fan_pulse"),
            _answered("verse_1", 9, 24, "circle_fan_hold"),
            _answered("chorus_1", 25, 40, "pendulum_chevron_breathe"),
        ],
        overall_strategy="Build energy progressively",
    )


class TestBuildPlannerVariables:
    """Tests for build_planner_variables function."""

    def test_initial_iteration(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test variables for initial iteration (iteration=0)."""
        variables = build_planner_variables(planning_context, iteration=0)

        # Should have all required fields
        assert variables["iteration"] == 0
        assert variables["song_title"] == "Test Song"
        assert variables["song_artist"] == "Test Artist"
        assert variables["tempo"] == 120.0
        assert variables["time_signature"] == "4/4"
        assert variables["fixture_count"] == 4
        assert len(variables["available_templates"]) == 3
        assert len(variables["sections"]) == 4

        # Should have audio_profile for initial iteration
        assert variables["audio_profile"] is not None

        # Should not have feedback for initial iteration
        assert variables["feedback"] is None

    def test_refinement_iteration(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test variables for refinement iteration (iteration>0)."""
        variables = build_planner_variables(
            planning_context,
            iteration=1,
            feedback="Fix timing issues",
            revision_focus=["TIMING: Fix overlapping sections"],
        )

        assert variables["iteration"] == 1
        assert variables["feedback"] == "Fix timing issues"
        assert variables["revision_focus"] == ["TIMING: Fix overlapping sections"]

        # Should NOT have audio_profile for refinement (token optimization)
        assert variables["audio_profile"] is None

    def test_sections_have_bar_positions(self, planning_context: MovingHeadPlanningContext) -> None:
        """Test sections include calculated bar positions."""
        variables = build_planner_variables(planning_context, iteration=0)

        sections = variables["sections"]
        assert all("start_bar" in s for s in sections)
        assert all("end_bar" in s for s in sections)


class TestBuildJudgeVariables:
    """Tests for build_judge_variables function."""

    def test_basic_judge_variables(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test basic judge variable building."""
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=0,
            iteration_context=IterationContext(),
        )

        assert "plan" in variables
        assert variables["iteration"] == 0
        assert len(variables["sections"]) == 4
        assert variables["total_bars"] > 0
        assert variables["tempo"] == 120.0
        assert len(variables["available_templates"]) == 3

    def test_judge_variables_with_history(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test judge variables with iteration history."""
        history = IterationContext()
        history.add_verdict(
            JudgeVerdict(
                status=VerdictStatus.SOFT_FAIL,
                score=6.0,
                confidence=0.9,
                strengths=["Timing is coherent"],
                issues=[],
                feedback_for_planner="Fix variety and add energy",
                iteration=1,
            )
        )
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=2,
            iteration_context=history,
        )

        assert variables["iteration"] == 2
        assert variables["previous_feedback"] == ["Fix variety and add energy"]
        assert variables["previous_issues"] == []
        assert variables["previous_verdicts"][0]["score"] == 6.0

    def test_plan_serialized_as_dict(
        self, planning_context: MovingHeadPlanningContext, valid_plan: ChoreographyPlan
    ) -> None:
        """Test plan is serialized as dict for JSON templates."""
        variables = build_judge_variables(
            context=planning_context,
            plan=valid_plan,
            iteration=0,
            iteration_context=IterationContext(),
        )

        # Plan should be dict, not Pydantic model
        assert isinstance(variables["plan"], dict)
        assert "sections" in variables["plan"]


class TestMovingHeadPlannerOrchestrator:
    """Tests for MovingHeadPlannerOrchestrator."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create mock LLM provider."""
        return MagicMock()

    def test_orchestrator_init(self, mock_provider: MagicMock) -> None:
        """Test orchestrator initialization."""
        orchestrator = MovingHeadPlannerOrchestrator(
            provider=mock_provider,
            max_iterations=5,
            min_pass_score=6.5,
        )

        assert orchestrator.provider == mock_provider
        assert orchestrator.controller.config.max_iterations == 5
        assert orchestrator.controller.config.approval_score_threshold == 6.5

    def test_orchestrator_uses_default_specs(self, mock_provider: MagicMock) -> None:
        """Test orchestrator uses default specs when not provided."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        assert orchestrator.planner_spec is not None
        assert orchestrator.judge_spec is not None
        assert orchestrator.planner_spec.name == "mh_planner"
        assert orchestrator.judge_spec.name == "mh_judge"

    @pytest.mark.asyncio
    async def test_get_cache_key(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """Test cache key generation."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        key1 = await orchestrator.get_cache_key(planning_context)
        key2 = await orchestrator.get_cache_key(planning_context)

        # Same context should produce same key
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex digest

    @pytest.mark.asyncio
    async def test_cache_and_prompt_track_song_level_macro_arcs(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """Top-level-only macro edits survive prompt projection and invalidate cache."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        plan = create_test_macro_plan(planning_context.audio_profile)
        baseline = planning_context.model_copy(update={"macro_plan": plan})
        baseline_key = await orchestrator.get_cache_key(baseline)
        baseline_prompt = baseline.for_prompt()

        palette_plan = plan.model_copy(
            update={
                "palette_arc": [
                    plan.palette_arc[0].model_copy(
                        update={"transition": PaletteTransition.CROSSFADE}
                    )
                ]
            }
        )
        motif_plan = plan.model_copy(
            update={
                "motif_continuity": [
                    plan.motif_continuity[0].model_copy(
                        update={"description": "A varied recurring whole-song pulse motif."}
                    )
                ]
            }
        )
        focal_plan = plan.model_copy(update={"focal_arc": list(reversed(plan.focal_arc))})

        for changed_plan in (palette_plan, motif_plan, focal_plan):
            changed = planning_context.model_copy(update={"macro_plan": changed_plan})
            assert await orchestrator.get_cache_key(changed) != baseline_key

        projection = plan.reader_projection()
        assert baseline_prompt["macro_palette_arc"] == projection["palette_arc"]
        assert baseline_prompt["macro_motif_continuity"] == projection["motif_continuity"]
        assert baseline_prompt["macro_focal_arc"] == projection["focal_arc"]

    def test_planner_sees_each_section_palette_colours(
        self, planning_context: MovingHeadPlanningContext
    ) -> None:
        """A palette-role colour is chosen knowing what the role stands for: each macro
        section carries its palette's colours, not only the palette id."""
        from twinklr.core.sequencer.theming.catalog import get_palette

        plan = create_test_macro_plan(planning_context.audio_profile)
        context = planning_context.model_copy(update={"macro_plan": plan})

        variables = build_planner_variables(context)

        stops = get_palette("core.christmas_traditional").stops
        for section in variables["macro_plan"]:
            assert section["palette_id"] == "core.christmas_traditional"
            assert section["palette_colors"] == [
                {"hex": stop.hex, "name": stop.name} for stop in stops
            ]

    @pytest.mark.asyncio
    async def test_the_response_schema_re_keys_the_plan_cache(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """A change to the planner's response model alone gives every song a new cache
        key, so a plan in another contract is never reused."""
        from pydantic import BaseModel, ConfigDict

        class OtherContract(BaseModel):
            model_config = ConfigDict(extra="forbid")

            sections: list[str]

        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        baseline = await orchestrator.get_cache_key(planning_context)
        orchestrator.planner_spec = orchestrator.planner_spec.model_copy(
            update={"response_model": OtherContract}
        )

        assert await orchestrator.get_cache_key(planning_context) != baseline

    @pytest.mark.asyncio
    async def test_cache_key_tracks_iteration_and_threshold_config(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """Behavioral judge-loop knobs invalidate cached plans honestly."""
        baseline = MovingHeadPlannerOrchestrator(
            provider=mock_provider, max_iterations=3, min_pass_score=7.0
        )
        stricter = MovingHeadPlannerOrchestrator(
            provider=mock_provider, max_iterations=3, min_pass_score=8.0
        )
        judge_disabled = MovingHeadPlannerOrchestrator(
            provider=mock_provider, max_iterations=0, min_pass_score=7.0
        )

        baseline_key = await baseline.get_cache_key(planning_context)
        assert await stricter.get_cache_key(planning_context) != baseline_key
        assert await judge_disabled.get_cache_key(planning_context) != baseline_key

    @pytest.mark.asyncio
    async def test_cache_key_tracks_sampling_temperature(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        from twinklr.core.agents.sequencer.moving_heads.specs import (
            get_judge_spec,
            get_planner_spec,
        )

        baseline = MovingHeadPlannerOrchestrator(
            provider=mock_provider,
            planner_spec=get_planner_spec().model_copy(update={"temperature": 0.3}),
            judge_spec=get_judge_spec().model_copy(update={"temperature": 0.4}),
        )
        changed = MovingHeadPlannerOrchestrator(
            provider=mock_provider,
            planner_spec=get_planner_spec().model_copy(update={"temperature": 0.9}),
            judge_spec=get_judge_spec().model_copy(update={"temperature": 0.4}),
        )
        assert await baseline.get_cache_key(planning_context) != await changed.get_cache_key(
            planning_context
        )

    @pytest.mark.asyncio
    async def test_cache_key_tracks_exact_template_metadata_and_ids(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """A same-ID metadata edit and a changed available set both invalidate plans."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        baseline = planning_context.model_copy(
            update={
                "template_descriptions": [
                    TemplateDescription(
                        template_id="sweep_lr_fan_pulse", name="Sweep", tags=["low"]
                    )
                ]
            }
        )
        metadata_changed = baseline.model_copy(
            update={
                "template_descriptions": [
                    TemplateDescription(
                        template_id="sweep_lr_fan_pulse", name="Sweep", tags=["high"]
                    )
                ]
            }
        )
        set_changed = baseline.model_copy(
            update={"available_templates": [*baseline.available_templates, "new_template"]}
        )

        key = await orchestrator.get_cache_key(baseline)
        assert await orchestrator.get_cache_key(metadata_changed) != key
        assert await orchestrator.get_cache_key(set_changed) != key

    @pytest.mark.asyncio
    async def test_cache_key_tracks_authoritative_beat_grid_and_macro_ablation(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """Timing drift and explicit no-macro mode cannot reuse a normal cached plan."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        grid = BeatGrid.from_tempo(120.0, total_bars=48, start_offset_ms=0.0)
        shifted_grid = BeatGrid.from_tempo(120.0, total_bars=48, start_offset_ms=17.0)
        baseline = planning_context.model_copy(
            update={"beat_grid": grid, "macro_planning_enabled": True}
        )
        shifted = baseline.model_copy(update={"beat_grid": shifted_grid})
        ablated = baseline.model_copy(update={"macro_planning_enabled": False})

        key = await orchestrator.get_cache_key(baseline)
        assert await orchestrator.get_cache_key(shifted) != key
        assert await orchestrator.get_cache_key(ablated) != key

    @pytest.mark.asyncio
    async def test_cache_key_tracks_exact_planning_fixture_identity(
        self, mock_provider: MagicMock, planning_context: MovingHeadPlanningContext
    ) -> None:
        """A fixture-group capability change invalidates the planning cache."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        changed = planning_context.model_copy(
            update={
                "fixtures": FixtureContext(
                    count=4,
                    groups=[{"id": "front", "fixtures": [1, 2], "position": "stage_left"}],
                )
            }
        )
        assert await orchestrator.get_cache_key(changed) != await orchestrator.get_cache_key(
            planning_context
        )

    @pytest.mark.asyncio
    async def test_run_validates_empty_templates(self, mock_provider: MagicMock) -> None:
        """Test run validates that templates are not empty."""
        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)

        # Empty templates should fail
        context = MovingHeadPlanningContext(
            audio_profile=create_test_audio_profile(),
            fixtures=FixtureContext(count=4, groups=[]),
            available_templates=[],  # Empty templates
        )

        with pytest.raises(ValueError, match="At least one template"):
            await orchestrator.run(context)

    def test_fixture_context_validates_count(self) -> None:
        """Test FixtureContext validates count >= 1 at Pydantic level."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FixtureContext(count=0, groups=[])

    @pytest.mark.asyncio
    async def test_macro_cache_key_tracks_exact_theming_catalog(
        self, mock_provider: MagicMock
    ) -> None:
        """A catalog-only revision invalidates the macro plan it conditions."""
        context = PlanningContext(
            audio_profile=create_test_audio_profile(),
            display_groups=[{"id": "MH", "model_count": 4}],
        )
        orchestrator = MacroPlannerOrchestrator(provider=mock_provider)
        target = "twinklr.core.agents.sequencer.macro_planner.orchestrator"
        with (
            patch(f"{target}.get_theming_catalog_dict", return_value={"themes": ["v1"]}),
            patch(f"{target}.get_theming_ids", return_value={"themes": ["v1"]}),
        ):
            baseline = await orchestrator.get_cache_key(context)
        with (
            patch(f"{target}.get_theming_catalog_dict", return_value={"themes": ["v2"]}),
            patch(f"{target}.get_theming_ids", return_value={"themes": ["v2"]}),
        ):
            changed = await orchestrator.get_cache_key(context)

        assert changed != baseline


class TestOrchestratorIntegration:
    """Integration tests for V2 orchestrator (mocked LLM calls)."""

    @pytest.fixture
    def mock_controller_run(self):
        """Mock the controller.run method."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )
        from twinklr.core.agents.shared.judge.models import (
            IterationState,
            JudgeVerdict,
            VerdictStatus,
        )

        async def mock_run(*args, **kwargs):
            # Create successful result
            context = IterationContext()
            context.current_iteration = 1
            context.update_state(IterationState.COMPLETE)
            context.final_verdict = JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=8.0,
                confidence=0.9,
                strengths=["Good variety", "Musical alignment"],
                issues=[],
                feedback_for_planner="No changes needed",
                iteration=1,
            )

            plan = ChoreographyPlan(
                sections=[_answered("intro", 1, 8, "sweep_lr_fan_pulse")],
                overall_strategy="Test",
            )

            return IterationResult(
                success=True,
                plan=plan,
                context=context,
            )

        return mock_run

    @pytest.mark.asyncio
    async def test_successful_orchestration(
        self,
        planning_context: MovingHeadPlanningContext,
        mock_controller_run,
    ) -> None:
        """Test successful orchestration with mocked controller."""
        mock_provider = MagicMock()

        orchestrator = MovingHeadPlannerOrchestrator(provider=mock_provider)
        controller_run = AsyncMock(side_effect=mock_controller_run)

        # Mock the controller.run method
        with patch.object(orchestrator.controller, "run", new=controller_run):
            result = await orchestrator.run(planning_context)

        assert result.success is True
        assert result.plan is not None
        assert len(result.plan.sections) > 0
        judge_context_builder = controller_run.await_args.kwargs["judge_context_builder"]
        assert callable(judge_context_builder)

        history = IterationContext()
        history.add_verdict(
            JudgeVerdict(
                status=VerdictStatus.SOFT_FAIL,
                score=6.0,
                confidence=0.9,
                strengths=[],
                issues=[],
                feedback_for_planner="Add a stronger chorus contrast.",
                iteration=0,
            )
        )
        shaped = judge_context_builder(result.plan, 1, history)
        assert shaped["previous_feedback"] == ["Add a stronger chorus contrast."]

    @pytest.mark.asyncio
    async def test_final_plan_binds_lyric_cue_to_authoritative_grid(self) -> None:
        """The actual orchestration seam returns the render-ready cue timing."""
        from twinklr.core.agents.shared.judge.controller import IterationContext, IterationResult

        cue_id = "intro-home"
        plan = ChoreographyPlan(
            sections=[
                _answered(
                    "intro",
                    1,
                    2,
                    "sweep_lr_fan_pulse",
                    moment_cues=[cue_id],
                    events=[_event(1, 1, "strobe_fast", cue_id)],
                )
            ],
            overall_strategy=STRATEGY,
        )
        controller_result = IterationResult[ChoreographyPlan](
            success=True,
            plan=plan,
            context=IterationContext(),
        )
        context = MovingHeadPlanningContext(
            audio_profile=create_test_audio_profile(),
            lyric_context=LyricContextModel(
                has_lyrics=True,
                vocal_coverage_pct=0.25,
                moment_cues=[
                    MomentCue(
                        cue_id=cue_id,
                        timestamp_ms=1_450,
                        section_id="intro",
                        emphasis="HIGH",
                        text="light the way home",
                        visual_hint="Open a white fan from center on home.",
                    )
                ],
            ),
            fixtures=FixtureContext(count=4, groups=[]),
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
            available_templates=["sweep_lr_fan_pulse"],
        )
        orchestrator = MovingHeadPlannerOrchestrator(provider=MagicMock())

        with patch.object(
            orchestrator.controller,
            "run",
            new=AsyncMock(return_value=controller_result),
        ) as controller_run:
            result = await orchestrator.run(context)

        assert result.plan is not None
        normalizer = controller_run.call_args.kwargs["plan_normalizer"]
        normalized = normalizer(result.plan)
        event = normalized.sections[0].events[0]
        assert (event.bar, event.beat) == (1, 4)
        repairs = controller_run.call_args.kwargs["plan_repairs"]
        assert repairs(normalized) == []

    @pytest.mark.asyncio
    async def test_judge_provider_receives_canonical_section_and_bound_cue_event(self) -> None:
        section = SongSectionRef(
            section_id="chorus_1",
            name="chorus",
            start_ms=0,
            end_ms=4_000,
        )
        profile = create_test_audio_profile().model_copy(
            update={
                "song_identity": SongIdentity(
                    title="Cue Song",
                    artist="Test Artist",
                    duration_ms=4_000,
                    bpm=120.0,
                    time_signature="4/4",
                ),
                "structure": Structure(sections=[section], structure_confidence=0.9),
            }
        )
        cue_id = "chorus-home"
        planner_plan = ChoreographyPlan(
            sections=[
                _answered(
                    "chorus",  # Display name; normalizer must canonicalize it.
                    1,
                    2,
                    "sweep_lr_fan_pulse",
                    moment_cues=[cue_id],
                    events=[_event(2, 4, "strobe_fast", cue_id)],
                )
            ],
            overall_strategy=STRATEGY,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            strengths=["Canonical and on-grid"],
            issues=[],
            feedback_for_planner="No changes needed",
            iteration=1,
        )
        judge_messages: list[dict[str, str]] = []
        provider = MagicMock()
        provider.provider_type = ProviderType.ANTHROPIC
        invalid_plan = planner_plan.model_copy(
            update={
                "sections": [
                    planner_plan.sections[0].model_copy(update={"section_id": "missing_section"})
                ]
            }
        )
        provider.generate_json_with_conversation_async = AsyncMock(
            side_effect=[
                LLMResponse(
                    content=invalid_plan.model_dump(mode="json"),
                    metadata=ResponseMetadata(),
                ),
                LLMResponse(
                    content=planner_plan.model_dump(mode="json"),
                    metadata=ResponseMetadata(),
                ),
            ]
        )

        async def judge_call(*, messages: list[dict[str, str]], **kwargs: object) -> LLMResponse:
            judge_messages.extend(messages)
            return LLMResponse(
                content=verdict.model_dump(mode="json"),
                metadata=ResponseMetadata(),
            )

        provider.generate_json_async = AsyncMock(side_effect=judge_call)
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            lyric_context=LyricContextModel(
                has_lyrics=True,
                vocal_coverage_pct=0.25,
                moment_cues=[
                    MomentCue(
                        cue_id=cue_id,
                        timestamp_ms=1_250,
                        section_id="chorus_1",
                        emphasis="HIGH",
                        text="light the way home",
                        visual_hint="Open a white fan from center on home.",
                    )
                ],
            ),
            fixtures=FixtureContext(count=4, groups=[]),
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
            available_templates=["sweep_lr_fan_pulse"],
        )

        result = await MovingHeadPlannerOrchestrator(
            provider=provider,
            max_iterations=2,
        ).run(context)

        assert result.success
        assert provider.generate_json_with_conversation_async.await_count == 2
        assert provider.generate_json_async.await_count == 1
        assert result.plan is not None
        assert result.plan.sections[0].section_id == "chorus_1"
        event = result.plan.sections[0].events[0]
        assert (event.bar, event.beat) == (1, 3)
        rendered_judge_request = "\n".join(message["content"] for message in judge_messages)
        assert '"section_id": "chorus_1"' in rendered_judge_request
        assert '"beat": 3' in rendered_judge_request

    @pytest.mark.asyncio
    async def test_a_repaired_item_reaches_the_judge_and_the_next_planning_prompt(self) -> None:
        """One impossible item is repaired, not refused: the run goes on to the judge, and
        what repair did reaches the planner's refinement prompt."""
        section = SongSectionRef(section_id="chorus_1", name="chorus", start_ms=0, end_ms=4_000)
        profile = create_test_audio_profile().model_copy(
            update={
                "song_identity": SongIdentity(
                    title="Cue Song",
                    artist="Test Artist",
                    duration_ms=4_000,
                    bpm=120.0,
                    time_signature="4/4",
                ),
                "structure": Structure(sections=[section], structure_confidence=0.9),
            }
        )
        first = ChoreographyPlan(
            sections=[
                _answered(
                    "chorus_1",
                    1,
                    2,
                    "sweep_lr_fan_pulse",
                    moment_cues=["ghost"],
                    events=[_event(2, 1, "hit", "ghost"), _event(5, 1, "closed")],
                )
            ],
            overall_strategy=STRATEGY,
        )
        second = ChoreographyPlan(
            sections=[_answered("chorus_1", 1, 2, "sweep_lr_fan_pulse")],
            overall_strategy=STRATEGY,
        )
        verdicts = [
            JudgeVerdict(
                status=status,
                score=score,
                confidence=0.9,
                strengths=["On the grid"],
                issues=[],
                feedback_for_planner="Tighten the chorus.",
                iteration=iteration,
            )
            for iteration, (status, score) in enumerate(
                [(VerdictStatus.SOFT_FAIL, 6.0), (VerdictStatus.APPROVE, 8.0)]
            )
        ]
        planner_messages: list[str] = []
        judge_messages: list[str] = []

        async def planner_call(*, user_message: str, **kwargs: object) -> LLMResponse:
            planner_messages.append(user_message)
            plan = first if len(planner_messages) == 1 else second
            return LLMResponse(content=plan.model_dump(mode="json"), metadata=ResponseMetadata())

        async def judge_call(*, messages: list[dict[str, str]], **kwargs: object) -> LLMResponse:
            judge_messages.append("\n".join(message["content"] for message in messages))
            verdict = verdicts[len(judge_messages) - 1]
            return LLMResponse(content=verdict.model_dump(mode="json"), metadata=ResponseMetadata())

        provider = MagicMock()
        provider.provider_type = ProviderType.ANTHROPIC
        provider.generate_json_with_conversation_async = AsyncMock(side_effect=planner_call)
        provider.generate_json_async = AsyncMock(side_effect=judge_call)
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            lyric_context=LyricContextModel(has_lyrics=True, vocal_coverage_pct=0.25),
            fixtures=FixtureContext(count=4, groups=[]),
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
            available_templates=["sweep_lr_fan_pulse"],
        )

        result = await MovingHeadPlannerOrchestrator(provider=provider, max_iterations=2).run(
            context
        )

        assert result.success
        assert len(planner_messages) == 2 and len(judge_messages) == 2
        # The judge sees the repaired plan and its repairs; "ghost" survives only there.
        assert '"repairs"' in judge_messages[0] and "ghost" in judge_messages[0]
        assert "section 'chorus_1': moment cue 'ghost' dropped" in planner_messages[1]
        assert (
            "section 'chorus_1': closed event at bar 5 beat 1 adjusted: after the section"
            in planner_messages[1]
        )
        assert "ghost" not in planner_messages[0]
        assert result.plan is not None and result.plan.repairs == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_iterations", [2, 1])
    async def test_an_unanswered_high_cue_sends_a_valid_plan_back_while_rounds_remain(
        self, max_iterations: int
    ) -> None:
        """A valid plan that leaves a HIGH lyric cue unanswered is re-planned before any
        judge call while a planning round remains; on the last round it is judged as is,
        never failed for it."""
        section = SongSectionRef(section_id="chorus_1", name="chorus", start_ms=0, end_ms=4_000)
        profile = create_test_audio_profile().model_copy(
            update={
                "song_identity": SongIdentity(
                    title="Cue Song",
                    artist="Test Artist",
                    duration_ms=4_000,
                    bpm=120.0,
                    time_signature="4/4",
                ),
                "structure": Structure(sections=[section], structure_confidence=0.9),
            }
        )
        cue = MomentCue(
            cue_id="hook",
            timestamp_ms=1_500,
            section_id="chorus_1",
            emphasis="HIGH",
            text="light it up",
            visual_hint="A bright hit.",
        )
        silent = ChoreographyPlan(
            sections=[_answered("chorus_1", 1, 2, "sweep_lr_fan_pulse")],
            overall_strategy=STRATEGY,
        )
        answered = ChoreographyPlan(
            sections=[
                _answered(
                    "chorus_1",
                    1,
                    2,
                    "sweep_lr_fan_pulse",
                    moment_cues=["hook"],
                    events=[_event(1, 4, "hit", "hook")],
                )
            ],
            overall_strategy=STRATEGY,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            strengths=["Answers the hook"],
            issues=[],
            feedback_for_planner="Good.",
            iteration=0,
        )
        planner_messages: list[str] = []

        async def planner_call(*, user_message: str, **kwargs: object) -> LLMResponse:
            planner_messages.append(user_message)
            plan = silent if len(planner_messages) == 1 else answered
            return LLMResponse(content=plan.model_dump(mode="json"), metadata=ResponseMetadata())

        provider = MagicMock()
        provider.provider_type = ProviderType.ANTHROPIC
        provider.generate_json_with_conversation_async = AsyncMock(side_effect=planner_call)
        provider.generate_json_async = AsyncMock(
            return_value=LLMResponse(
                content=verdict.model_dump(mode="json"), metadata=ResponseMetadata()
            )
        )
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            lyric_context=LyricContextModel(
                has_lyrics=True, vocal_coverage_pct=0.25, moment_cues=[cue]
            ),
            fixtures=FixtureContext(count=4, groups=[]),
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
            available_templates=["sweep_lr_fan_pulse"],
        )

        result = await MovingHeadPlannerOrchestrator(
            provider=provider, max_iterations=max_iterations
        ).run(context)

        assert result.success
        assert provider.generate_json_async.await_count == 1
        assert len(planner_messages) == max_iterations
        if max_iterations == 2:
            assert "the HIGH lyric moment cue 'hook'" in planner_messages[1]
            assert result.plan is not None and result.plan.sections[0].events
        else:
            assert result.plan is not None and result.plan.sections[0].events == []

    @pytest.mark.asyncio
    async def test_the_advisory_resends_at_most_once_so_the_judge_keeps_its_rounds(self) -> None:
        """A planner that ignores the advice twice: the first plan is sent back, the second
        is judged anyway, and the judge's "revise" verdict still gets its round."""
        section = SongSectionRef(section_id="chorus_1", name="chorus", start_ms=0, end_ms=4_000)
        profile = create_test_audio_profile().model_copy(
            update={
                "song_identity": SongIdentity(
                    title="Cue Song",
                    artist="Test Artist",
                    duration_ms=4_000,
                    bpm=120.0,
                    time_signature="4/4",
                ),
                "structure": Structure(sections=[section], structure_confidence=0.9),
            }
        )
        cue = MomentCue(
            cue_id="hook",
            timestamp_ms=1_500,
            section_id="chorus_1",
            emphasis="HIGH",
            text="light it up",
            visual_hint="A bright hit.",
        )
        silent = ChoreographyPlan(
            sections=[_answered("chorus_1", 1, 2, "sweep_lr_fan_pulse")],
            overall_strategy=STRATEGY,
        )
        verdicts = [
            JudgeVerdict(
                status=status,
                score=score,
                confidence=0.9,
                strengths=["Clean"],
                issues=[],
                feedback_for_planner="Answer the hook.",
                iteration=index,
            )
            for index, (status, score) in enumerate(
                [(VerdictStatus.SOFT_FAIL, 6.0), (VerdictStatus.APPROVE, 8.0)]
            )
        ]
        planner_messages: list[str] = []
        judged = 0

        async def planner_call(*, user_message: str, **kwargs: object) -> LLMResponse:
            planner_messages.append(user_message)
            return LLMResponse(content=silent.model_dump(mode="json"), metadata=ResponseMetadata())

        async def judge_call(**kwargs: object) -> LLMResponse:
            nonlocal judged
            judged += 1
            return LLMResponse(
                content=verdicts[judged - 1].model_dump(mode="json"), metadata=ResponseMetadata()
            )

        provider = MagicMock()
        provider.provider_type = ProviderType.ANTHROPIC
        provider.generate_json_with_conversation_async = AsyncMock(side_effect=planner_call)
        provider.generate_json_async = AsyncMock(side_effect=judge_call)
        context = MovingHeadPlanningContext(
            audio_profile=profile,
            lyric_context=LyricContextModel(
                has_lyrics=True, vocal_coverage_pct=0.25, moment_cues=[cue]
            ),
            fixtures=FixtureContext(count=4, groups=[]),
            beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=2),
            available_templates=["sweep_lr_fan_pulse"],
        )

        result = await MovingHeadPlannerOrchestrator(provider=provider, max_iterations=3).run(
            context
        )

        assert result.success
        assert len(planner_messages) == 3
        assert judged == 2
        assert "the HIGH lyric moment cue 'hook'" in planner_messages[1]
        assert result.context.advisory_sent


# --- The rig offer (song-intent rendering W3) ---------------------------------------------


@pytest.mark.asyncio
async def test_the_cache_key_tracks_the_rig_offer(
    planning_context: MovingHeadPlanningContext,
) -> None:
    """What the planner is told the rig can show, and what repair keeps, re-keys the plan."""
    orchestrator = MovingHeadPlannerOrchestrator(provider=MagicMock())
    tagged = planning_context.model_copy(update={"rig_offer": m.tagged_offer()})
    untagged = planning_context.model_copy(update={"rig_offer": m.untagged_offer()})

    keys = {
        await orchestrator.get_cache_key(context)
        for context in (planning_context, tagged, untagged)
    }

    assert len(keys) == 3


def test_the_normaliser_repairs_what_the_rig_cannot_show() -> None:
    """Palette roles resolve through each section's macro palette (here
    `core.christmas_traditional`: red, green, warm white, white): on a white/red/blue
    wheel the green ACCENT is shown by no head and is repaired to as authored; PRIMARY's
    red stays. Without the gate's offer nothing is repaired."""
    profile = create_test_audio_profile()
    context = MovingHeadPlanningContext(
        audio_profile=profile,
        fixtures=FixtureContext(count=4, groups=[]),
        available_templates=["sweep_lr_fan_pulse"],
        macro_plan=create_test_macro_plan(profile),
        rig_offer=m.tagged_offer(),
    )
    plan = ChoreographyPlan(
        sections=[
            _answered("intro", 1, 2, "sweep_lr_fan_pulse", color="PALETTE_PRIMARY"),
            _answered("verse_1", 3, 4, "sweep_lr_fan_pulse", color="PALETTE_ACCENT"),
        ],
        overall_strategy=STRATEGY,
    )

    repaired = normalize_plan(plan, context)
    unrepaired = normalize_plan(plan, context.model_copy(update={"rig_offer": None}))

    assert [section.color for section in repaired.sections] == [PlanColor.PALETTE_PRIMARY, None]
    (repair,) = repaired.repairs
    assert repair.section_id == "verse_1"
    assert repair.item == (
        "colour PALETTE_ACCENT (#43A047, palette 'core.christmas_traditional' stop 2)"
    )
    assert repair.reason.startswith("no head's colour wheel shows anything like it")
    assert unrepaired.repairs == [] and unrepaired.sections[1].color is PlanColor.PALETTE_ACCENT


def test_the_planner_prompt_variables_carry_the_offer(
    planning_context: MovingHeadPlanningContext,
) -> None:
    offered = planning_context.model_copy(update={"rig_offer": m.tagged_offer()})

    assert build_planner_variables(planning_context)["rig_offer"] is None
    shown = build_planner_variables(offered)["rig_offer"]
    assert shown["colors_tagged"] is True
    assert [entry["section_ids"] for entry in shown["sections"]] == [
        ["intro", "verse_1", "chorus_1", "outro"]
    ]
