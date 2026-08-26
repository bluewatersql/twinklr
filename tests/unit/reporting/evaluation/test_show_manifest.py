"""Strict show manifest and trace-v2 seam."""

from __future__ import annotations

import json

from pydantic import ValidationError
import pytest

from tests.unit.reporting.evaluation.show_test_support import (
    entry,
    graph,
    macro,
    mapping,
    trace,
)
from twinklr.core.reporting.evaluation.show_manifest import (
    ShowEvaluationManifest,
    identity_sha256,
    load_show_evaluation_manifest,
    load_show_trace,
    write_show_evaluation_manifest,
)
from twinklr.core.sequencer.display.xlights_mapping import XLightsGroupMapping, XLightsMapping


def test_manifest_round_trips_current_models_and_artifact_hashes(tmp_path) -> None:
    xsq_path = tmp_path / "show.xsq"
    trace_path = tmp_path / "show.xsq.trace.json"
    manifest_path = tmp_path / "show.xsq.evaluation.json"
    xsq_path.write_text("<xsequence />", encoding="utf-8")
    trace_path.write_text(
        trace(entry("display", 0, 500), entry("moving_head", 500, 1_000)).model_dump_json(),
        encoding="utf-8",
    )
    write_show_evaluation_manifest(
        path=manifest_path,
        xsq_path=xsq_path,
        trace_path=trace_path,
        macro_plan=macro(),
        choreography_graph=graph(),
        xlights_mapping=mapping(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    loaded = load_show_evaluation_manifest(manifest_path)
    assert loaded.macro_plan == macro()
    assert loaded.choreography_graph.graph_id == "show"
    assert loaded.capability.cross_part_applicable is True
    assert loaded.xsq_path.name == "show.xsq"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "twinklr-xsq-trace.v1", "literal_error"),
        ("entry_count", 2, "entry_count"),
    ],
)
def test_trace_rejects_old_version_and_count_mismatch(tmp_path, field, value, message) -> None:
    payload = trace(entry("display", 0, 500)).model_dump(mode="json")
    payload[field] = value
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        load_show_trace(path)
    assert message in str(error.value)


def test_trace_rejects_unknown_backend(tmp_path) -> None:
    payload = trace(entry("display", 0, 500)).model_dump(mode="json")
    payload["entries"][0]["backend"] = "unknown"
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError, match="literal_error"):
        load_show_trace(path)


def test_manifest_rejects_duplicate_mapping_ids() -> None:
    payload = mapping().model_dump(mode="python")
    payload["entries"].append(XLightsGroupMapping(choreo_id="DISPLAY").model_dump())
    plan = macro()
    show_graph = graph()
    duplicate = XLightsMapping.model_validate(payload)
    with pytest.raises(ValidationError, match="duplicate choreography ids"):
        ShowEvaluationManifest(
            xsq_path="show.xsq",
            trace_path="trace.json",
            xsq_sha256="0" * 64,
            trace_sha256="0" * 64,
            macro_plan_sha256=identity_sha256(plan),
            choreography_graph_sha256=identity_sha256(show_graph),
            xlights_mapping_sha256=identity_sha256(duplicate),
            macro_plan=plan,
            choreography_graph=show_graph,
            xlights_mapping=duplicate,
            moving_head_target_ids=["MOVING_HEADS"],
            capability={
                "has_display": True,
                "has_moving_heads": True,
                "cross_part_applicable": True,
            },
        )
