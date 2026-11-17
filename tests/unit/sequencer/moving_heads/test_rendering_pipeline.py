"""Unit tests for RenderingPipeline.

Covers: initialization, section iteration, fixture context building, the plan schema's
intent fields, and the delivery with timeline tracks.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.support.moving_heads import (
    SUBSET_TEMPLATE_ID,
    bars_grid,
    family_catalog,
    family_job,
    family_rig,
    p1_templates,
    sections_plan,
)
from twinklr.core.agents.sequencer.moving_heads.models import Density, PlanColor, PlanSection
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.models.xsq import TimingTrack
from twinklr.core.sequencer.models.enum import Intensity, TemplateRole
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    UnsupportedRigShapeError,
)
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")


def _make_beat_grid(bars: int = 8) -> BeatGrid:
    return bars_grid(*([500.0] * bars))


def _job(heads: tuple[str, ...] = HEADS, **fields: Any) -> JobConfig:
    """`family_job` for `heads`, with other job fields set from `fields`."""
    payload = family_job(heads).model_dump(mode="json", exclude_unset=True)
    return JobConfig.model_validate({**payload, **fields})


def _pipeline(
    heads: tuple[str, ...] = HEADS,
    sections: tuple[tuple[str, int, int], ...] = (
        ("mirror_wings", 1, 4),
        ("target_orbit", 5, 8),
    ),
    *,
    beat_grid: BeatGrid | None = None,
    job_config: JobConfig | None = None,
    **kwargs: Any,
) -> RenderingPipeline:
    return RenderingPipeline(
        choreography_plan=sections_plan(*sections),
        beat_grid=beat_grid or _make_beat_grid(),
        fixture_group=family_rig(heads),
        job_config=job_config or _job(heads),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with family_catalog():
        yield


def test_plan_section_schema_requires_every_intent_field() -> None:
    schema = PlanSection.model_json_schema()
    assert {
        "parts",
        "intensity",
        "color",
        "gobo",
        "moment_cues",
        "events",
        "motif_id",
        "variation",
        "density",
        "transitions",
    } <= set(schema["required"])


def _unrendered(pipeline: RenderingPipeline) -> list[dict[str, Any]]:
    assert pipeline.render_record is not None
    return [
        diagnostic
        for diagnostic in pipeline.render_record["diagnostics"]
        if "is not rendered yet" in diagnostic["message"]
    ]


def test_a_neutral_section_reports_no_unrendered_intent() -> None:
    pipeline = _pipeline()
    pipeline.render()

    assert _unrendered(pipeline) == []


def test_set_intent_is_reported_unrendered_per_section_and_renders_as_authored() -> None:
    """Song intent is not rendered yet: the frames are those of the neutral plan, and
    each section that set intent says which fields, naming the plan that fixes it."""
    neutral = _pipeline()
    neutral.render()
    plan = neutral.choreography_plan
    accented = plan.model_copy(
        update={
            "sections": [
                plan.sections[0].model_copy(
                    update={"intensity": Intensity.DRAMATIC, "color": PlanColor.PALETTE_ACCENT}
                ),
                plan.sections[1],
            ]
        }
    )
    pipeline = RenderingPipeline(
        choreography_plan=accented,
        beat_grid=_make_beat_grid(),
        fixture_group=family_rig(HEADS),
        job_config=_job(),
    )
    pipeline.render()

    assert pipeline.frames == neutral.frames
    (diagnostic,) = _unrendered(pipeline)
    assert diagnostic["section_id"] == "s1"
    assert "intensity, colour: a known regression" in diagnostic["message"]
    assert "not rendered by any renderer" not in diagnostic["message"]
    assert "plan/song-intent-rendering.md" in diagnostic["message"]


def test_intent_no_renderer_rendered_yet_is_not_called_a_regression() -> None:
    """Fields the renderer before the cutover never rendered are named apart from the
    regressed ones."""
    plan = sections_plan(("mirror_wings", 1, 4))
    section = plan.sections[0].model_copy(
        update={"density": Density.BUSY, "motif_id": "pulse", "intensity": Intensity.FAST}
    )
    pipeline = RenderingPipeline(
        choreography_plan=plan.model_copy(update={"sections": [section]}),
        beat_grid=_make_beat_grid(),
        fixture_group=family_rig(HEADS),
        job_config=_job(),
    )
    pipeline.render()

    (diagnostic,) = _unrendered(pipeline)
    assert "intensity: a known regression" in diagnostic["message"]
    assert "motif, density: not rendered by any renderer yet" in diagnostic["message"]


def test_plan_repairs_reach_the_render_record_only_when_there_are_any() -> None:
    from twinklr.core.agents.sequencer.moving_heads.models import PlanRepair, RepairAction

    plain = _pipeline()
    plain.render()
    assert plain.render_record is not None and "plan_repairs" not in plain.render_record
    repair = PlanRepair(
        section_id="s1", item="moment cue 'x'", action=RepairAction.DROPPED, reason="unknown"
    )
    repaired = RenderingPipeline(
        choreography_plan=plain.choreography_plan.model_copy(update={"repairs": [repair]}),
        beat_grid=_make_beat_grid(),
        fixture_group=family_rig(HEADS),
        job_config=_job(),
    )
    repaired.render()

    assert repaired.frames == plain.frames
    assert repaired.render_record is not None
    assert repaired.render_record["plan_repairs"] == [repair.model_dump(mode="json")]


def test_one_head_rig_collapses_spatial_groups_to_its_only_fixture() -> None:
    pipeline = _pipeline(("MH1",), (("mirror_wings", 1, 4),))

    segments = pipeline.render()

    assert segments
    assert {segment.fixture_id for segment in segments} == {"MH1"}
    assert any(segment.template_id == "mirror_wings" for segment in segments)


EIGHT = tuple(f"MH{index}" for index in range(1, 9))


def test_8head_rig_renders_its_sections_on_every_head() -> None:
    """P4-F26: every plan section emits cues, on all eight heads."""
    segments = _pipeline(EIGHT).render()

    cues = [segment for segment in segments if segment.section_id in {"s1", "s2"}]
    assert {segment.section_id for segment in cues} == {"s1", "s2"}
    assert {segment.fixture_id for segment in cues} == set(EIGHT)


def test_8head_rig_fixture_roles_are_spatial() -> None:
    """The mechanism, named so a future reader does not have to re-derive it."""
    roles = [context.role for context in _pipeline(EIGHT)._build_fixture_contexts()]
    assert roles == [
        TemplateRole.FAR_LEFT,
        TemplateRole.OUTER_LEFT,
        TemplateRole.MID_LEFT,
        TemplateRole.INNER_LEFT,
        TemplateRole.INNER_RIGHT,
        TemplateRole.MID_RIGHT,
        TemplateRole.OUTER_RIGHT,
        TemplateRole.FAR_RIGHT,
    ]


def test_a_group_the_rig_cannot_fill_raises_rather_than_going_dark() -> None:
    """A template addressing RIGHT on a one-head rig (CENTER only) is a rig/plan mismatch
    the operator has to see, not a section to skip in silence."""
    with p1_templates():
        pipeline = _pipeline(("MH1",), ((SUBSET_TEMPLATE_ID, 1, 2),))
        with pytest.raises(UnsupportedRigShapeError, match=SUBSET_TEMPLATE_ID):
            pipeline.render()


@pytest.fixture
def pipeline() -> RenderingPipeline:
    """Create a minimal RenderingPipeline for testing."""
    return _pipeline()


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
        rp = _pipeline(timeline_tracks=[track])
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
        names = [s.section_id for s in sections]
        assert names == ["s1", "s2"]


# ---------------------------------------------------------------------------
# Fixture context building
# ---------------------------------------------------------------------------


class TestBuildFixtureContexts:
    """Tests for _build_fixture_contexts (role inference)."""

    def test_returns_context_per_fixture(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        assert len(contexts) == 4

    def test_four_fixture_roles_assigned(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        roles = [c.role for c in contexts]
        assert roles == ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]

    def test_two_fixture_roles(self) -> None:
        rp = _pipeline(("MH1", "MH2"))
        contexts = rp._build_fixture_contexts()
        roles = [c.role for c in contexts]
        assert roles == ["LEFT", "RIGHT"]

    def test_fixture_ids_match(self, pipeline: RenderingPipeline) -> None:
        contexts = pipeline._build_fixture_contexts()
        ids = [c.fixture_id for c in contexts]
        assert ids == ["MH1", "MH2", "MH3", "MH4"]


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


class TestExportDelivery:
    """The delivery a render with an output path writes, with timeline tracks."""

    def _pipeline(self, tmp_path: Path) -> RenderingPipeline:
        from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker

        beat_track = TimingTrack(
            name="Twinklr Beats",
            markers=[TimeMarker(name="1", time_ms=0), TimeMarker(name="2", time_ms=500)],
        )
        return _pipeline(
            sections=(("mirror_wings", 1, 4),),
            beat_grid=_make_beat_grid(bars=4),
            output_path=tmp_path / "test.xsq",
            timeline_tracks=[beat_track],
            media_file="song.mp3",
        )

    def test_export_creates_xsq_file(self, tmp_path: Path) -> None:
        """The render writes an XSQ file."""
        rp = self._pipeline(tmp_path)
        rp.render()

        assert (tmp_path / "test.xsq").exists()

    def test_export_creates_sidecar_deliverables(self, tmp_path: Path) -> None:
        """The run hands back three kinds of artifact, not just the sequence."""
        rp = self._pipeline(tmp_path)
        rp.render()

        assert rp.artifacts is not None
        assert rp.artifacts.xmap_path == tmp_path / "test.xmap"
        assert {path.name for path in rp.artifacts.xtiming_paths} == {
            "test.audiosections.xtiming",
            "test.beats.xtiming",
        }
        assert all(path.exists() for path in rp.artifacts.all_paths)

    @pytest.mark.parametrize(
        ("config_path", "payload"),
        (
            (
                "job.timeline_tracks",
                {"beats": False, "bars": False, "lyrics": False, "phonemes": True},
            ),
            ("job.timeline_tracks.beats", {"beats": False}),
            ("job.timeline_tracks.bars", {"bars": False}),
            ("job.timeline_tracks.lyrics", {"lyrics": False}),
            ("job.timeline_tracks.phonemes", {"phonemes": True}),
        ),
        ids=(
            "job.timeline_tracks",
            "job.timeline_tracks.beats",
            "job.timeline_tracks.bars",
            "job.timeline_tracks.lyrics",
            "job.timeline_tracks.phonemes",
        ),
    )
    def test_timeline_config_field_changes_rendering_stage_delivery_layers(
        self, tmp_path: Path, config_path: str, payload: dict[str, bool]
    ) -> None:
        """Each timeline knob changes layers emitted by the production stage/delivery path."""
        from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
            MovingHeadRenderingStage,
        )

        audio_bundle = SimpleNamespace(
            lyrics=SimpleNamespace(words=[SimpleNamespace(text="word", start_ms=100, end_ms=200)]),
            phonemes=SimpleNamespace(
                phonemes=[SimpleNamespace(text="W", start_ms=100, end_ms=150)]
            ),
        )

        def delivery_snapshot(job: JobConfig, name: str) -> set[str]:
            context = MagicMock()
            context.job_config = job
            context.get_state.return_value = audio_bundle
            tracks = MovingHeadRenderingStage._build_timeline_tracks(
                _make_beat_grid(bars=4), context
            )
            output_dir = tmp_path / name
            output_dir.mkdir()
            pipeline = _pipeline(
                sections=(("mirror_wings", 1, 4),),
                beat_grid=_make_beat_grid(bars=4),
                job_config=job,
                output_path=output_dir / "test.xsq",
                timeline_tracks=tracks,
                media_file="song.mp3",
            )
            pipeline.render()
            assert pipeline.artifacts is not None
            return {path.name for path in pipeline.artifacts.xtiming_paths}

        baseline = delivery_snapshot(_job(), "baseline")
        changed = delivery_snapshot(_job(timeline_tracks=payload), "changed")

        assert changed != baseline, config_path
