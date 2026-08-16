"""Executable contract for the Phase 3 typed macro plan."""

from pathlib import Path
from types import SimpleNamespace, UnionType
from typing import get_args, get_origin
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel, ValidationError
import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.prompts import PromptRenderer
from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.schema_utils import strict_json_schema, strict_schema_stats
from twinklr.core.agents.sequencer.group_planner.context import project_macro_section
from twinklr.core.agents.sequencer.macro_planner.heuristics import (
    MacroPlanHeuristicValidator,
)
from twinklr.core.agents.sequencer.macro_planner.orchestrator import (
    MacroPlannerOrchestrator,
)
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict
from twinklr.core.sequencer.planning import (
    CallResponsePair,
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
from twinklr.core.sequencer.templates.group.models import (
    ChoreographyGraph,
    ChoreoGroup,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    MotionDensity,
    StepUnit,
    TargetType,
)
from twinklr.core.sequencer.vocabulary.visual import PaletteRole


def _target(group_id: str = "ARCHES") -> PlanTarget:
    return PlanTarget(type=TargetType.GROUP, id=group_id)


def _palette(palette_id: str) -> PaletteRef:
    return PaletteRef(palette_id=palette_id, role=None, intensity=None, variant=None)


def _section(
    section_id: str = "verse_1",
    *,
    target_id: str = "ARCHES",
    motif_ids: list[str] | None = None,
    palette_stop_id: str = "warm",
) -> MacroSection:
    target = _target(target_id)
    return MacroSection(
        section=SongSectionRef(
            section_id=section_id,
            name="Verse",
            start_ms=0,
            end_ms=10_000,
        ),
        energy_target=EnergyTarget.MED,
        motion_density=MotionDensity.MED,
        choreography_style=ChoreographyStyle.HYBRID,
        palette_role=PaletteRoleRef(stop_id=palette_stop_id, override=None),
        theme=ThemeRef(
            theme_id="theme.abstract.neon",
            scope=ThemeScope.SECTION,
            tags=[],
            palette_id=None,
        ),
        motif_ids=motif_ids if motif_ids is not None else ["pulse"],
        focal_roles=[FocalRole(target=target, role=FocalRoleKind.LEAD)],
        call_response_pairs=[
            CallResponsePair(
                call=target,
                response=_target("TREE"),
                step_unit=StepUnit.BEAT,
                step_duration=1,
            )
        ],
        coordination_intent=CoordinationMode.CALL_RESPONSE,
        notes="Typed macro prose guidance for the section planner.",
    )


def _plan(section: MacroSection | None = None) -> MacroPlan:
    section = section or _section()
    section_id = section.section.section_id
    return MacroPlan(
        sections=[section],
        palette_arc=[
            PaletteStop(
                stop_id="warm",
                palette=_palette("core.christmas_traditional"),
                applies_from_section_id=section_id,
                transition=PaletteTransition.HOLD,
            )
        ],
        motif_continuity=[
            MotifThread(
                motif_id="pulse",
                section_ids=[section_id],
                evolution=MotifEvolution.INTRODUCE,
                description="A recurring pulse that anchors the show.",
            )
        ],
        focal_arc=[
            FocalAssignment(
                section_id=section_id,
                lead_target=next(
                    role.target for role in section.focal_roles if role.role == FocalRoleKind.LEAD
                ),
            )
        ],
    )


def test_contract_fields() -> None:
    assert set(MacroPlan.model_fields) == {
        "sections",
        "palette_arc",
        "motif_continuity",
        "focal_arc",
    }
    assert set(MacroSection.model_fields) == {
        "section",
        "energy_target",
        "motion_density",
        "choreography_style",
        "palette_role",
        "theme",
        "motif_ids",
        "focal_roles",
        "call_response_pairs",
        "coordination_intent",
        "notes",
    }


MACRO_READER_LEAVES = {
    "sections[].section.section_id",
    "sections[].section.name",
    "sections[].section.start_ms",
    "sections[].section.end_ms",
    "sections[].energy_target",
    "sections[].motion_density",
    "sections[].choreography_style",
    "sections[].palette_role.stop_id",
    "sections[].palette_role.override.palette_id",
    "sections[].palette_role.override.role",
    "sections[].palette_role.override.intensity",
    "sections[].palette_role.override.variant",
    "sections[].theme.theme_id",
    "sections[].theme.scope",
    "sections[].theme.tags[]",
    "sections[].theme.palette_id",
    "sections[].motif_ids[]",
    "sections[].focal_roles[].target.type",
    "sections[].focal_roles[].target.id",
    "sections[].focal_roles[].role",
    "sections[].call_response_pairs[].call.type",
    "sections[].call_response_pairs[].call.id",
    "sections[].call_response_pairs[].response.type",
    "sections[].call_response_pairs[].response.id",
    "sections[].call_response_pairs[].step_unit",
    "sections[].call_response_pairs[].step_duration",
    "sections[].coordination_intent",
    "sections[].notes",
    "palette_arc[].stop_id",
    "palette_arc[].palette.palette_id",
    "palette_arc[].palette.role",
    "palette_arc[].palette.intensity",
    "palette_arc[].palette.variant",
    "palette_arc[].applies_from_section_id",
    "palette_arc[].transition",
    "motif_continuity[].motif_id",
    "motif_continuity[].section_ids[]",
    "motif_continuity[].evolution",
    "motif_continuity[].description",
    "focal_arc[].section_id",
    "focal_arc[].lead_target.type",
    "focal_arc[].lead_target.id",
}

# P3-T5 is explicitly the first behavioral consumer of these leaves.  P3-T4 reads,
# projects, prompts, validates, and cache-keys them, but does not claim emitted behavior.
P3_T5_BEHAVIORAL_READS = {
    "sections[].call_response_pairs[].call.type",
    "sections[].call_response_pairs[].call.id",
    "sections[].call_response_pairs[].response.type",
    "sections[].call_response_pairs[].response.id",
    "sections[].call_response_pairs[].step_unit",
    "sections[].call_response_pairs[].step_duration",
    "sections[].coordination_intent",
}


def _flatten_reader_leaves(value: object, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        flattened: dict[str, object] = {}
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten_reader_leaves(item, child))
        return flattened
    if isinstance(value, list):
        flattened = {}
        if not value:
            return {f"{prefix}[]": value}
        for item in value:
            flattened.update(_flatten_reader_leaves(item, f"{prefix}[]"))
        return flattened
    return {prefix: value}


def _schema_leaf_paths(model_type: type[BaseModel], prefix: str = "") -> set[str]:
    """Recursively derive the contract leaf registry from Pydantic annotations."""
    leaves: set[str] = set()
    for name, field in model_type.model_fields.items():
        path = f"{prefix}.{name}" if prefix else name
        annotation = field.annotation
        args = get_args(annotation)
        if get_origin(annotation) in (list, tuple):
            item_type = args[0]
            item_path = f"{path}[]"
            if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                leaves.update(_schema_leaf_paths(item_type, item_path))
            else:
                leaves.add(item_path)
            continue
        if get_origin(annotation) in (UnionType,):
            annotation = next(arg for arg in args if arg is not type(None))
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            leaves.update(_schema_leaf_paths(annotation, path))
        else:
            leaves.add(path)
    return leaves


def _mutated_reader_plan() -> MacroPlan:
    """Construct an invariant-bypassing sentinel whose every contract leaf differs."""
    override = PaletteRef.model_construct(
        palette_id="core.ice_blue",
        role=PaletteRole.ACCENT,
        intensity=0.5,
        variant="mutated",
    )
    lead = PlanTarget.model_construct(type=TargetType.ZONE, id="HOUSE")
    section = MacroSection.model_construct(
        section=SongSectionRef.model_construct(
            section_id="bridge_9", name="Bridge", start_ms=111, end_ms=22_222
        ),
        energy_target=EnergyTarget.LOW,
        motion_density=MotionDensity.SPARSE,
        choreography_style=ChoreographyStyle.ABSTRACT,
        palette_role=PaletteRoleRef.model_construct(stop_id="cool", override=override),
        theme=ThemeRef.model_construct(
            theme_id="theme.other",
            scope=ThemeScope.SONG,
            tags=["mutated-tag"],
            palette_id="core.ice_blue",
        ),
        motif_ids=["mutated-motif"],
        focal_roles=[FocalRole.model_construct(target=lead, role=FocalRoleKind.SUPPORT)],
        call_response_pairs=[
            CallResponsePair.model_construct(
                call=PlanTarget.model_construct(type=TargetType.SPLIT, id="LEFT"),
                response=PlanTarget.model_construct(type=TargetType.ZONE, id="YARD"),
                step_unit=StepUnit.BAR,
                step_duration=2,
            )
        ],
        coordination_intent=CoordinationMode.COMPLEMENTARY,
        notes="Mutated typed macro prose guidance for discrimination.",
    )
    return MacroPlan.model_construct(
        sections=[section],
        palette_arc=[
            PaletteStop.model_construct(
                stop_id="cool",
                palette=override,
                applies_from_section_id="bridge_9",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[
            MotifThread.model_construct(
                motif_id="mutated-motif",
                section_ids=["bridge_9"],
                evolution=MotifEvolution.VARY,
                description="Mutated motif-thread description.",
            )
        ],
        focal_arc=[FocalAssignment.model_construct(section_id="bridge_9", lead_target=lead)],
    )


def test_every_field_has_a_named_mutation_discriminating_reader() -> None:
    baseline = _flatten_reader_leaves(_plan().reader_projection())
    mutated = _flatten_reader_leaves(_mutated_reader_plan().reader_projection())

    assert set(baseline) == MACRO_READER_LEAVES
    assert set(mutated) == MACRO_READER_LEAVES
    assert {path for path in MACRO_READER_LEAVES if baseline[path] == mutated[path]} == set()
    assert P3_T5_BEHAVIORAL_READS < MACRO_READER_LEAVES


def test_named_reader_registry_is_derived_from_the_recursive_schema() -> None:
    assert _schema_leaf_paths(MacroPlan) == MACRO_READER_LEAVES


def test_group_projection_reads_the_complete_section_contract() -> None:
    plan = _plan()
    projection = project_macro_section(plan, plan.sections[0]).reader_projection()
    assert projection["macro_section"] == plan.reader_projection()["sections"][0]
    assert projection["palette_stop"] == plan.reader_projection()["palette_arc"][0]
    assert projection["motif_threads"] == plan.reader_projection()["motif_continuity"]
    assert projection["focal_assignment"] == plan.reader_projection()["focal_arc"][0]


def test_motif_cross_reference_validation() -> None:
    invalid = _plan().model_dump()
    invalid["sections"][0]["motif_ids"] = ["missing_motif"]
    invalid["motif_continuity"] = []
    with pytest.raises(ValidationError, match="missing_motif"):
        MacroPlan.model_validate(invalid)


def test_motif_membership_is_bidirectional() -> None:
    section_missing_from_thread = _plan().model_dump()
    second = _section("chorus_1").model_copy(
        update={
            "section": SongSectionRef(
                section_id="chorus_1",
                name="Chorus",
                start_ms=10_000,
                end_ms=20_000,
            )
        }
    )
    section_missing_from_thread["sections"].append(second.model_dump())
    section_missing_from_thread["focal_arc"].append(
        FocalAssignment(section_id="chorus_1", lead_target=_target()).model_dump()
    )
    section_missing_from_thread["motif_continuity"][0]["section_ids"] = ["chorus_1"]
    with pytest.raises(ValidationError, match=r"pulse.*verse_1|verse_1.*pulse"):
        MacroPlan.model_validate(section_missing_from_thread)

    thread_missing_from_section = _plan().model_dump()
    thread_missing_from_section["sections"][0]["motif_ids"] = []
    with pytest.raises(ValidationError, match=r"pulse.*verse_1|verse_1.*pulse"):
        MacroPlan.model_validate(thread_missing_from_section)


def test_empty_motif_contract_is_valid() -> None:
    plan = _plan().model_dump()
    plan["sections"][0]["motif_ids"] = []
    plan["motif_continuity"] = []
    assert MacroPlan.model_validate(plan).motif_continuity == []


def test_palette_stop_cross_reference_validation() -> None:
    with pytest.raises(ValidationError, match="missing_stop"):
        _plan(_section(palette_stop_id="missing_stop"))


def test_focal_and_call_response_targets_resolve_against_graph() -> None:
    plan = _plan(_section(target_id="MISSING"))
    graph = ChoreographyGraph(
        graph_id="test",
        groups=[
            ChoreoGroup(id="ARCHES", role="ARCHES"),
            ChoreoGroup(id="TREE", role="TREE"),
        ],
    )
    with pytest.raises(ValidationError, match="MISSING"):
        MacroPlan.model_validate(plan.model_dump(), context={"choreo_graph": graph})


def test_focal_arc_matches_exactly_one_section_lead() -> None:
    plan = _plan()
    mismatched = plan.model_dump()
    mismatched["focal_arc"][0]["lead_target"]["id"] = "TREE"
    with pytest.raises(ValidationError, match=r"focal_arc.*LEAD"):
        MacroPlan.model_validate(mismatched)


def test_call_response_requires_distinct_targets() -> None:
    plan = _plan()
    invalid = plan.model_dump()
    invalid["sections"][0]["call_response_pairs"][0]["response"] = invalid["sections"][0][
        "call_response_pairs"
    ][0]["call"]
    with pytest.raises(ValidationError, match="call and response must differ"):
        MacroPlan.model_validate(invalid)


def test_palette_arc_starts_at_first_section_and_follows_section_order() -> None:
    first = _section("verse_1")
    second = _section("chorus_1")
    second = second.model_copy(
        update={"section": second.section.model_copy(update={"start_ms": 10_000, "end_ms": 20_000})}
    )
    plan = _plan(first).model_dump()
    plan["sections"].append(second.model_dump())
    plan["focal_arc"].append(
        FocalAssignment(section_id="chorus_1", lead_target=_target()).model_dump()
    )
    plan["palette_arc"][0]["applies_from_section_id"] = "chorus_1"
    with pytest.raises(ValidationError, match="first palette stop"):
        MacroPlan.model_validate(plan)


def test_theme_palette_must_not_conflict_with_typed_palette_role() -> None:
    plan = _plan().model_dump()
    plan["sections"][0]["theme"]["palette_id"] = "core.ice_blue"
    with pytest.raises(ValidationError, match="theme palette_id"):
        MacroPlan.model_validate(plan)


def test_schema_is_structured_outputs_compatible() -> None:
    schema = strict_json_schema(MacroPlan)
    stats = strict_schema_stats(schema)
    assert schema["type"] == "object"
    assert "anyOf" not in schema
    assert schema["required"] == list(MacroPlan.model_fields)
    assert stats.property_count <= 5_000
    assert stats.max_depth <= 10
    assert stats.enum_value_count <= 1_000

    palette_role = schema["$defs"]["PaletteRoleRef"]
    assert "override" in palette_role["required"]
    assert {branch.get("type") for branch in palette_role["properties"]["override"]["anyOf"]} == {
        None,
        "null",
    }


def test_macro_plan_theme_scope_ref_has_no_annotation_sibling() -> None:
    raw_scope = MacroPlan.model_json_schema()["$defs"]["ThemeRef"]["properties"]["scope"]
    assert raw_scope == {
        "$ref": "#/$defs/ThemeScope",
        "description": "How broadly the theme applies (SONG, SECTION, or PLACEMENT)",
    }

    sent_scope = strict_json_schema(MacroPlan)["$defs"]["ThemeRef"]["properties"]["scope"]
    assert sent_scope == {"$ref": "#/$defs/ThemeScope"}


def test_duplicate_and_stale_cross_references_name_the_value() -> None:
    duplicate = _plan().model_dump()
    duplicate["palette_arc"].append(duplicate["palette_arc"][0])
    with pytest.raises(ValidationError, match="warm"):
        MacroPlan.model_validate(duplicate)

    stale = _plan().model_dump()
    stale["motif_continuity"][0]["section_ids"] = ["stale_section"]
    with pytest.raises(ValidationError, match="stale_section"):
        MacroPlan.model_validate(stale)


def test_external_catalog_and_typed_target_rejection() -> None:
    plan = _plan()
    audio_profile = SimpleNamespace(structure=SimpleNamespace(sections=[plan.sections[0].section]))
    issues = MacroPlanHeuristicValidator().validate(
        plan,
        audio_profile,  # type: ignore[arg-type]
        motif_by_id={},
        palette_ids={"core.ice_blue"},
        display_groups=[{"id": "ARCHES"}, {"id": "TREE"}],
    )
    issue_ids = {issue.issue_id for issue in issues}
    assert "MOTIF_UNKNOWN_pulse" in issue_ids
    assert "PALETTE_UNKNOWN_core.christmas_traditional" in issue_ids


def test_external_audio_section_and_theme_catalog_equality() -> None:
    plan = _plan()
    mismatched_audio = SimpleNamespace(
        structure=SimpleNamespace(
            sections=[
                SongSectionRef(
                    section_id="verse_1",
                    name="Wrong canonical name",
                    start_ms=0,
                    end_ms=9_999,
                )
            ]
        )
    )
    issues = MacroPlanHeuristicValidator().validate(
        plan,
        mismatched_audio,  # type: ignore[arg-type]
        theme_ids={"theme.other"},
        tag_ids={"other-tag"},
    )
    issue_ids = {issue.issue_id for issue in issues}
    assert "COVERAGE_SECTION_MISMATCH" in issue_ids
    assert "THEME_UNKNOWN_theme.abstract.neon" in issue_ids

    tagged = plan.model_dump()
    tagged["sections"][0]["theme"]["tags"] = ["unknown-tag"]
    tagged_plan = MacroPlan.model_validate(tagged)
    tag_issues = MacroPlanHeuristicValidator().validate(
        tagged_plan,
        SimpleNamespace(structure=SimpleNamespace(sections=[plan.sections[0].section])),  # type: ignore[arg-type]
        theme_ids={"theme.abstract.neon"},
        tag_ids={"known-tag"},
    )
    assert "THEME_TAG_UNKNOWN_unknown-tag" in {issue.issue_id for issue in tag_issues}


def test_macro_zone_validation_uses_choreography_tags_not_physical_zones() -> None:
    plan_data = _plan().model_dump()
    house = {"type": TargetType.ZONE.value, "id": "HOUSE"}
    plan_data["sections"][0]["focal_roles"][0]["target"] = house
    plan_data["focal_arc"][0]["lead_target"] = house
    plan = MacroPlan.model_validate(plan_data)
    display = [
        {"id": "TAGGED", "tags": ["HOUSE"], "position": {"zone": "YARD"}},
        {"id": "PHYSICAL_ONLY", "tags": [], "position": {"zone": "ACCENT"}},
        {"id": "TREE"},
    ]

    issues = MacroPlanHeuristicValidator().validate(
        plan,
        SimpleNamespace(  # type: ignore[arg-type]
            structure=SimpleNamespace(sections=[plan.sections[0].section])
        ),
        display_groups=display,
    )
    assert not any("TARGET_ZONE_UNKNOWN" in issue.issue_id for issue in issues)

    accent_data = plan.model_dump()
    accent = {"type": TargetType.ZONE.value, "id": "ACCENT"}
    accent_data["sections"][0]["focal_roles"][0]["target"] = accent
    accent_data["focal_arc"][0]["lead_target"] = accent
    accent_plan = MacroPlan.model_validate(accent_data)
    accent_issues = MacroPlanHeuristicValidator().validate(
        accent_plan,
        SimpleNamespace(structure=SimpleNamespace(sections=[accent_plan.sections[0].section])),  # type: ignore[arg-type]
        display_groups=display,
    )
    assert "TARGET_ZONE_UNKNOWN_verse_1_ACCENT" in {issue.issue_id for issue in accent_issues}


def test_section_id_canonicalization_rewrites_all_cross_references() -> None:
    plan = _plan(_section("chorus"))
    canonical = SongSectionRef(
        section_id="chorus_1",
        name="Chorus",
        start_ms=0,
        end_ms=10_000,
    )
    profile = SimpleNamespace(structure=SimpleNamespace(sections=[canonical]))
    orchestrator = MacroPlannerOrchestrator(provider=MagicMock())

    orchestrator._canonicalize_section_ids(plan, profile)

    assert plan.sections[0].section.section_id == "chorus_1"
    assert plan.palette_arc[0].applies_from_section_id == "chorus_1"
    assert plan.motif_continuity[0].section_ids == ["chorus_1"]
    assert plan.focal_arc[0].section_id == "chorus_1"
    MacroPlan.model_validate(plan.model_dump())


def test_macro_prompt_pack_renders_new_contract_with_strict_undefined() -> None:
    plan = _plan()
    audio_profile = SimpleNamespace(
        song_identity=SimpleNamespace(
            title="Sentinel Song",
            artist="Sentinel Artist",
            duration_ms=10_000,
            bpm=120.0,
        ),
        structure=SimpleNamespace(sections=[plan.sections[0].section]),
        energy_profile=SimpleNamespace(macro_energy=SimpleNamespace(value="MED")),
        creative_guidance=SimpleNamespace(
            recommended_motion_density=SimpleNamespace(value="MED"),
            recommended_contrast=SimpleNamespace(value="HIGH"),
            cautions=[],
        ),
    )
    common = {
        "audio_profile": audio_profile,
        "display_groups": [SimpleNamespace(id="ARCHES", element_kind="ARCH")],
        "theme_catalog": [SimpleNamespace(theme_id="theme.abstract.neon", title="Neon")],
        "palette_catalog": [SimpleNamespace(id="core.christmas_traditional", title="Traditional")],
        "motif_catalog": [SimpleNamespace(id="pulse", energy="MED", description="Pulse")],
        "taxonomy": get_taxonomy_dict(),
        "response_schema": "{}",
        "iteration": 0,
        "feedback": "Keep the typed contract coherent.",
        "revision_request": None,
        "macro_plan": plan,
    }
    prompt_root = Path("packages/twinklr/core/agents/sequencer/macro_planner/prompts")
    renderer = PromptRenderer()
    rendered = "\n".join(
        renderer.render(path.read_text(), common) for path in sorted(prompt_root.glob("*/*.j2"))
    )

    assert "Sentinel Song" in rendered
    assert "palette_arc" in rendered
    assert "motif_continuity" in rendered
    assert "focal_arc" in rendered
    for legacy in ("global_story", "layering_plan", "primary_focus_targets"):
        assert legacy not in rendered


def test_section_palette_override_precedes_arc_stop() -> None:
    plan = _plan()
    assert plan.palette_for_section("verse_1").palette_id == "core.christmas_traditional"

    overridden = plan.model_copy(
        update={
            "sections": [
                plan.sections[0].model_copy(
                    update={
                        "palette_role": PaletteRoleRef(
                            stop_id="warm",
                            override=_palette("core.ice_blue"),
                        )
                    }
                )
            ]
        }
    )
    assert overridden.palette_for_section("verse_1").palette_id == "core.ice_blue"


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_macro_cross_reference_schema_repair_is_bounded_and_accounted(
    tmp_path: Path,
    repair_succeeds: bool,
) -> None:
    """A malformed typed cross-reference gets exactly one response-level repair."""
    prompt_pack = tmp_path / "macro"
    prompt_pack.mkdir()
    (prompt_pack / "system.j2").write_text("Return the injected typed response schema.")
    (prompt_pack / "user.j2").write_text("Return the macro plan.")

    valid = _plan().model_dump(mode="json")
    invalid = _plan().model_dump(mode="json")
    invalid["sections"][0]["motif_ids"] = ["missing_motif"]
    usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    provider = MagicMock()
    provider.provider_type = ProviderType.OPENAI
    provider.generate_json_async = AsyncMock(
        side_effect=[
            LLMResponse(content=invalid, metadata=ResponseMetadata(token_usage=usage)),
            LLMResponse(
                content=valid if repair_succeeds else invalid,
                metadata=ResponseMetadata(token_usage=usage),
            ),
        ]
    )
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
    spec = AgentSpec(
        name="macro_contract_repair",
        prompt_pack="macro",
        response_model=MacroPlan,
        max_schema_repair_attempts=1,
    )

    result = await runner.run(spec=spec, variables={})

    assert result.success is repair_succeeds
    assert provider.generate_json_async.await_count == 2
    assert result.tokens_used == 30
    assert result.metadata["logical_request_count"] == 2
