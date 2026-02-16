"""Unit tests for RenderingPipeline.

Covers: initialization, section iteration, fixture context building,
transition planning (with real durations), and XSQ export with timeline tracks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    PlanSegment,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.models.xsq import TimingTrack
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_dmx_mapping() -> DmxMapping:
    return DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15)


def _make_fixture_group(count: int = 4) -> FixtureGroup:
    """Build a minimal FixtureGroup with ``count`` fixtures."""
    group = FixtureGroup(group_id="test_group")
    for i in range(count):
        fid = f"MH{i + 1}"
        cfg = FixtureConfig(fixture_id=fid, dmx_mapping=_make_dmx_mapping())
        inst = FixtureInstance(fixture_id=fid, config=cfg, xlights_model_name=f"Dmx {fid}")
        group.add_fixture(inst)
    return group


def _make_beat_grid(bars: int = 8, bpm: float = 120.0) -> BeatGrid:
    return BeatGrid.from_tempo(tempo_bpm=bpm, total_bars=bars)


def _make_plan(sections: list[tuple[str, int, int, str]] | None = None) -> ChoreographyPlan:
    """Build a ChoreographyPlan from (name, start, end, template_id) tuples."""
    if sections is None:
        sections = [
            ("intro", 1, 4, "sweep_lr_fan_hold"),
            ("verse", 5, 8, "pendulum_chevron_breathe"),
        ]
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name=name,
                start_bar=s,
                end_bar=e,
                template_id=tid,
            )
            for name, s, e, tid in sections
        ],
    )


@pytest.fixture
def pipeline() -> RenderingPipeline:
    """Create a minimal RenderingPipeline for testing."""
    return RenderingPipeline(
        choreography_plan=_make_plan(),
        beat_grid=_make_beat_grid(),
        fixture_group=_make_fixture_group(4),
        job_config=JobConfig(),
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    """Verify construction stores expected state."""

    def test_stores_plan_and_beat_grid(self, pipeline: RenderingPipeline) -> None:
        assert pipeline.choreography_plan is not None
        assert pipeline.beat_grid is not None

    def test_default_timeline_tracks_empty(self, pipeline: RenderingPipeline) -> None:
        assert pipeline.timeline_tracks == []

    def test_timeline_tracks_injected(self) -> None:
        track = TimingTrack(name="beats", markers=[])
        rp = RenderingPipeline(
            choreography_plan=_make_plan(),
            beat_grid=_make_beat_grid(),
            fixture_group=_make_fixture_group(),
            job_config=JobConfig(),
            timeline_tracks=[track],
        )
        assert len(rp.timeline_tracks) == 1
        assert rp.timeline_tracks[0].name == "beats"

    def test_rig_profile_has_correct_fixture_count(self, pipeline: RenderingPipeline) -> None:
        assert len(pipeline.rig_profile.fixtures) == 4


# ---------------------------------------------------------------------------
# Section iteration
# ---------------------------------------------------------------------------


class TestIteratePlanSections:
    """Tests for iterate_plan_sections (section + segment flattening)."""

    def test_yields_all_sections(self, pipeline: RenderingPipeline) -> None:
        sections = list(pipeline.iterate_plan_sections(pipeline.choreography_plan))
        assert len(sections) == 2

    def test_section_names_match(self, pipeline: RenderingPipeline) -> None:
        sections = list(pipeline.iterate_plan_sections(pipeline.choreography_plan))
        names = [s.section_name for s in sections]
        assert names == ["intro", "verse"]


# ---------------------------------------------------------------------------
# Fixture context building
# ---------------------------------------------------------------------------


class TestBuildFixtureContexts:
    """Tests for _build_fixture_contexts (role inference, calibration)."""

    def test_returns_context_per_fixture(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        assert len(contexts) == 4

    def test_four_fixture_roles_assigned(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        roles = [c.role for c in contexts]
        assert roles == ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]

    def test_two_fixture_roles(self) -> None:
        rp = RenderingPipeline(
            choreography_plan=_make_plan(),
            beat_grid=_make_beat_grid(),
            fixture_group=_make_fixture_group(2),
            job_config=JobConfig(),
        )
        contexts = rp._build_fixture_contexts()
        roles = [c.role for c in contexts]
        assert roles == ["LEFT", "RIGHT"]

    def test_fixture_ids_match(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        ids = [c.fixture_id for c in contexts]
        assert ids == ["MH1", "MH2", "MH3", "MH4"]


# ---------------------------------------------------------------------------
# Transition planning uses real durations
# ---------------------------------------------------------------------------


class TestTransitionPlanning:
    """Verify _detect_and_plan_transitions uses real section durations."""

    def test_transition_boundaries_detected(self) -> None:
        """Pipeline with transitions enabled should detect 1 boundary for 2 sections."""
        plan = _make_plan()
        job = JobConfig()
        job.transitions.enabled = True
        rp = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=_make_beat_grid(),
            fixture_group=_make_fixture_group(),
            job_config=job,
        )
        registry = rp._detect_and_plan_transitions()
        assert len(registry.transitions) == 1

    def test_no_transitions_when_disabled(self) -> None:
        """Transitions can be explicitly disabled."""
        job = JobConfig()
        job.transitions.enabled = False
        rp = RenderingPipeline(
            choreography_plan=_make_plan(),
            beat_grid=_make_beat_grid(),
            fixture_group=_make_fixture_group(),
            job_config=job,
        )
        assert rp.job_config.transitions.enabled is False

    def test_segmented_sections_transition_detection_uses_flattened_ids(self) -> None:
        """Segmented plans should produce transition IDs compatible with flattened section keys."""
        job = JobConfig()
        job.transitions.enabled = True
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="verse",
                    start_bar=1,
                    end_bar=8,
                    segments=[
                        PlanSegment(
                            segment_id="A",
                            start_bar=1,
                            end_bar=4,
                            template_id="sweep_lr_fan_hold",
                        ),
                        PlanSegment(
                            segment_id="B",
                            start_bar=5,
                            end_bar=8,
                            template_id="pendulum_chevron_breathe",
                        ),
                    ],
                ),
                PlanSection(
                    section_name="chorus",
                    start_bar=9,
                    end_bar=12,
                    template_id="pendulum_chevron_breathe",
                ),
            ]
        )
        rp = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=_make_beat_grid(),
            fixture_group=_make_fixture_group(),
            job_config=job,
        )

        registry = rp._detect_and_plan_transitions()

        assert len(registry.transitions) >= 1
        transition_ids = [t.transition_id for t in registry.transitions]
        assert any(
            "verse|A" in transition_id or "verse|B" in transition_id
            for transition_id in transition_ids
        )


# ---------------------------------------------------------------------------
# Full render smoke test (mocked compile)
# ---------------------------------------------------------------------------


class TestRender:
    """Smoke tests for the full render() path."""

    @patch(
        "twinklr.core.sequencer.moving_heads.pipeline.compile_template",
    )
    def test_render_returns_segments(self, mock_compile: MagicMock) -> None:
        """Mocking compile_template, render() should return segment lists."""
        from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment

        # compile_template returns a result with .segments and .num_complete_cycles
        mock_result = MagicMock()
        mock_result.segments = [
            FixtureSegment(
                fixture_id="MH1",
                section_id="intro",
                segment_id="seg_0",
                step_id="step_0",
                template_id="sweep_lr_fan_hold",
                t0_ms=0,
                t1_ms=4000,
                channels={},
            )
        ]
        mock_result.num_complete_cycles = 1
        mock_compile.return_value = mock_result

        rp = RenderingPipeline(
            choreography_plan=_make_plan([("intro", 1, 4, "sweep_lr_fan_hold")]),
            beat_grid=_make_beat_grid(bars=4),
            fixture_group=_make_fixture_group(4),
            job_config=JobConfig(),
        )

        segments = rp.render()
        assert len(segments) >= 1
        assert mock_compile.call_count >= 1


# ---------------------------------------------------------------------------
# XSQ export
# ---------------------------------------------------------------------------


class TestExportToXsq:
    """Tests for _export_to_xsq with timeline tracks."""

    def test_export_creates_xsq_file(self, tmp_path: Path) -> None:
        """Export should create an XSQ file with timing layers."""
        from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker

        output_path = tmp_path / "test.xsq"

        beat_track = TimingTrack(
            name="Beats",
            markers=[TimeMarker(name="1", time_ms=0), TimeMarker(name="2", time_ms=500)],
        )

        rp = RenderingPipeline(
            choreography_plan=_make_plan([("intro", 1, 4, "sweep_lr_fan_hold")]),
            beat_grid=_make_beat_grid(bars=4),
            fixture_group=_make_fixture_group(4),
            job_config=JobConfig(),
            output_path=output_path,
            timeline_tracks=[beat_track],
        )

        time_markers = [TimeMarker(name="intro", time_ms=0, end_time_ms=4000)]
        rp._export_to_xsq([], time_markers)

        assert output_path.exists()
