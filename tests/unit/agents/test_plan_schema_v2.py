"""Contract tests for the strict-compatible moving-head plan schema v2."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
import pytest

if TYPE_CHECKING:
    from pydantic import BaseModel

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.audio.profile.models import (
    AudioProfileModel,
    CreativeGuidance,
    EnergyPoint,
    EnergyProfile,
    Structure,
)
from twinklr.core.agents.issues import Issue
from twinklr.core.agents.sequencer.group_planner.holistic import HolisticEvaluation
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    ColorIntent,
    ColorIntentKind,
    GoboEvent,
    MomentCueReference,
    PlanModifier,
    PlanSection,
    PlanSegment,
    ShutterEvent,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.planning.group_plan import (
    CorrectionResult,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import (
    LayeringPlan,
    MacroPlan,
    PalettePlan,
)
from twinklr.core.sequencer.vocabulary import intensity as intensity_vocabulary

RESPONSE_MODELS: tuple[type[BaseModel], ...] = (
    ChoreographyPlan,
    AudioProfileModel,
    LyricContextModel,
    JudgeVerdict,
    MacroPlan,
)


def _walk_json(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _schema_depth(schema: dict[str, Any]) -> int:
    definitions = schema.get("$defs", {})

    def visit(node: Any, seen_refs: frozenset[str]) -> int:
        if not isinstance(node, dict):
            if isinstance(node, list):
                return max((visit(item, seen_refs) for item in node), default=0)
            return 0

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            if name in seen_refs:
                return 0
            return visit(definitions[name], seen_refs | {name})

        child_depths: list[int] = []
        for key in ("properties", "items", "anyOf", "oneOf"):
            child = node.get(key)
            if key == "properties" and isinstance(child, dict):
                child_depths.extend(visit(item, seen_refs) for item in child.values())
            elif child is not None:
                child_depths.append(visit(child, seen_refs))
        return (1 if node.get("type") in {"object", "array"} else 0) + max(child_depths, default=0)

    return visit(schema, frozenset())


def test_plan_schema_v2_strict_mode_compatible() -> None:
    for model in RESPONSE_MODELS:
        schema = model.model_json_schema()
        assert schema.get("type") == "object", model.__name__

        nodes = tuple(_walk_json(schema))
        assert all("allOf" not in node for node in nodes), model.__name__

        for node in nodes:
            if node.get("type") != "object":
                continue
            properties = node.get("properties", {})
            assert node.get("additionalProperties") is False, (model.__name__, node)
            assert set(node.get("required", ())) == set(properties), (model.__name__, node)

        property_count = sum(len(node.get("properties", {})) for node in nodes)
        assert property_count <= 5_000, (model.__name__, property_count)
        assert _schema_depth(schema) <= 10, (model.__name__, _schema_depth(schema))
        assert max((len(node.get("enum", ())) for node in nodes), default=0) <= 1_000


def _section_payload() -> dict[str, Any]:
    return {
        "section_name": "chorus_1",
        "start_bar": 1,
        "end_bar": 4,
        "section_role": "chorus",
        "energy_level": 82,
        "template_id": "sweep_lr_fan_pulse",
        "preset_id": None,
        "modifiers": [PlanModifier(key="movement_scale", value="wide")],
        "reasoning": "A broad sweep supports the first chorus.",
        "segments": None,
        "transition_in": None,
        "transition_out": None,
        "intensity": Intensity.DRAMATIC,
        "color_intent": ColorIntent(
            kind=ColorIntentKind.EXPLICIT,
            palette_role=None,
            explicit_color=ColorPreset.BLUE,
        ),
        "shutter_events": [
            ShutterEvent(
                bar=2,
                beat=3,
                pattern=ShutterPattern.STROBE_MEDIUM,
                moment_cue_id="chorus-hit",
            )
        ],
        "gobo_events": [
            GoboEvent(
                bar=3,
                beat=1,
                pattern=GoboPattern.STARS,
                moment_cue_id=None,
            )
        ],
        "moment_cues": [MomentCueReference(cue_id="chorus-hit")],
    }


def test_plan_section_v2_carries_typed_intents() -> None:
    section = PlanSection(**_section_payload())
    round_tripped = PlanSection.model_validate_json(section.model_dump_json())

    assert round_tripped == section
    assert round_tripped.intensity is Intensity.DRAMATIC
    assert round_tripped.color_intent.explicit_color is ColorPreset.BLUE
    assert round_tripped.shutter_events[0].pattern is ShutterPattern.STROBE_MEDIUM
    assert round_tripped.gobo_events[0].pattern is GoboPattern.STARS
    assert round_tripped.moment_cues[0].cue_id == "chorus-hit"


def test_color_intent_schema_correlates_discriminated_arms() -> None:
    """The schema itself, not only a post-validator, must encode the kind/arm XOR."""
    schema = ChoreographyPlan.model_json_schema()
    color_schema = schema["$defs"]["ColorIntent"]
    selection = color_schema["properties"]["selection"]

    assert color_schema["required"] == ["selection"]
    assert selection["discriminator"] == {
        "mapping": {
            "EXPLICIT": "#/$defs/ExplicitColorIntent",
            "PALETTE_ROLE": "#/$defs/PaletteRoleColorIntent",
        },
        "propertyName": "kind",
    }
    assert selection["oneOf"] == [
        {"$ref": "#/$defs/PaletteRoleColorIntent"},
        {"$ref": "#/$defs/ExplicitColorIntent"},
    ]

    palette_arm = schema["$defs"]["PaletteRoleColorIntent"]
    explicit_arm = schema["$defs"]["ExplicitColorIntent"]
    assert palette_arm["properties"]["kind"]["const"] == "PALETTE_ROLE"
    assert palette_arm["properties"]["explicit_color"]["type"] == "null"
    assert explicit_arm["properties"]["kind"]["const"] == "EXPLICIT"
    assert explicit_arm["properties"]["palette_role"]["type"] == "null"


def _segmented_plan() -> ChoreographyPlan:
    payload = _section_payload()
    payload.update(
        {
            "template_id": None,
            "segments": [
                PlanSegment(
                    segment_id="A",
                    start_bar=1,
                    end_bar=2,
                    template_id="sweep_lr_fan_pulse",
                    preset_id=None,
                    modifiers=[],
                    reasoning="First half.",
                ),
                PlanSegment(
                    segment_id="B",
                    start_bar=3,
                    end_bar=4,
                    template_id="circle_fan_hold",
                    preset_id=None,
                    modifiers=[],
                    reasoning="Second half.",
                ),
            ],
            "shutter_events": [
                ShutterEvent(
                    bar=bar,
                    beat=1,
                    pattern=ShutterPattern.STROBE_MEDIUM,
                    moment_cue_id="chorus-hit" if bar == 2 else None,
                )
                for bar in range(1, 5)
            ],
            "gobo_events": [
                GoboEvent(
                    bar=bar,
                    beat=1,
                    pattern=GoboPattern.STARS,
                    moment_cue_id="chorus-hit" if bar == 3 else None,
                )
                for bar in range(1, 5)
            ],
        }
    )
    return ChoreographyPlan(sections=[PlanSection(**payload)], overall_strategy="Segmented.")


def _assert_segment_event_projection(sections: list[PlanSection]) -> None:
    assert [[event.bar for event in section.shutter_events] for section in sections] == [
        [1, 2],
        [3, 4],
    ]
    assert [[event.bar for event in section.gobo_events] for section in sections] == [
        [1, 2],
        [3, 4],
    ]
    assert [section.moment_cues for section in sections] == [
        [MomentCueReference(cue_id="chorus-hit")],
        [MomentCueReference(cue_id="chorus-hit")],
    ]
    assert sections[0].intensity is sections[1].intensity
    assert sections[0].color_intent == sections[1].color_intent


def test_render_pipeline_routes_segment_events_with_inclusive_boundaries() -> None:
    """Absolute event bars belong only to the segment whose inclusive range contains them."""
    from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

    sections = list(RenderingPipeline.iterate_plan_sections(object(), _segmented_plan()))

    _assert_segment_event_projection(sections)


def test_reporting_expansion_routes_segment_events_with_inclusive_boundaries() -> None:
    """Report reproduction must use the identical event projection as live rendering."""
    from twinklr.core.reporting.evaluation.generator import _expand_plan_sections

    sections = _expand_plan_sections(_segmented_plan())

    _assert_segment_event_projection(sections)


def test_plan_section_either_or_invariant() -> None:
    """The post-validation XOR remains explicit to preserve the renderer interface."""
    both = _section_payload()
    both["segments"] = [
        PlanSegment(
            segment_id="all",
            start_bar=1,
            end_bar=4,
            template_id="circle_fan_hold",
            preset_id=None,
            modifiers=[],
            reasoning="Use one segment to exercise the invariant.",
        )
    ]
    with pytest.raises(
        ValidationError,
        match="Provide either 'segments' OR 'template_id', not both",
    ):
        PlanSection(**both)

    neither = _section_payload()
    neither["template_id"] = None
    with pytest.raises(
        ValidationError,
        match="Must provide either 'segments' or 'template_id'",
    ):
        PlanSection(**neither)


@pytest.mark.parametrize(
    ("model", "deleted_fields"),
    [
        (PalettePlan, {"transition_notes"}),
        (LayeringPlan, {"strategy_notes"}),
        (CorrectionResult, {"correction_notes"}),
        (AudioProfileModel, {"agent_id", "schema_version"}),
        (Structure, {"notes"}),
        (EnergyProfile, {"overall_mean", "energy_confidence"}),
        (EnergyPoint, {"energy_0_1"}),
        (CreativeGuidance, {"recommended_asset_usage"}),
        (
            LyricContextModel,
            {"vocal_presence_pct"},
        ),
        (JudgeVerdict, {"overall_assessment", "score_breakdown"}),
        (Issue, {"estimated_effort", "suggested_action", "scope"}),
        (HolisticEvaluation, {"score_breakdown", "recommendations"}),
        (MacroPlan, {"asset_requirements"}),
    ],
)
def test_deleted_fields_are_gone(model: type[BaseModel], deleted_fields: set[str]) -> None:
    assert deleted_fields.isdisjoint(model.model_fields)


def test_audio_profile_prompt_examples_match_strict_response_schema() -> None:
    """Few-shot examples must not teach fields that the response schema rejects."""
    examples_dir = (
        Path(__file__).parents[3]
        / "packages"
        / "twinklr"
        / "core"
        / "agents"
        / "audio"
        / "profile"
        / "prompts"
        / "audio_profile"
        / "examples"
    )

    example_paths = sorted(examples_dir.glob("*.json"))
    assert example_paths
    for example_path in example_paths:
        example = json.loads(example_path.read_text())
        AudioProfileModel.model_validate(example["expected_output"])


def test_dead_intensity_compatibility_shims_are_gone() -> None:
    assert not hasattr(Intensity, "amplitude")
    assert not hasattr(intensity_vocabulary, "INTENSITY_MAP")
    assert not hasattr(intensity_vocabulary, "resolve_intensity")


def test_strict_response_root_boundary_defers_display_models_to_p2p_t11() -> None:
    """P2P-T1 owns five LLM roots; display-only repair remains explicitly P2P-T11 scope."""
    assert (
        ChoreographyPlan,
        AudioProfileModel,
        LyricContextModel,
        JudgeVerdict,
        MacroPlan,
    ) == RESPONSE_MODELS
    assert CorrectionResult not in RESPONSE_MODELS
    assert SectionCoordinationPlan not in RESPONSE_MODELS
