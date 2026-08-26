"""CI-safe display and combined show evaluation through strict persisted seams."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.unit.reporting.evaluation.show_test_support import (
    entry,
    graph,
    macro,
    mapping,
    trace,
)
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.models.xsq import (
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.reporting.evaluation.show_cli import run_show_eval_command
from twinklr.core.reporting.evaluation.show_manifest import (
    load_show_evaluation_manifest,
    write_show_evaluation_manifest,
)
from twinklr.core.reporting.evaluation.show_record import ShowDeterministicReport


def _write_xsq(path) -> None:
    beats = [
        TimeMarker(name=f"1.{index + 1}", time_ms=value)
        for index, value in enumerate((0, 500, 1_000, 1_500, 2_000))
    ]
    bars = [TimeMarker(name="1", time_ms=0), TimeMarker(name="2", time_ms=2_000)]
    sequence = XSequence(
        head=SequenceHead(
            version="2026.15",
            media_file="fixture.wav",
            sequence_duration_ms=2_000,
        ),
        timing_tracks=[
            TimingTrack(name="Twinklr Beats", markers=beats),
            TimingTrack(name="Twinklr Bars", markers=bars),
        ],
    )
    XSQExporter().export(sequence, path)


@pytest.mark.integration
@pytest.mark.parametrize("combined", [False, True])
def test_show_eval_strict_reload_requires_no_xlights_provider_or_audio(tmp_path, combined) -> None:
    xsq_path = tmp_path / "show.xsq"
    trace_path = tmp_path / "show.xsq.trace.json"
    manifest_path = tmp_path / "show.xsq.evaluation.json"
    report_path = tmp_path / "report.json"
    _write_xsq(xsq_path)
    entries = [entry("display", 0, 500)]
    if combined:
        entries.append(entry("moving_head", 500, 1_000))
    trace_path.write_text(trace(*entries).model_dump_json(), encoding="utf-8")
    write_show_evaluation_manifest(
        path=manifest_path,
        xsq_path=xsq_path,
        trace_path=trace_path,
        macro_plan=macro(),
        choreography_graph=graph(),
        xlights_mapping=mapping(),
        moving_head_target_ids={"MOVING_HEADS"} if combined else set(),
    )
    assert load_show_evaluation_manifest(manifest_path).capability.cross_part_applicable is combined
    assert (
        run_show_eval_command(SimpleNamespace(manifest=str(manifest_path), out=str(report_path)))
        == 0
    )
    report = ShowDeterministicReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert report.metrics.cross_part.applicable is combined
    assert report.recipe_ids == ["display-recipe"]
    assert report.moving_head_template_ids == (["mh-template"] if combined else [])
