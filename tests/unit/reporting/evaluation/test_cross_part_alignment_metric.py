"""Public deterministic cross-part scoring seam."""

from __future__ import annotations

import pytest

from tests.unit.reporting.evaluation.show_test_support import entry, grid, manifest, trace
from twinklr.core.reporting.evaluation.show_metrics import score_cross_part_alignment
from twinklr.core.sequencer.planning import CallResponsePair
from twinklr.core.sequencer.templates.group.models.choreography import ChoreoGroup
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.vocabulary import StepUnit, TargetType


def test_schedule_start_500_and_emission_750_report_250_ms_error() -> None:
    rows = trace(
        entry("display", 0, 500),
        entry("moving_head", 750, 1_000),
        entry("display", 1_000, 1_500),
        entry("moving_head", 1_500, 2_000),
    )
    result = score_cross_part_alignment(manifest=manifest(), trace=rows, beat_grid=grid())
    pair = result.pair_alignments[0]
    response = next(item for item in pair.expected if item.expected_start_ms == 500)
    assert response.observed_start_ms == 750
    assert response.signed_error_ms == 250


def test_trace_duplicates_are_deduplicated_and_mapping_names_are_normalized() -> None:
    duplicate = entry("display", 0, 500, event_id="same")
    fixture_trace = entry("moving_head", 500, 1_000).model_copy(
        update={"group_id": "Dmx MH1", "element_name": "Dmx MH1"}
    )
    rows = trace(duplicate, duplicate, fixture_trace)
    result = score_cross_part_alignment(manifest=manifest(), trace=rows, beat_grid=grid())
    assert result.emitted_entry_count == 3
    assert result.deduplicated_entry_count == 2
    assert result.pair_alignments[0].expected[0].observed_start_ms == 0


def test_missing_boundary_is_reported_without_invented_zero() -> None:
    result = score_cross_part_alignment(
        manifest=manifest(),
        trace=trace(entry("display", 100, 500)),
        beat_grid=grid(),
    )
    boundary = result.section_boundaries[0]
    assert boundary.status == "missing_moving_head"
    assert boundary.moving_head_start_ms is None
    assert boundary.signed_offset_ms is None


def test_observed_boundary_difference_is_signed() -> None:
    result = score_cross_part_alignment(
        manifest=manifest(),
        trace=trace(entry("display", 100, 500), entry("moving_head", 0, 500)),
        beat_grid=grid(),
    )
    assert result.section_boundaries[0].signed_offset_ms == 100


def test_unmatched_schedule_windows_are_explicit_not_zero_filled() -> None:
    result = score_cross_part_alignment(
        manifest=manifest(), trace=trace(entry("display", 0, 500)), beat_grid=grid()
    )
    pair = result.pair_alignments[0]
    unmatched = [row for row in pair.expected if row.observed_start_ms is None]
    assert pair.unmatched_expected_count == len(unmatched)
    assert unmatched
    assert all(row.signed_error_ms is None for row in unmatched)


def test_nonspanning_pair_is_excluded_with_truthful_reason() -> None:
    show_manifest = manifest()
    section = show_manifest.macro_plan.sections[0]
    display_graph = show_manifest.choreography_graph.model_copy(
        update={
            "groups": [
                *show_manifest.choreography_graph.groups,
                ChoreoGroup(id="DISPLAY_2", role="DISPLAY"),
            ]
        }
    )
    display = PlanTarget(type=TargetType.GROUP, id="DISPLAY")
    fixture_only_plan = show_manifest.macro_plan.model_copy(
        update={
            "sections": [
                section.model_copy(
                    update={
                        "call_response_pairs": [
                            CallResponsePair(
                                call=display,
                                response=PlanTarget(type=TargetType.GROUP, id="DISPLAY_2"),
                                step_unit=StepUnit.BEAT,
                                step_duration=1,
                            )
                        ]
                    }
                )
            ]
        }
    )
    result = score_cross_part_alignment(
        manifest=show_manifest.model_copy(
            update={"macro_plan": fixture_only_plan, "choreography_graph": display_graph}
        ),
        trace=trace(entry("display", 0, 500), entry("moving_head", 500, 1_000)),
        beat_grid=grid(),
    )
    assert result.pair_alignments[0].applicable is False
    assert result.pair_alignments[0].excluded_reason == (
        "declared pair does not span moving-head and display parts"
    )


def test_unknown_moving_head_fixture_fallback_fails_with_multiple_owners() -> None:
    show_manifest = manifest().model_copy(
        update={"moving_head_target_ids": ["MOVING_HEADS", "MOVING_HEADS_2"]}
    )
    unknown = entry("moving_head", 500, 1_000).model_copy(
        update={"group_id": "Unknown MH fixture", "element_name": "Unknown MH fixture"}
    )
    with pytest.raises(ValueError, match="cannot be normalized"):
        score_cross_part_alignment(
            manifest=show_manifest,
            trace=trace(entry("display", 0, 500), unknown),
            beat_grid=grid(),
        )
