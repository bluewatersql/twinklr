"""Rubric-v2 and visual-evaluator boundary guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.reporting.evaluation.show_test_support import entry, manifest, trace
from twinklr.core.reporting.evaluation.show_judge import (
    COORDINATION_CRITERIA,
    ShowVisionRubricResponse,
    build_show_judge_payload_from_models,
    not_applicable_cross_part,
    validate_rubric_capability,
)
from twinklr.core.reporting.evaluation.vision_judge import RubricCategoryScore


def _category() -> RubricCategoryScore:
    return RubricCategoryScore(score=8, justification="Section shows a clear focal read.")


def test_rubric_v2_has_five_higher_is_better_coordination_criteria() -> None:
    assert [item.criterion_id for item in COORDINATION_CRITERIA] == [
        "focal_clarity",
        "call_response_legibility",
        "cross_part_palette_agreement",
        "section_transition_agreement",
        "mutual_complement",
    ]
    assert all(item.higher_is_better for item in COORDINATION_CRITERIA)


def test_visual_prompt_does_not_request_deterministic_scoring() -> None:
    prompt_dir = (
        Path(__file__).parents[4] / "packages/twinklr/core/agents/prompts/show_vision_judge"
    )
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in prompt_dir.glob("*.j2"))
    assert all(term not in text for term in ("sync", "timing", "alignment", "on the beat"))


def test_display_only_requires_strict_cross_part_na() -> None:
    response = ShowVisionRubricResponse(
        musicality_by_proxy=_category(),
        coordination=_category(),
        color_palette_coherence=_category(),
        variety_and_pacing=_category(),
        cross_part_coordination=not_applicable_cross_part("Only display is present."),
    )
    single = manifest(combined=False).capability
    validate_rubric_capability(response, single)
    with pytest.raises(ValueError, match="must be 'scored'"):
        validate_rubric_capability(response, manifest().capability)


def test_payload_contains_current_plan_claims_and_trace_summary() -> None:
    payload = build_show_judge_payload_from_models(
        manifest(),
        trace(entry("display", 0, 500), entry("moving_head", 500, 1_000)),
    )
    assert all(
        key in payload.claims_json
        for key in ("focal_arc", "focal_roles", "call_response_pairs", "palette_stops", "sections")
    )
    assert "moving_head" in payload.trace_summary_json
