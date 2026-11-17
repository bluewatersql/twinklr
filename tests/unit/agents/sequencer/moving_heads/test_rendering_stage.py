"""Unit tests for the moving head rendering stage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    TEMPLATE_ID,
    hold_step,
    physical_bars_grid,
    physical_grid,
    physical_job,
    physical_plan,
    physical_rig,
    physical_sections,
    physical_template_doc,
    physical_test_templates,
    registered_templates,
    unprofiled_rig,
)
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import MovingHeadRenderingStage
from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.reporting.evaluation.collect import load_checkpoint, recorded_render
from twinklr.core.sequencer.moving_heads.compile.template_compiler import UnsupportedRigShapeError
from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission


def _context_with_fixture_path(fixture_path: str) -> PipelineContext:
    mock_session = MagicMock()
    mock_session.app_config = MagicMock()
    mock_session.job_config = MagicMock()
    mock_session.job_config.fixture_config_path = fixture_path
    return PipelineContext(session=mock_session)


def test_load_fixture_config_resolves_relative_job_config_path(tmp_path: Path) -> None:
    """Relative fixture path resolves against job_config_dir stored in context state."""
    fixture_file = tmp_path / "fixture_config.json"
    fixture_file.write_text('{"fixtures": []}', encoding="utf-8")

    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.set_state("job_config_dir", tmp_path)

    sentinel = MagicMock()
    with patch("twinklr.core.config.loader.load_fixture_group", return_value=sentinel) as mock_load:
        result = stage._load_fixture_config(context)

    assert result is sentinel
    mock_load.assert_called_once_with(fixture_file)


def test_media_metadata_comes_from_the_analyzed_audio(tmp_path: Path) -> None:
    """The delivered sequence names the audio it was choreographed against.

    An empty `mediaFile` is fatal to xLights and to Twinklr's own parser, so the
    resolver reads the bundle the audio stage stored rather than leaving it blank.
    """
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")

    bundle = MagicMock()
    bundle.audio_path = "/music/Need A Favor.mp3"
    bundle.metadata = MetadataBundle.model_construct(
        embedded=EmbeddedMetadata(title="Need A Favor", artist="Luke Combs")
    )
    context.set_state("audio_bundle", bundle)

    assert stage._resolve_media_metadata(context) == (
        "Need A Favor.mp3",
        "Need A Favor",
        "Luke Combs",
    )


def test_media_file_falls_back_when_no_audio_bundle(tmp_path: Path) -> None:
    """With nothing to name, the head still gets a non-empty media file."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    media_file, song, artist = stage._resolve_media_metadata(_context_with_fixture_path("f.json"))

    assert media_file
    assert (song, artist) == ("", "")


@pytest.mark.asyncio
async def test_unsupported_rig_shape_is_reported_as_an_actionable_message(tmp_path: Path) -> None:
    """A template the rig cannot fill fails with guidance, not a traceback.

    The compile raises `UnsupportedRigShapeError` naming the template, the step,
    the group and the roles the rig has (P1P-T5). The stage passes that text through and
    adds what the user can do about it.
    """
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.set_state("beat_grid", MagicMock())

    with (
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=MagicMock()),
        patch.object(MovingHeadRenderingStage, "_build_timeline_tracks", return_value=[]),
        patch(
            "twinklr.core.sequencer.moving_heads.pipeline.RenderingPipeline",
            side_effect=UnsupportedRigShapeError(
                "template 'split_lr_sweep_counter' step 'sweep' targets RIGHT; rig has [CENTER]"
            ),
        ),
    ):
        result = await stage.execute({"moving_heads": MagicMock()}, context)

    assert not result.success
    assert result.error is not None
    assert "split_lr_sweep_counter" in result.error
    assert "rig config" in result.error


@pytest.mark.asyncio
async def test_physical_mode_without_profiles_fails_the_stage(tmp_path: Path) -> None:
    """A physical job on a rig without physical profiles fails, naming each head and
    the missing item, and delivers nothing."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _context_with_fixture_path("fixture_config.json")
    context.session.job_config = physical_job()
    context.set_state("beat_grid", physical_grid())

    with (
        physical_test_templates(),
        patch.object(
            MovingHeadRenderingStage, "_load_fixture_config", return_value=unprofiled_rig()
        ),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert not result.success
    assert result.error is not None
    assert "cannot render this rig" in result.error
    for fixture_id in ("MH1", "MH2", "MH3", "MH4"):
        assert f"{fixture_id}: physical_profile is missing" in result.error
    assert list(tmp_path.iterdir()) == []
    assert context.get_state("delivery_artifacts") is None


def _physical_context() -> PipelineContext:
    context = _context_with_fixture_path("fixture_config.json")
    context.session.job_config = physical_job()
    context.set_state("beat_grid", physical_grid())
    return context


@pytest.mark.asyncio
async def test_physical_job_renders_and_delivers_through_the_stage(tmp_path: Path) -> None:
    """The stage dispatches a physical job to the physical renderer and delivers it,
    with the render identity in the trace beside the `.xsq`."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    artifacts = context.get_state("delivery_artifacts")
    assert artifacts is not None
    assert artifacts.xsq_path == tmp_path / "out.xsq"
    assert artifacts.model_names == ("Dmx MH1", "Dmx MH2")
    trace = json.loads(artifacts.trace_path.read_text(encoding="utf-8"))
    assert trace["render"]["renderer"] == "physical_v2"
    assert len(trace["render"]["render_fingerprint"]) == 64
    assert context.get_state("rendered_segment_count") > 0


@pytest.mark.asyncio
async def test_stage_hands_the_run_layout_to_the_physical_render(tmp_path: Path) -> None:
    """The layout `twinklr run` loads reaches the model check, and the trace says so."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    models = tuple(
        Model.model_validate(
            {"name": f"Dmx MH{index}", "DisplayAs": "DmxMovingHeadAdv", "DmxChannelCount": "18"}
        )
        for index in (1, 2)
    )
    context.set_state("layout_models", models)
    context.set_state("layout_sha256", "ef" * 32)

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    trace = json.loads(context.get_state("delivery_artifacts").trace_path.read_text())
    assert (trace["render"]["layout_check"], trace["render"]["layout_sha256"]) == (
        "performed",
        "ef" * 32,
    )


@pytest.mark.asyncio
async def test_physical_refusal_fails_the_stage_and_delivers_nothing(tmp_path: Path) -> None:
    """A physical job whose heads are not known to be settled is refused, naming the
    head and the item, and writes no file."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    initial = {**PHYSICAL_INITIAL_STATE, "settled": False}
    context.session.job_config = physical_job(initial_states={"MH1": initial, "MH2": initial})
    rig = physical_rig()

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=rig),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert not result.success
    assert result.error is not None
    assert "MH1: moving_heads.initial_states['MH1']: initial state is not settled" in result.error
    assert list(tmp_path.iterdir()) == []
    assert context.get_state("delivery_artifacts") is None


@pytest.mark.asyncio
async def test_the_stage_keeps_the_warning_about_cues_kept_dark(tmp_path: Path) -> None:
    """A plan placing a cue where it cannot play renders dark under the default
    `on_unplayable`; the stage keeps the render's one warning for the run's summary."""
    jump = physical_template_doc(
        "stage_jump",
        [hold_step("l", -90.0, duration=0.5), hold_step("r", 90.0, start=0.5, duration=0.5)],
    )
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    context.set_state("beat_grid", physical_bars_grid(*[500.0] * 4))

    with (
        registered_templates(jump),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute(
            {"moving_heads": physical_sections(("stage_jump", 1, 4))}, context
        )

    assert result.success, result.error
    warning = context.get_state("unplayable_warning")
    assert warning is not None and "cannot play honestly" in warning
    trace = json.loads(context.get_state("delivery_artifacts").trace_path.read_text())
    assert trace["render"]["unplayable_totals"]["infeasible_transition"]["cues"] > 0


def _canonical_sha256(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _checkpoint(output_dir: Path, plan: Any, **fields: Any) -> Path:
    """A plan checkpoint as the planning stage writes it."""
    path = output_dir / "checkpoints" / "plans" / "final.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"run_id": "run", "plan": plan.model_dump(mode="json"), **fields}, indent=2),
        encoding="utf-8",
    )
    return path


@pytest.mark.asyncio
async def test_physical_render_records_itself_in_the_plan_checkpoint(tmp_path: Path) -> None:
    """`eval-report` re-renders a physical plan from what the run rendered: the stage adds
    the render's fingerprint, policy, beat grid and gate result to the run's checkpoint,
    and they read back as the objects the render used."""
    admission = TemplateAdmission(
        admitted=(TEMPLATE_ID,),
        admitted_presets={TEMPLATE_ID: ()},
        effective_preset={TEMPLATE_ID: None},
        exclusions=({"template_id": "other", "reason": "why"},),
        preset_exclusions=(),
        entry_dips={TEMPLATE_ID: {"fixture_id": "MH1", "bound_ms": 120, "beats": 1}},
    )
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    context.output_dir = tmp_path
    context.set_state("template_admission", admission)
    checkpoint = _checkpoint(tmp_path, physical_plan())
    checkpoint.chmod(0o640)

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    trace = json.loads((tmp_path / "out.xsq.trace.json").read_text(encoding="utf-8"))
    data = load_checkpoint(checkpoint)
    assert set(data) == {"run_id", "plan", "render"}
    recorded = recorded_render(data)
    assert recorded is not None
    assert recorded.fingerprint == trace["render"]["render_fingerprint"]
    assert recorded.policy == context.job_config.moving_heads
    assert recorded.beat_grid == physical_grid()
    assert recorded.admission == admission
    # The hashes the trace carries, to name the input that differs on a mismatch, and the
    # rig as the fingerprint hashes it: whole, and field by field.
    rig = physical_rig().model_dump(mode="json")
    assert recorded.inputs == {
        **{
            key: trace["render"][key]
            for key in (
                "fixtures",
                "template_sha256",
                "beat_grid_sha256",
                "renderer_revision",
                "encoder_version",
            )
        },
        "rig": {
            "sha256": _canonical_sha256(rig),
            "fields": {name: _canonical_sha256(value) for name, value in rig.items()},
            "live_layout": False,
        },
    }
    # No dark spans: the record keeps its keys.
    assert "dark_spans" not in data["render"] and "dark_spans" not in data["render"]["inputs"]
    assert recorded.dark_spans == ()
    assert [p.name for p in checkpoint.parent.iterdir()] == ["final.json"]  # no temp left
    assert checkpoint.stat().st_mode & 0o777 == 0o640  # the replaced file keeps its mode


@pytest.mark.asyncio
async def test_a_checkpoint_that_cannot_be_extended_does_not_fail_the_render(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The delivery is written before the record; a checkpoint the stage cannot read
    is left as it is, with a warning, and the render still succeeds."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    context.output_dir = tmp_path
    checkpoint = tmp_path / "checkpoints" / "plans" / "final.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{not json", encoding="utf-8")

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
        caplog.at_level("WARNING"),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    assert (tmp_path / "out.xsq").exists()
    assert checkpoint.read_text(encoding="utf-8") == "{not json"
    assert "could not record the render in the checkpoint" in caplog.text
    assert [p.name for p in checkpoint.parent.iterdir()] == ["final.json"]


@pytest.mark.asyncio
async def test_physical_render_writes_no_checkpoint_the_run_did_not(tmp_path: Path) -> None:
    """With no plan checkpoint (the planning stage writes one when `write_checkpoint`
    holds), the render records nothing."""
    stage = MovingHeadRenderingStage(xsq_output_path=tmp_path / "out.xsq")
    context = _physical_context()
    context.output_dir = tmp_path

    with (
        physical_test_templates(),
        patch.object(MovingHeadRenderingStage, "_load_fixture_config", return_value=physical_rig()),
    ):
        result = await stage.execute({"moving_heads": physical_plan()}, context)

    assert result.success, result.error
    assert not (tmp_path / "checkpoints").exists()
