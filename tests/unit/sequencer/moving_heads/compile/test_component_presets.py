"""Named rig components (P2.1): a physical step names position and attribute presets the
fixture group declares, instead of hard-coding angles and profile state names.

Resolution is per fixture, per axis and per channel: a value set on the (preset-patched)
step wins for that axis or channel alone, a referenced preset supplies the rest, and an
axis set by neither, an unknown preset or a fixture a preset does not declare fails,
never centers. Provenance is recorded per fixture in segment metadata.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
import hashlib
import json
from typing import Any, Literal

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    physical_grid,
    physical_job,
    physical_preset_rig,
    physical_rig,
    physical_sections,
    physical_template_doc,
    preset_library_payload,
    referencing_step,
    registered_templates,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.presets import RigPresetLibrary
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.template import Template, TemplatePreset, TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import (
    PhysicalCompileError,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_GRID = physical_grid()
_PHASE_MAP = build_musical_phase_map(_GRID)


def _template(*steps: dict[str, Any], template_id: str = "p21_probe") -> Template:
    return physical_template_doc(template_id, steps).template


def _compile(
    template: Template,
    rig: FixtureGroup | None = None,
    *,
    duration_bars: int = 2,
    preset: TemplatePreset | None = None,
) -> list[FixtureSegment]:
    rig = rig or physical_preset_rig()
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=_GRID,
        start_bar=1,
        duration_bars=duration_bars,
        presets=rig.presets,
    )
    start_limit, end_limit = physical_cue_limits(_PHASE_MAP, int(_GRID.duration_ms))
    return compile_physical_template(
        template,
        context,
        preset,
        phase_map=_PHASE_MAP,
        start_limit_ms=start_limit,
        end_limit_ms=end_limit,
    ).segments


def _pose(segment: FixtureSegment) -> tuple[float, float]:
    values = []
    for channel in (ChannelName.PAN, ChannelName.TILT):
        physical = segment.channels[channel].physical
        assert isinstance(physical, ContinuousTrajectory)
        assert len({point.value for point in physical.points}) == 1
        values.append(physical.points[0].value)
    return values[0], values[1]


def _held(segment: FixtureSegment) -> dict[str, Any]:
    held: dict[str, Any] = {}
    for channel in (ChannelName.SHUTTER, ChannelName.COLOR, ChannelName.GOBO, ChannelName.DIMMER):
        value = segment.channels.get(channel)
        if value is None:
            continue
        physical = value.physical
        if isinstance(physical, DiscreteTrajectory):
            assert len(physical.events) == 1
            held[channel.value] = physical.events[0].state
        else:
            assert isinstance(physical, ContinuousTrajectory)
            assert len({point.value for point in physical.points}) == 1
            held[channel.value] = physical.points[0].value
    return held


def _provenance(segment: FixtureSegment) -> dict[str, dict[str, str]]:
    return json.loads(segment.metadata["component_provenance"])


def _entry_hash(kind: str, preset_id: str, fixture_id: str) -> str:
    library = RigPresetLibrary.model_validate(preset_library_payload())
    presets = library.positions if kind == "position" else library.attributes
    entry = presets[preset_id].fixtures[fixture_id]
    return hashlib.sha256(entry.model_dump_json().encode()).hexdigest()


def _by_fixture(segments: list[FixtureSegment]) -> dict[str, FixtureSegment]:
    return {segment.fixture_id: segment for segment in segments if segment.t0_ms < 2000}


# --- Resolution and precedence --------------------------------------------------------


def test_references_supply_each_fixtures_pose_states_and_provenance() -> None:
    """MH1 reads `front` and `wash` directly; MH2, which neither declares, reads their
    declared fallbacks `home` and `wash_all`, and the provenance says so."""
    heads = _by_fixture(_compile(_template(referencing_step())))

    assert _pose(heads["MH1"]) == (-30.0, 20.0)
    assert _held(heads["MH1"]) == {"shutter": "open", "color": "red", "gobo": "dots", "dimmer": 0.8}
    assert _pose(heads["MH2"]) == (10.0, 5.0)
    assert _held(heads["MH2"]) == {
        "shutter": "open",
        "color": "blue",
        "gobo": "star",
        "dimmer": 0.6,
    }
    assert _provenance(heads["MH2"])["pan"] == {
        "source": "position",
        "preset_id": "front",
        "resolved_preset_id": "home",
        "sha256": _entry_hash("position", "home", "MH2"),
    }
    assert _provenance(heads["MH2"])["gobo"] == {
        "source": "attribute",
        "preset_id": "wash",
        "resolved_preset_id": "wash_all",
        "sha256": _entry_hash("attribute", "wash_all", "MH2"),
    }


def test_missing_fixture_preset_is_not_centered() -> None:
    """A preset without the fixture and without a fallback fails, naming template, step,
    preset and fixture; so does an unknown preset id and an axis nothing sets. Nothing
    is ever compiled at a centered default."""
    presets = preset_library_payload()
    presets["positions"]["front"].pop("fallback")
    rig = physical_preset_rig(presets)

    with pytest.raises(PhysicalCompileError) as missing:
        _compile(_template(referencing_step()), rig)
    message = str(missing.value)
    for name in ("'p21_probe'", "'look'", "'front'", "'MH2'"):
        assert name in message, message
    assert missing.value.diagnostic.fixture_id == "MH2"

    with pytest.raises(PhysicalCompileError, match=r"'p21_probe'.*'look'.*'nowhere'"):
        _compile(_template(referencing_step(position_id="nowhere")))
    with pytest.raises(PhysicalCompileError, match=r"'p21_probe'.*'look'.*'nothing'.*'MH1'"):
        _compile(_template(referencing_step(attribute_preset_ids=("nothing",))))


def test_unset_axis_without_a_position_reference_is_refused() -> None:
    """An axis neither the step nor a position reference sets is refused: at validation,
    and at compile for a step that lost its reference after validation."""
    with pytest.raises(ValidationError, match=r"start_pan_deg.*never centered"):
        TemplateStep.model_validate(referencing_step(position_id=None))

    template = _template(referencing_step())
    template.steps[0] = template.steps[0].model_copy(update={"component_refs": None})
    with pytest.raises(PhysicalCompileError, match=r"'look'.*'p21_probe'.*start_pan_deg"):
        _compile(template)


def test_step_axis_overrides_reference_only_for_that_axis() -> None:
    """Tilt and color set on the step win for that axis and channel alone; pan and the
    other channels still come from the references."""
    step = referencing_step(physical_color="white")
    step["movement"]["physical"]["start_tilt_deg"] = 45.0
    heads = _by_fixture(_compile(_template(step)))

    assert _pose(heads["MH1"]) == (-30.0, 45.0)
    assert _held(heads["MH1"]) == {
        "shutter": "open",
        "color": "white",
        "gobo": "dots",
        "dimmer": 0.8,
    }
    provenance = _provenance(heads["MH1"])
    assert provenance["tilt"] == {"source": "step"}
    assert provenance["color"] == {"source": "step"}
    assert provenance["pan"]["preset_id"] == "front"
    assert provenance["gobo"]["preset_id"] == "wash"


def test_template_preset_patch_counts_as_set_on_the_step() -> None:
    """A template preset that patches the tilt onto a referencing step sets it on the
    step: every fixture gets the patched tilt with its referenced pan, tilt from `step`."""
    preset = TemplatePreset.model_validate(
        {
            "preset_id": "high",
            "step_patches": {"look": {"movement": {"physical": {"start_tilt_deg": 44.0}}}},
        }
    )
    heads = _by_fixture(_compile(_template(referencing_step()), preset=preset))

    assert _pose(heads["MH1"]) == (-30.0, 44.0)
    assert _pose(heads["MH2"]) == (10.0, 44.0)
    for head in heads.values():
        assert _provenance(head)["tilt"] == {"source": "step"}
        assert _provenance(head)["pan"]["source"] == "position"


def test_step_pulses_replace_referenced_shutter_and_dimmer() -> None:
    """A step's own dimmer or shutter pulse drives that channel; the preset's static
    level or state for it is not applied."""
    step = referencing_step(
        physical_shutter={
            "period_beats": 1.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        }
    )
    step["dimmer"] = {"physical": {"period_beats": 1.0, "duty_cycle": 1.0, "low": 0.0, "high": 0.3}}
    head = _by_fixture(_compile(_template(step)))["MH1"]

    dimmer = head.channels[ChannelName.DIMMER].physical
    shutter = head.channels[ChannelName.SHUTTER].physical
    assert isinstance(dimmer, ContinuousTrajectory) and isinstance(shutter, DiscreteTrajectory)
    assert {point.value for point in dimmer.points} == {0.3}
    assert {event.state for event in shutter.events} == {"open", "closed"}
    assert _provenance(head)["dimmer"] == _provenance(head)["shutter"] == {"source": "step"}


def test_conflicting_attribute_presets_fail_instead_of_last_write_wins() -> None:
    """`wash` and `cool` both set MH1's color at the same level: refused, naming both."""
    with pytest.raises(
        PhysicalCompileError, match="'wash' and 'cool' both set color for fixture 'MH1'"
    ):
        _compile(_template(referencing_step(attribute_preset_ids=("wash", "cool"))))


def test_preset_poses_are_unwrapped_and_still_checked() -> None:
    """A preset pose is never taken modulo 360, and the Phase 1 bounds and travel-rate
    checks still apply to it."""
    presets = preset_library_payload()
    presets["positions"]["side"]["fixtures"]["MH1"]["pan_deg"] = 200.0
    heads = _by_fixture(
        _compile(_template(referencing_step(position_id="side")), physical_preset_rig(presets))
    )
    assert _pose(heads["MH1"])[0] == 200.0

    presets["positions"]["side"]["fixtures"]["MH1"]["pan_deg"] = 300.0
    with pytest.raises(PhysicalChannelError, match="pan"):
        _compile(_template(referencing_step(position_id="side")), physical_preset_rig(presets))

    sweep = referencing_step(position_id="side")
    sweep["movement"]["physical"] = {
        "shape": "linear",
        "mode": "finite",
        "pan_extent_deg": 100.0,
        "period_beats": 0.25,
    }
    with pytest.raises(PhysicalChannelError, match="above the configured speed"):
        _compile(_template(sweep))


def test_attribute_preset_maps_one_name_to_each_profiles_state() -> None:
    """One preset name, `warm`, selects MH1's `red` and MH2's `rot`: each profile's own
    state name, so each head emits its own declared byte."""
    payload = physical_rig().model_dump(mode="python")
    colors = payload["fixtures"][1]["config"]["physical_profile"]["discrete"]["color"]
    colors["states"]["rot"] = colors["states"].pop("red")
    presets = preset_library_payload()
    presets["attributes"]["warm"] = {"fixtures": {"MH1": {"color": "red"}, "MH2": {"color": "rot"}}}
    payload["presets"] = presets
    rig = FixtureGroup.model_validate(payload)

    heads = _by_fixture(
        _compile(
            _template(referencing_step(position_id="side", attribute_preset_ids=("warm",))), rig
        )
    )

    assert _held(heads["MH1"]) == {"color": "red"}
    assert _held(heads["MH2"]) == {"color": "rot"}
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    mh1, mh2 = profiles["MH1"], profiles["MH2"]
    assert mh1 is not None and mh2 is not None
    assert mh1.discrete["color"].resolve("red") == mh2.discrete["color"].resolve("rot") == 14


# --- Rig validation -------------------------------------------------------------------


def test_fallback_cycle_rejected() -> None:
    presets = preset_library_payload()
    presets["positions"]["home"]["fallback"] = "front"
    with pytest.raises(ValidationError, match="cycle: front -> home -> front"):
        RigPresetLibrary.model_validate(presets)

    presets = preset_library_payload()
    presets["attributes"]["cool"]["fallback"] = "cool"
    with pytest.raises(ValidationError, match="cycle: cool -> cool"):
        RigPresetLibrary.model_validate(presets)

    presets = preset_library_payload()
    presets["positions"]["front"]["fallback"] = "nowhere"
    with pytest.raises(ValidationError, match="'nowhere', which is not declared"):
        RigPresetLibrary.model_validate(presets)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda p: p["attributes"]["cool"]["fixtures"]["MH2"].update(color="green"),
            "attribute preset 'cool', fixture 'MH2': color state 'green' is not one of",
        ),
        (
            lambda p: p["attributes"]["cool"]["fixtures"]["MH2"].update(dimmer=1.5),
            "less than or equal to 1",
        ),
        (
            lambda p: p["positions"]["home"]["fixtures"].update(MH9={"pan_deg": 0, "tilt_deg": 0}),
            "position preset 'home' names fixture 'MH9', which is not in the group",
        ),
        (
            lambda p: p["attributes"]["cool"]["fixtures"].update(MH1={}),
            "sets no shutter, color, gobo or dimmer",
        ),
        (
            lambda p: p["attributes"]["cool"]["fixtures"]["MH2"].update(dimmer=0.9),
            r"'cool', fixture 'MH2': dimmer 0.9 is outside the operable range \(0.0, 0.7\)",
        ),
    ],
)
def test_attribute_preset_is_validated_against_each_profile(
    mutate: Callable[[dict[str, Any]], Any], match: str
) -> None:
    presets = preset_library_payload()
    mutate(presets)
    payload = physical_rig().model_dump(mode="python")
    payload["fixtures"][1]["config"]["physical_profile"]["axes"]["dimmer"]["allowed_max"] = 0.7
    payload["presets"] = presets
    with pytest.raises(ValidationError, match=match):
        FixtureGroup.model_validate(payload)


def test_attribute_preset_needs_a_profile_on_the_fixture() -> None:
    """`check_rig` itself refuses an attribute entry for a fixture with no profile."""
    library = RigPresetLibrary.model_validate(preset_library_payload())
    profiles = {f.fixture_id: f.config.physical_profile for f in physical_rig().expand_fixtures()}
    with pytest.raises(
        ValueError, match="'wash_all', fixture 'MH2': the fixture has no physical_profile"
    ):
        library.check_rig({**profiles, "MH2": None})


def test_attribute_preset_needs_the_channel_on_the_profile() -> None:
    payload = physical_rig().model_dump(mode="python")
    profile = payload["fixtures"][1]["config"]["physical_profile"]
    profile["discrete"].pop("gobo")
    payload["presets"] = preset_library_payload()
    with pytest.raises(
        ValidationError, match="'wash_all', fixture 'MH2': the profile declares no gobo"
    ):
        FixtureGroup.model_validate(payload)


# --- Legacy and identity --------------------------------------------------------------


def test_component_refs_are_physical_data() -> None:
    """A step whose aim comes from a position reference alone is a valid step."""
    step = _template(referencing_step()).steps[0]
    assert step.component_refs is not None and step.component_refs.position_id == "front"
    assert step.movement.physical.start_pan_deg is None


def test_empty_preset_library_is_left_out_of_the_group_dump() -> None:
    rig = physical_rig()
    assert rig.presets == RigPresetLibrary()
    assert "presets" not in rig.model_dump(mode="json")
    assert FixtureGroup.model_validate(rig.model_dump(mode="json")) == rig

    with_presets = physical_preset_rig()
    assert with_presets.model_dump(mode="json")["presets"] == RigPresetLibrary.model_validate(
        preset_library_payload()
    ).model_dump(mode="json")

    unreferencing = TemplateStep.model_validate(
        {
            "step_id": "aimed",
            "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
            "movement": {
                "physical": {
                    "shape": "hold",
                    "mode": "periodic",
                    "start_pan_deg": 0.0,
                    "start_tilt_deg": 0.0,
                }
            },
            "dimmer": {},
        }
    )
    assert "component_refs" not in unreferencing.model_dump(mode="json")


def _fingerprint(segment: FixtureSegment) -> str:
    return hashlib.sha256(segment.model_dump_json().encode()).hexdigest()


def test_preset_change_only_changes_dependent_segments() -> None:
    """Editing MH1's entry of `front` changes MH1's segments of the step that names it,
    and nothing else: not MH2's (resolved through `home`), not the step naming `side`."""
    template = _template(
        referencing_step("a", attribute_preset_ids=("cool",), duration=0.5),
        referencing_step(
            "b", position_id="side", attribute_preset_ids=("cool",), start=0.5, duration=0.5
        ),
    )
    presets = preset_library_payload()
    presets["positions"]["front"]["fixtures"]["MH1"]["pan_deg"] = -35.0

    before = _compile(template)
    after = _compile(template, physical_preset_rig(presets))

    assert len(before) == len(after) == 8
    changed = [
        (old.step_id, old.fixture_id)
        for old, new in zip(before, after, strict=True)
        if _fingerprint(old) != _fingerprint(new)
    ]
    assert changed == [("a", "MH1"), ("a", "MH1")]
    for old, new in zip(before, after, strict=True):
        if (old.step_id, old.fixture_id) == ("a", "MH1"):
            assert _pose(new) == (-35.0, 20.0)
            assert _provenance(new)["pan"]["sha256"] != _provenance(old)["pan"]["sha256"]


def test_preset_edit_changes_render_identity_but_not_planning_identity() -> None:
    """Presets are rig data, like fixture calibration: an edit changes the render
    fingerprint (the group's dump) but not the planner's session id, which `twinklr run`
    derives from the app and job configs alone (the job names its fixture file only by
    path), nor the rig the planner is shown (`expand_fixtures`, from which the planner's
    fixture count and groups come; it carries no group-level presets)."""
    document = physical_template_doc("p21_probe", [referencing_step(start=0.5, duration=0.5)])
    presets = preset_library_payload()
    presets["positions"]["front"]["fixtures"]["MH1"]["pan_deg"] = -35.0
    rigs = (physical_preset_rig(), physical_preset_rig(presets))
    with registered_templates(document):
        fingerprints = {
            RenderingPipeline(
                choreography_plan=physical_sections(("p21_probe", 1, 2)),
                beat_grid=_GRID,
                fixture_group=rig,
                job_config=physical_job(),
            ).fingerprint()
            for rig in rigs
        }
    assert len(fingerprints) == 2

    assert JobConfig.model_fields["fixture_config_path"].annotation is str
    assert "presets" not in json.dumps(physical_job().model_dump(mode="json"))
    assert rigs[0].expand_fixtures() == rigs[1].expand_fixtures()
    assert physical_rig().expand_fixtures() == rigs[0].expand_fixtures()


# --- Gate and render ------------------------------------------------------------------


def test_gate_and_render_resolve_references_alike() -> None:
    """The gate dry-compiles with the rig's presets, so a reference this rig cannot
    resolve is refused before planning; on a rig that resolves it, the render's cues
    carry the same resolved values the gate compiled."""
    document = physical_template_doc("p21_probe", [referencing_step(start=0.5, duration=0.5)])
    presets = preset_library_payload()
    presets["attributes"]["wash"].pop("fallback")
    with registered_templates(document):
        with pytest.raises(UnsupportedRenderModeError, match=r"'p21_probe'.*'look'.*'wash'.*'MH2'"):
            check_physical_templates(
                ["p21_probe"],
                beat_grid=_GRID,
                fixture_group=physical_preset_rig(presets),
                initial_states=physical_job().moving_heads.initial_states,
                failure_mode="error",
            )

        rig = physical_preset_rig()
        check_physical_templates(
            ["p21_probe"],
            beat_grid=_GRID,
            fixture_group=rig,
            initial_states=physical_job().moving_heads.initial_states,
            failure_mode="error",
        )
        rendered = RenderingPipeline(
            choreography_plan=physical_sections(("p21_probe", 1, 2)),
            beat_grid=_GRID,
            fixture_group=rig,
            job_config=physical_job(),
        ).render()

    cues = [s for s in rendered if "component_provenance" in s.metadata]
    assert {(s.fixture_id, _pose(s)) for s in cues} == {
        ("MH1", (-30.0, 20.0)),
        ("MH2", (10.0, 5.0)),
    }
    assert {s.fixture_id: _held(s)["color"] for s in cues} == {"MH1": "red", "MH2": "blue"}


# --- Registry evidence for the new config paths ---------------------------------------

Component = Literal["rejected", "compiled"]

_COMPONENT_NOTES: dict[Component, str] = {
    "rejected": "exact path's alternative is rejected by physical validation or compile",
    "compiled": "exact path changes the physical compile result",
}

Mutation = Callable[[dict[str, Any], dict[str, Any]], Any]
"""Mutates (rig presets payload, step payload) in place."""

_POSITIONS = "fixture.presets.positions"
_ATTRIBUTES = "fixture.presets.attributes"
_REFS = "template.template.steps.component_refs"

_MUTATIONS: dict[str, tuple[Component, Mutation]] = {
    "fixture.presets": ("rejected", lambda p, s: p.clear()),
    _POSITIONS: ("rejected", lambda p, s: p["positions"].clear()),
    f"{_POSITIONS}.fixtures": (
        "compiled",
        lambda p, s: p["positions"]["front"].update(
            fixtures={"MH1": {"pan_deg": -40.0, "tilt_deg": 25.0}}
        ),
    ),
    f"{_POSITIONS}.fixtures.pan_deg": (
        "compiled",
        lambda p, s: p["positions"]["front"]["fixtures"]["MH1"].update(pan_deg=-45.0),
    ),
    f"{_POSITIONS}.fixtures.tilt_deg": (
        "compiled",
        lambda p, s: p["positions"]["front"]["fixtures"]["MH1"].update(tilt_deg=35.0),
    ),
    f"{_POSITIONS}.fallback": (
        "compiled",
        lambda p, s: p["positions"]["front"].update(fallback="side"),
    ),
    _ATTRIBUTES: ("rejected", lambda p, s: p["attributes"].clear()),
    f"{_ATTRIBUTES}.fixtures": (
        "compiled",
        lambda p, s: p["attributes"]["wash"].update(fixtures={"MH1": {"color": "blue"}}),
    ),
    f"{_ATTRIBUTES}.fixtures.shutter": (
        "compiled",
        lambda p, s: p["attributes"]["wash"]["fixtures"]["MH1"].update(shutter="closed"),
    ),
    f"{_ATTRIBUTES}.fixtures.color": (
        "compiled",
        lambda p, s: p["attributes"]["wash"]["fixtures"]["MH1"].update(color="white"),
    ),
    f"{_ATTRIBUTES}.fixtures.gobo": (
        "compiled",
        lambda p, s: p["attributes"]["wash"]["fixtures"]["MH1"].update(gobo="star"),
    ),
    f"{_ATTRIBUTES}.fixtures.dimmer": (
        "compiled",
        lambda p, s: p["attributes"]["wash"]["fixtures"]["MH1"].update(dimmer=0.5),
    ),
    f"{_ATTRIBUTES}.fallback": (
        "compiled",
        lambda p, s: p["attributes"]["wash"].update(fallback="cool"),
    ),
    _REFS: ("rejected", lambda p, s: s.pop("component_refs")),
    f"{_REFS}.position_id": (
        "compiled",
        lambda p, s: s["component_refs"].update(position_id="side"),
    ),
    f"{_REFS}.attribute_preset_ids": (
        "compiled",
        lambda p, s: s["component_refs"].update(attribute_preset_ids=["cool"]),
    ),
}
"""Per config path: the one component its alternative must change."""

COMPONENT_PRESET_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_component_preset_field_changes_compile[" in disposition.test_nodeid
)


def _compile_snapshot(presets: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    try:
        rig = physical_preset_rig(presets)
        segments = _compile(_template(step), rig, duration_bars=1)
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": [segment.model_dump(mode="json") for segment in segments]}


def test_component_preset_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and the mutation table describe the same evidence."""
    assert set(COMPONENT_PRESET_PATHS) == set(_MUTATIONS)
    for path, (component, _) in _MUTATIONS.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", COMPONENT_PRESET_PATHS, ids=COMPONENT_PRESET_PATHS)
def test_component_preset_field_changes_compile(config_path: str) -> None:
    """Each preset or reference path changes the one compile component its note names."""
    component, mutate = _MUTATIONS[config_path]
    presets, step = copy.deepcopy(preset_library_payload()), referencing_step()
    mutate(presets, step)

    base = _compile_snapshot(preset_library_payload(), referencing_step())
    changed = _compile_snapshot(presets, step)

    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
    else:
        assert "rejected" not in changed, changed
        assert changed["compiled"] != base["compiled"]
