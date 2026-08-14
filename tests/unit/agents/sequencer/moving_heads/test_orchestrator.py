"""Tests for V2 MovingHead orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    MomentCueReference,
    PlanSection,
    ShutterEvent,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
    MovingHeadPlannerOrchestrator,
    build_judge_variables,
    build_planner_variables,
)
from twinklr.core.agents.shared.judge.controller import IterationContext
from twinklr.core.agents.shared.judge.models import JudgeVerdict, VerdictStatus
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


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


@pytest.fixture
def planning_context() -> MovingHeadPlanningContext:
    """Create a test planning context."""
    return MovingHeadPlanningContext(
        audio_profile=create_test_audio_profile(),
        fixtures=FixtureContext(count=4, groups=[{"id": "front", "fixtures": [1, 2]}]),
        available_templates=["sweep_lr_fan_pulse", "circle_fan_hold", "pendulum_chevron_breathe"],
    )


@pytest.fixture
def valid_plan() -> ChoreographyPlan:
    """Create a valid choreography plan."""
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=8,
                template_id="sweep_lr_fan_pulse",
            ),
            PlanSection(
                section_name="verse_1",
                start_bar=9,
                end_bar=24,
                template_id="circle_fan_hold",
            ),
            PlanSection(
                section_name="chorus_1",
                start_bar=25,
                end_bar=40,
                template_id="pendulum_chevron_breathe",
            ),
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
                sections=[
                    PlanSection(
                        section_name="intro",
                        start_bar=1,
                        end_bar=8,
                        template_id="sweep_lr_fan_pulse",
                    )
                ],
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
                PlanSection(
                    section_name="intro",
                    start_bar=1,
                    end_bar=2,
                    template_id="sweep_lr_fan_pulse",
                    moment_cues=[MomentCueReference(cue_id=cue_id)],
                    shutter_events=[
                        ShutterEvent(
                            bar=1,
                            beat=1,
                            pattern="strobe_fast",
                            moment_cue_id=cue_id,
                        )
                    ],
                )
            ],
            overall_strategy="Accentuate the lyric.",
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
        event = normalized.sections[0].shutter_events[0]
        assert (event.bar, event.beat) == (1, 4)

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
                PlanSection(
                    section_name="chorus",  # Display name; normalizer must canonicalize it.
                    start_bar=1,
                    end_bar=2,
                    template_id="sweep_lr_fan_pulse",
                    moment_cues=[MomentCueReference(cue_id=cue_id)],
                    shutter_events=[
                        ShutterEvent(
                            bar=2,
                            beat=4,
                            pattern="strobe_fast",
                            moment_cue_id=cue_id,
                        )
                    ],
                )
            ],
            overall_strategy="Accentuate the lyric.",
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
                    planner_plan.sections[0].model_copy(update={"section_name": "missing_section"})
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
        assert result.plan.sections[0].section_name == "chorus_1"
        event = result.plan.sections[0].shutter_events[0]
        assert (event.bar, event.beat) == (1, 3)
        rendered_judge_request = "\n".join(message["content"] for message in judge_messages)
        assert '"section_name": "chorus_1"' in rendered_judge_request
        assert '"beat": 3' in rendered_judge_request
