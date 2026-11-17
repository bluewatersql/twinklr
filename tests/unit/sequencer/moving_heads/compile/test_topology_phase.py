"""Stable topology and separate phase domains (P2.2).

A fixture group's topology describes the canonical full rig. A physical step's
`physical_distribution` spreads phase over it per domain (pan, tilt, dimmer, shutter):
rank comes from the canonical `(row, column, ordinal, fixture_id)` order of the whole
rig, so rendering a subset of heads, or a rig with a head missing, never rephases the
others. Slot 0 leads; a fixture's phase in a domain is the step phase minus its offset.
Two mirrored wings flip the sign of the pan displacement only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import copy
from fractions import Fraction
from itertools import combinations
import json
from typing import Any, Literal

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    hold_step,
    physical_grid,
    physical_job,
    physical_rig,
    physical_sections,
    physical_template_doc,
    preset_library_payload,
    registered_templates,
    sine_step,
    sweep_step,
    topology_payload,
    topology_rig,
)
from twinklr.core.config.fixtures import FixtureGroup
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
from twinklr.core.sequencer.models.moving_heads.topology import (
    FixtureTopology,
    PhaseDistribution,
    resolve_distribution,
    rig_topology,
)
from twinklr.core.sequencer.models.template import Template, TemplateStep
from twinklr.core.sequencer.moving_heads import pipeline as pipeline_module
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.timing.musical_phase import (
    build_musical_phase_map,
    musical_phase_fraction,
)

_GRID = physical_grid()
_PHASE_MAP = build_musical_phase_map(_GRID)
_PAN, _TILT, _DIMMER, _SHUTTER = (
    ChannelName.PAN,
    ChannelName.TILT,
    ChannelName.DIMMER,
    ChannelName.SHUTTER,
)


def _ids(count: int) -> tuple[str, ...]:
    return tuple(f"MH{index}" for index in range(1, count + 1))


def _topology(ids: tuple[str, ...]) -> FixtureTopology:
    return FixtureTopology.model_validate(topology_payload(ids))


def _spec(**fields: Any) -> PhaseDistribution:
    return PhaseDistribution.model_validate({"domains": ["pan"], **fields})


def _resolve(
    topology: FixtureTopology, spec: PhaseDistribution, ids: tuple[str, ...]
) -> tuple[list[Fraction], list[int]]:
    resolved = resolve_distribution(topology, [spec], ids)
    return (
        [resolved[fixture_id].phase_by_channel[_PAN] for fixture_id in ids],
        [resolved[fixture_id].pan_sign for fixture_id in ids],
    )


def _template(*steps: dict[str, Any], cycle_bars: float = 1.0) -> Template:
    return physical_template_doc("p22_probe", steps, cycle_bars=cycle_bars).template


def _compile(
    template: Template, rig: FixtureGroup, *, duration_bars: int = 1
) -> list[FixtureSegment]:
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=_GRID,
        start_bar=1,
        duration_bars=duration_bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    start_limit, end_limit = physical_cue_limits(_PHASE_MAP, int(_GRID.duration_ms))
    return compile_physical_template(
        template, context, phase_map=_PHASE_MAP, start_limit_ms=start_limit, end_limit_ms=end_limit
    ).segments


def _by_fixture(segments: list[FixtureSegment]) -> dict[str, FixtureSegment]:
    first: dict[str, FixtureSegment] = {}
    for segment in segments:
        first.setdefault(segment.fixture_id, segment)
    return first


def _points(segment: FixtureSegment, channel: ChannelName) -> list[tuple[int, float]]:
    physical = segment.channels[channel].physical
    assert isinstance(physical, ContinuousTrajectory)
    return [(point.t_ms, point.value) for point in physical.points]


def _events(segment: FixtureSegment, channel: ChannelName) -> list[tuple[int, str]]:
    physical = segment.channels[channel].physical
    assert isinstance(physical, DiscreteTrajectory)
    return [(event.t_ms, event.state) for event in physical.events]


def _rig(count: int, **fields: Any) -> FixtureGroup:
    ids = _ids(count)
    return topology_rig(ids, topology=topology_payload(ids), **fields)


# --- Rank, fold, block and slot arithmetic -------------------------------------------

_HEAD_CASES = {
    1: ([0], [1], [0], [0]),
    2: ([0, 1], [1, 1], [0, 0], [-1, 1]),
    3: ([0, Fraction(1, 2), 1], [1] * 3, [0, 1, 0], [-1, 0, 1]),
    4: ([0, Fraction(1, 3), Fraction(2, 3), 1], [1] * 4, [0, 1, 1, 0], [-1, -1, 1, 1]),
    6: (
        [Fraction(slot, 5) for slot in range(6)],
        [1] * 6,
        [0, Fraction(1, 2), 1, 1, Fraction(1, 2), 0],
        [-1, -1, -1, 1, 1, 1],
    ),
}


@pytest.mark.parametrize("count", sorted(_HEAD_CASES))
def test_offsets_and_signs_for_each_rig_size(count: int) -> None:
    """One cycle spread from the first slot to the last, one wing and two mirrored
    wings; an odd center sits at the fold with no pan displacement."""
    ids = _ids(count)
    one_offsets, one_signs, two_offsets, two_signs = _HEAD_CASES[count]
    topology = _topology(ids)
    assert _resolve(topology, _spec(spread_cycles=1.0), ids) == (one_offsets, one_signs)
    assert _resolve(topology, _spec(spread_cycles=1.0, wings=2), ids) == (two_offsets, two_signs)


def test_exact_five_head_folded_block_group_arrays() -> None:
    """The plan's worked example pins the denominator and the endpoints."""
    ids = _ids(5)
    topology = _topology(ids)
    spec = {"wings": 2, "block_size": 2, "group_count": 2, "spread_cycles": 0.5}
    half = Fraction(1, 2)

    assert _resolve(topology, _spec(**spec), ids) == ([0, 0, half, 0, 0], [-1, -1, 0, 1, 1])
    assert _resolve(topology, _spec(**spec, direction="reverse"), ids) == (
        [half, half, 0, half, half],
        [-1, -1, 0, 1, 1],
    )
    without_center = ("MH1", "MH2", "MH4", "MH5")
    assert _resolve(topology, _spec(**spec), without_center) == ([0, 0, 0, 0], [-1, -1, 1, 1])
    assert _resolve(topology, _spec(**spec, direction="reverse"), without_center) == (
        [half] * 4,
        [-1, -1, 1, 1],
    )


@pytest.mark.parametrize(
    ("spec", "offsets"),
    [
        ({"block_size": 2, "spread_cycles": 1.0}, ["0", "0", "1/2", "1/2", "1", "1"]),
        ({"group_count": 2, "spread_cycles": 0.5}, ["0", "1/2", "0", "1/2", "0", "1/2"]),
        ({"block_size": 2, "group_count": 2, "spread_cycles": 1.0}, ["0", "0", "1", "1", "0", "0"]),
        ({"group_count": 9, "spread_cycles": 1.0}, ["0", "1/5", "2/5", "3/5", "4/5", "1"]),
        (
            {"spread_cycles": 0.1, "direction": "reverse"},
            ["1/10", "2/25", "3/50", "1/25", "1/50", "0"],
        ),
    ],
)
def test_blocks_and_interleaved_phase_groups(spec: dict[str, Any], offsets: list[str]) -> None:
    """Blocks share a slot; groups interleave slots; a group count above the block count
    changes nothing; offsets are exact fractions of the decimal spread."""
    ids = _ids(6)
    assert _resolve(_topology(ids), _spec(**spec), ids)[0] == [Fraction(o) for o in offsets]


def test_two_rows_fold_as_one_canonical_order_whatever_the_member_order() -> None:
    """Rows sort first, then columns; wings fold the whole ordered rig."""
    placed = {"A": (1, 0), "B": (1, 1), "C": (1, 2), "D": (0, 0), "E": (0, 1), "F": (0, 2)}
    members = [
        {"fixture_id": fixture_id, "row": row, "column": column, "ordinal": index}
        for index, (fixture_id, (row, column)) in enumerate(reversed(placed.items()))
    ]
    topology = FixtureTopology.model_validate({"members": members})
    assert topology.canonical_ids == ("D", "E", "F", "A", "B", "C")
    ids = ("D", "E", "F", "A", "B", "C")
    assert _resolve(topology, _spec(wings=2, spread_cycles=1.0), ids) == (
        [0, Fraction(1, 2), 1, 1, Fraction(1, 2), 0],
        [-1, -1, -1, 1, 1, 1],
    )
    assert resolve_distribution(topology, [_spec()], ("B",))["B"].rank == 4


def test_ordinal_breaks_a_row_and_column_tie() -> None:
    members = [
        {"fixture_id": "MH1", "row": 0, "column": 0, "ordinal": 7},
        {"fixture_id": "MH2", "row": 0, "column": 0, "ordinal": 3},
    ]
    topology = FixtureTopology.model_validate({"members": members})
    assert topology.canonical_ids == ("MH2", "MH1")


_SUBSET_SPECS = [
    {"spread_cycles": 1.0},
    {"spread_cycles": 0.75, "wings": 2},
    {"spread_cycles": 0.5, "wings": 2, "block_size": 2, "group_count": 2},
    {"spread_cycles": 1.0, "group_count": 3, "direction": "reverse"},
]


@pytest.mark.parametrize("count", [5, 6])
def test_every_subset_keeps_each_heads_full_rig_phase_and_sign(count: int) -> None:
    ids = _ids(count)
    topology = _topology(ids)
    for fields in _SUBSET_SPECS:
        spec = _spec(**fields, domains=["pan", "dimmer"])
        full = resolve_distribution(topology, [spec], ids)
        for size in range(1, count):
            for subset in combinations(ids, size):
                resolved = resolve_distribution(topology, [spec], subset)
                assert set(resolved) == set(subset)
                for fixture_id in subset:
                    assert resolved[fixture_id] == full[fixture_id], (fields, subset)


def test_missing_middle_head_leaves_a_hole_in_the_compiled_rig() -> None:
    """A rig with MH3 absent but declared in the topology compiles every other head
    exactly as the full rig does."""
    ids = _ids(5)
    template = _template(
        sine_step(
            "wave",
            0.0,
            20.0,
            distribution=[{"domains": ["pan", "dimmer"], "wings": 2, "spread_cycles": 0.5}],
            dimmer={"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        )
    )
    full = _compile(template, topology_rig(ids, topology=topology_payload(ids)))
    holed_ids = ("MH1", "MH2", "MH4", "MH5")
    holed = _compile(template, topology_rig(holed_ids, topology=topology_payload(ids)))

    full_by_fixture = {s.fixture_id: s.model_dump(mode="json") for s in full}
    assert {s.fixture_id for s in holed} == set(holed_ids)
    for segment in holed:
        assert segment.model_dump(mode="json") == full_by_fixture[segment.fixture_id]
    # Three folded ranks: the dimmer, which has no mirror sign, pairs the wings.
    dimmer = {s.fixture_id: _points(s, _DIMMER) for s in full}
    assert dimmer["MH1"] == dimmer["MH5"] and dimmer["MH2"] == dimmer["MH4"]
    assert len({json.dumps(points) for points in dimmer.values()}) == 3


# --- Domains ----------------------------------------------------------------------------


def test_dimmer_spread_shifts_only_the_dimmer() -> None:
    template = _template(
        sine_step(
            "wave",
            0.0,
            20.0,
            distribution=[{"domains": ["dimmer"], "spread_cycles": 0.5}],
            dimmer={"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        )
    )
    rig = _rig(2)
    resolved = resolve_distribution(
        rig_topology(rig), template.steps[0].physical_distribution, ("MH1", "MH2")
    )
    assert resolved["MH2"].phase_by_channel == {
        _PAN: 0,
        _TILT: 0,
        _DIMMER: Fraction(1, 2),
        _SHUTTER: 0,
    }
    assert resolved["MH2"].pan_sign == 1

    heads = _by_fixture(_compile(template, rig))
    assert _points(heads["MH1"], _PAN) == _points(heads["MH2"], _PAN)
    assert _points(heads["MH1"], _TILT) == _points(heads["MH2"], _TILT)
    first, second = _points(heads["MH1"], _DIMMER), _points(heads["MH2"], _DIMMER)
    assert [t for t, _ in first] == [t for t, _ in second]
    assert all(a == 1.0 - b for (_, a), (_, b) in zip(first, second, strict=True))


def test_overlapping_or_unphased_domains_are_rejected() -> None:
    step = sine_step("wave", 0.0, 20.0)
    for distribution in (
        [{"domains": ["pan", "tilt"]}, {"domains": ["tilt"]}],
        [{"domains": ["color"]}],
        [{"domains": ["gobo"]}],
        [{"domains": []}],
        [{"domains": ["pan", "pan"]}],
        [{"domains": ["pan"], "block_size": 0}],
        [{"domains": ["pan"], "group_count": 0}],
        [{"domains": ["pan"], "spread_cycles": -0.25}],
        [{"domains": ["pan"], "wings": 3}],
    ):
        with pytest.raises(ValidationError):
            TemplateStep.model_validate({**step, "physical_distribution": distribution})
    with pytest.raises(ValueError, match="tilt"):
        resolve_distribution(
            _topology(_ids(2)),
            [_spec(domains=["pan", "tilt"]), _spec(domains=["tilt"])],
            _ids(2),
        )
    with pytest.raises(ValueError, match="MH9"):
        resolve_distribution(_topology(_ids(2)), [_spec()], ("MH9",))


# --- Offset direction, mirror sign -----------------------------------------------------


def test_lagging_linear_head_holds_at_start_until_its_phase_begins() -> None:
    """Offsets 0 and 0.25 of a 1.6-beat period (800 ms at 500 ms beats): the second head
    holds its start pose for 200 ms, then traces the first head's path 200 ms late; both
    end at the terminal pose."""
    template = _template(
        sweep_step(
            "sweep",
            -30.0,
            60.0,
            period_beats=1.6,
            physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.25}],
        )
    )
    heads = _by_fixture(_compile(template, _rig(2)))
    lead, lag = dict(_points(heads["MH1"], _PAN)), dict(_points(heads["MH2"], _PAN))
    assert heads["MH1"].t0_ms == heads["MH2"].t0_ms == 20
    t1 = heads["MH1"].t1_ms
    assert t1 == 2020

    assert lead[40] > -30.0
    assert all(lag[t] == -30.0 for t in range(20, 240, 20))
    assert lag[240] > -30.0
    assert all(lag[t] == lead[t - 200] for t in range(220, t1 + 1, 20))
    assert lead[800] < 30.0 and lead[820] == 30.0
    assert lag[1000] < 30.0 and lag[1020] == 30.0
    assert lead[t1] == lag[t1] == 30.0


def test_step_ending_before_a_lagging_heads_phase_reaches_one_cuts_it_midway() -> None:
    """A one-bar step over a one-bar (four-beat) linear period: the leading head reaches
    the terminal pose at the step end; the head lagging half a period is cut where its
    path has reached, about halfway, and nothing carries it on."""
    template = _template(
        sweep_step(
            "sweep",
            -30.0,
            60.0,
            period_beats=4.0,
            physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.5}],
        )
    )
    heads = _by_fixture(_compile(template, _rig(2)))
    lead, lag = _points(heads["MH1"], _PAN), _points(heads["MH2"], _PAN)
    assert lead[-1] == (2020, 30.0)
    # The step end falls 5 ms into bar 2's faster beats, just past half a period.
    reached = musical_phase_fraction(_PHASE_MAP, 2020, origin_ms=20, period_beats=4.0)
    assert lag[-1] == (2020, -30.0 + 60.0 * float(reached - Fraction(1, 2)))
    assert lag[-1][1] == pytest.approx(0.0375)
    assert max(value for _, value in lag) == lag[-1][1]


def test_mirror_sign_flips_pan_displacement_not_the_referenced_aim() -> None:
    """With a position reference each head keeps its own base aim; the left wing's pan
    displacement is negated, the right wing's kept, and tilt's displacement untouched."""
    ids = ("MH1", "MH2")

    def step(distribution: list[dict[str, Any]]) -> dict[str, Any]:
        payload = sweep_step("sweep", 0.0, 15.0, period_beats=2.0)
        payload["movement"]["physical"]["tilt_extent_deg"] = 10.0
        for name in ("start_pan_deg", "start_tilt_deg"):
            payload["movement"]["physical"].pop(name)
        payload["component_refs"] = {"position_id": "side"}
        if distribution:
            payload["physical_distribution"] = distribution
        return payload

    rig = topology_rig(ids, topology=topology_payload(ids), presets=preset_library_payload())
    plain = _by_fixture(_compile(_template(step([])), rig))
    mirrored = _by_fixture(_compile(_template(step([{"domains": ["pan"], "wings": 2}])), rig))
    base = {"MH1": 60.0, "MH2": -60.0}  # preset `side`, not mirrored
    for fixture_id, sign in (("MH1", -1), ("MH2", 1)):
        for (t, value), (t_plain, value_plain) in zip(
            _points(mirrored[fixture_id], _PAN), _points(plain[fixture_id], _PAN), strict=True
        ):
            assert t == t_plain
            displacement = value_plain - base[fixture_id]
            assert value - base[fixture_id] == pytest.approx(sign * displacement, abs=1e-12)
        assert _points(mirrored[fixture_id], _TILT) == _points(plain[fixture_id], _TILT)
    assert _points(mirrored["MH1"], _PAN)[0][1] == 60.0
    assert _points(mirrored["MH1"], _PAN)[-1][1] == 45.0
    assert _points(mirrored["MH1"], _TILT)[-1][1] == 40.0


def test_two_wings_on_another_domain_leave_the_pan_sign() -> None:
    """Only the distribution that owns pan mirrors it."""
    ids = _ids(4)
    topology = _topology(ids)
    for specs in (
        [_spec(domains=["dimmer"], wings=2, spread_cycles=0.5)],
        [_spec(spread_cycles=0.5), _spec(domains=["dimmer"], wings=2)],
    ):
        resolved = resolve_distribution(topology, specs, ids)
        assert [resolved[fixture_id].pan_sign for fixture_id in ids] == [1, 1, 1, 1]


def test_bounds_check_sees_each_heads_mirrored_path() -> None:
    """A finite move from 260 degrees by -15: unmirrored every head stays inside the
    270-degree limit; mirrored, the left wing moves +15 and only it is refused."""
    step = sweep_step(
        "sweep",
        260.0,
        -15.0,
        period_beats=2.0,
        physical_distribution=[{"domains": ["pan"], "wings": 2}],
    )
    plain = copy.deepcopy(step)
    plain.pop("physical_distribution")
    _compile(_template(plain), _rig(2))

    with pytest.raises(PhysicalChannelError, match="pan") as error:
        _compile(_template(step), _rig(2))
    assert error.value.fixture_id == "MH1"


# --- Pulses at the step edges ----------------------------------------------------------


def _shutter_step(phase_cycles: float, spread: float, *, duration: float = 1.0) -> dict[str, Any]:
    step = hold_step(
        "strobe",
        0.0,
        duration=duration,
        physical_shutter={
            "period_beats": 1.0,
            "duty_cycle": 0.5,
            "phase_cycles": phase_cycles,
            "low_state": "closed",
            "high_state": "open",
        },
        physical_distribution=[{"domains": ["shutter"], "spread_cycles": spread}],
    )
    step.pop("physical_shutter_state")
    return step


def test_lagging_pulse_starts_mid_cycle_and_rises_when_its_phase_reaches_zero() -> None:
    """Offset 0.25 of a one-beat pulse: at the step start the lagging head is in the
    last quarter of its cycle (low) and opens 125 ms later, on the next frame."""
    heads = _by_fixture(_compile(_template(_shutter_step(0.0, 0.25)), _rig(2)))
    assert _events(heads["MH1"], _SHUTTER)[:3] == [(20, "open"), (280, "closed"), (520, "open")]
    assert _events(heads["MH2"], _SHUTTER)[:3] == [(20, "closed"), (160, "open"), (400, "closed")]


def test_lagging_pulse_cut_intervals_at_step_edges_follow_the_phase1_rule() -> None:
    """The interval cut by the step start is exempt from the one-frame rule and holds
    the first frame (10 ms of low becomes the frame at 20 ms); the one cut by the step
    end is exempt too and, shorter than a frame, never reaches a frame: offset 0.97
    rises at 2005 ms, so the cue stays low from its last fall at 1760 ms."""
    start = _by_fixture(_compile(_template(_shutter_step(0.0, 0.02)), _rig(2)))
    assert _events(start["MH2"], _SHUTTER)[:2] == [(20, "closed"), (40, "open")]

    end = _by_fixture(_compile(_template(_shutter_step(0.0, 0.97)), _rig(2)))
    assert end["MH2"].t1_ms == 2020
    assert _events(end["MH2"], _SHUTTER)[-2:] == [(1520, "open"), (1760, "closed")]


def test_pulse_width_check_runs_at_each_heads_own_phase() -> None:
    """A 15 ms high interval straddles the unshifted head's step start and end (cut,
    exempt), but sits inside the lagging head's step, which is refused."""
    step = _shutter_step(0.02, 0.5, duration=0.25)
    step["physical_shutter"]["duty_cycle"] = 0.03
    template = _template(step, cycle_bars=0.25)
    unshifted = copy.deepcopy(step)
    unshifted.pop("physical_distribution")
    _compile(_template(unshifted, cycle_bars=0.25), _rig(2))

    with pytest.raises(PhysicalChannelError, match="shorter than one 20 ms frame") as error:
        _compile(template, _rig(2))
    assert error.value.fixture_id == "MH2"


# --- Rigs without a topology -----------------------------------------------------------


def test_rig_without_topology_derives_one_row_from_position_index() -> None:
    rig = topology_rig(("MH1", "MH2", "MH3"), position_indexes=(3, 1, 2))
    assert rig.topology is None
    topology = rig_topology(rig)
    assert topology is not None
    order = [f.fixture_id for f in rig_profile_from_fixture_group(rig).fixtures]
    assert topology.canonical_ids == tuple(order) == ("MH2", "MH3", "MH1")

    template = _template(
        sweep_step(
            "sweep",
            -30.0,
            60.0,
            period_beats=2.0,
            physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.5}],
        )
    )
    heads = _by_fixture(_compile(template, rig))
    phases = {
        fixture_id: json.loads(segment.metadata["phase_distribution"])
        for fixture_id, segment in heads.items()
    }
    assert phases == {
        "MH2": {
            "rank": 0,
            "pan_sign": 1,
            "offsets": {"pan": "0", "tilt": "0", "dimmer": "0", "shutter": "0"},
        },
        "MH3": {
            "rank": 1,
            "pan_sign": 1,
            "offsets": {"pan": "1/4", "tilt": "0", "dimmer": "0", "shutter": "0"},
        },
        "MH1": {
            "rank": 2,
            "pan_sign": 1,
            "offsets": {"pan": "1/2", "tilt": "0", "dimmer": "0", "shutter": "0"},
        },
    }


def test_derived_row_keeps_the_slot_of_a_skipped_position_index() -> None:
    """Heads at indices 1, 2, 4 and 5 rank as the full 1..5 row does: the head that
    left index 3 leaves a hole, and the others compile exactly as on the full rig."""
    template = _template(
        sine_step(
            "wave",
            0.0,
            20.0,
            distribution=[{"domains": ["pan"], "wings": 2, "spread_cycles": 0.5}],
        )
    )
    full_ids, holed_ids = _ids(5), ("MH1", "MH2", "MH4", "MH5")
    full_rig = topology_rig(full_ids, position_indexes=(1, 2, 3, 4, 5))
    holed_rig = topology_rig(holed_ids, position_indexes=(1, 2, 4, 5))
    holed_topology = rig_topology(holed_rig)
    assert holed_topology is not None
    assert resolve_distribution(holed_topology, [_spec()], holed_ids)["MH4"].rank == 3

    full = {s.fixture_id: s.model_dump(mode="json") for s in _compile(template, full_rig)}
    holed = _compile(template, holed_rig)
    assert {s.fixture_id for s in holed} == set(holed_ids)
    for segment in holed:
        assert segment.model_dump(mode="json") == full[segment.fixture_id]


def test_derived_row_refuses_a_distribution_over_shared_position_indexes() -> None:
    rig = topology_rig(_ids(3), position_indexes=(1, 2, 2))
    distributed = _template(
        sine_step("wave", 0.0, 20.0, distribution=[{"domains": ["pan"], "spread_cycles": 0.5}])
    )
    with pytest.raises(PhysicalCompileError, match=r"\['MH2', 'MH3'\] share a position_index"):
        _compile(distributed, rig)
    _compile(_template(sine_step("wave", 0.0, 20.0)), rig)  # no distribution: fine


def test_rig_without_topology_or_positions_refuses_a_distribution_at_compile_and_gate() -> None:
    template = _template(
        sine_step("wave", 0.0, 20.0, distribution=[{"domains": ["pan"], "spread_cycles": 0.5}])
    )
    for rig in (physical_rig(), topology_rig(("MH1", "MH2"), position_indexes=None)):
        assert rig_topology(rig) is None
        with pytest.raises(PhysicalCompileError, match="fixture group 'MOVING_HEADS'"):
            _compile(template, rig)
        _compile(_template(sine_step("wave", 0.0, 20.0)), rig)  # no distribution: fine

    document = physical_template_doc("p22_probe", template.model_dump()["steps"])
    with (
        registered_templates(document),
        pytest.raises(UnsupportedRenderModeError, match="fixture group 'MOVING_HEADS'"),
    ):
        check_physical_templates(
            ["p22_probe"],
            beat_grid=_GRID,
            fixture_group=physical_rig(),
            initial_states=physical_job().moving_heads.initial_states,
            failure_mode="error",
        )


def test_topology_must_place_every_fixture_of_the_group_once() -> None:
    ids = _ids(3)
    with pytest.raises(ValidationError, match="MH3"):
        topology_rig(ids, topology=topology_payload(ids[:2]))
    duplicate_id = topology_payload(ids)
    duplicate_id["members"][2]["fixture_id"] = "MH1"
    with pytest.raises(ValidationError, match="fixture"):
        FixtureTopology.model_validate(duplicate_id)
    duplicate_ordinal = topology_payload(ids)
    duplicate_ordinal["members"][2]["ordinal"] = 0
    with pytest.raises(ValidationError, match="ordinal"):
        FixtureTopology.model_validate(duplicate_ordinal)
    # A head the topology declares but the group lacks is a hole, not an error.
    topology_rig(ids[:2], topology=topology_payload(ids))


# --- Legacy, dumps and identity --------------------------------------------------------


def test_absent_topology_and_distribution_are_left_out_of_dumps() -> None:
    rig = physical_rig()
    assert rig.topology is None
    assert "topology" not in rig.model_dump(mode="json")
    assert "topology" in _rig(2).model_dump(mode="json")

    plain = {
        "step_id": "plain",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
        "movement": {
            "physical": {
                "shape": "hold",
                "mode": "periodic",
                "start_pan_deg": 0,
                "start_tilt_deg": 0,
            }
        },
        "dimmer": {},
    }
    assert "physical_distribution" not in TemplateStep.model_validate(plain).model_dump(mode="json")


def _job(ids: tuple[str, ...]) -> JobConfig:
    return physical_job(initial_states=dict.fromkeys(ids, PHYSICAL_INITIAL_STATE))


def test_topology_changes_render_identity_but_not_planning_identity() -> None:
    """Topology is rig data, like presets: it enters the render fingerprint (the group's
    dump) but not the job the session id hashes, nor the fixtures the planner sees."""
    ids = _ids(3)
    document = physical_template_doc("p22_probe", [sine_step("wave", 0.0, 20.0)])
    reordered = topology_payload(ids[::-1])
    rigs = (
        topology_rig(ids, position_indexes=(1, 2, 3)),
        topology_rig(ids, position_indexes=(1, 2, 3), topology=topology_payload(ids)),
        topology_rig(ids, position_indexes=(1, 2, 3), topology=reordered),
    )
    with registered_templates(document):
        fingerprints = {
            RenderingPipeline(
                choreography_plan=physical_sections(("p22_probe", 1, 1)),
                beat_grid=_GRID,
                fixture_group=rig,
                job_config=_job(ids),
            ).fingerprint()
            for rig in rigs
        }
    assert len(fingerprints) == 3
    assert "topology" not in json.dumps(_job(ids).model_dump(mode="json"))
    assert rigs[0].expand_fixtures() == rigs[1].expand_fixtures() == rigs[2].expand_fixtures()


# --- Gate grouping and the render ------------------------------------------------------


def test_plan_key_follows_trajectories_not_rank() -> None:
    """The gate plans heads with identical inputs once. Heads whose phase or pan sign
    changes a trajectory get different keys; heads whose distribution leaves every
    trajectory identical share one, whatever their rank."""
    profile = _rig(4).expand_fixtures()[0].config.physical_profile
    assert profile is not None

    def keys(step: dict[str, Any]) -> tuple[dict[str, FixtureSegment], dict[str, Any]]:
        heads = _by_fixture(_compile(_template(step), _rig(4)))
        return heads, {
            fixture_id: pipeline_module._plan_key([segment], profile, None)
            for fixture_id, segment in heads.items()
        }

    distribution = [{"domains": ["pan"], "spread_cycles": 0.5, "wings": 2}]
    _, swing_keys = keys(sine_step("wave", 0.0, 20.0, distribution=distribution))
    assert swing_keys["MH1"] != swing_keys["MH4"]  # same phase, opposite sign
    assert swing_keys["MH1"] != swing_keys["MH2"]  # same sign, different phase
    assert len(set(swing_keys.values())) == 4

    holding, hold_keys = keys(hold_step("look", 0.0, physical_distribution=distribution))
    assert len({s.metadata["phase_distribution"] for s in holding.values()}) == 4
    assert len(set(hold_keys.values())) == 1


def test_gate_plans_heads_once_unless_their_cues_differ(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = _ids(4)
    planned: dict[str, set[int]] = defaultdict(set)
    real = pipeline_module.plan_prepositions

    def recording(segments: Any, *args: Any, **kwargs: Any) -> Any:
        templates = {segment.template_id for segment in segments}
        planned[templates.pop()].add(len({segment.fixture_id for segment in segments}))
        return real(segments, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "plan_prepositions", recording)
    distribution = [{"domains": ["pan"], "spread_cycles": 0.5}]
    documents = (
        physical_template_doc("p22_plain", [hold_step("look", 0.0)]),
        physical_template_doc(
            "p22_hold", [hold_step("look", 0.0, physical_distribution=distribution)]
        ),
        physical_template_doc(
            "p22_wave", [sine_step("wave", 0.0, 20.0, distribution=distribution)]
        ),
    )
    with registered_templates(*documents):
        check_physical_templates(
            ["p22_plain", "p22_hold", "p22_wave"],
            beat_grid=_GRID,
            fixture_group=_rig(4),
            initial_states=_job(ids).moving_heads.initial_states,
            failure_mode="error",
        )
    # At every placement the gate checks.
    assert planned == {"p22_plain": {1}, "p22_hold": {1}, "p22_wave": {4}}


def test_mirrored_odd_rig_renders_with_a_still_center_and_records_canonical_order() -> None:
    """Three heads in two wings across two sections: the center head's pan never moves
    yet it gets a valid cue; the render plans every head's own phase through the entry
    window and the transaction pass, and the trace keeps canonical order and phases."""
    ids = _ids(3)
    wave = physical_template_doc(
        "p22_wave",
        [
            sine_step(
                "wave",
                0.0,
                20.0,
                distribution=[{"domains": ["pan", "dimmer"], "wings": 2, "spread_cycles": 0.25}],
            )
        ],
    )
    reverse = physical_template_doc(
        "p22_reverse",
        [
            sine_step(
                "reverse",
                -20.0,
                30.0,
                distribution=[{"domains": ["pan"], "spread_cycles": 0.5, "direction": "reverse"}],
            )
        ],
    )
    rig = topology_rig(ids, topology=topology_payload(ids[::-1]))
    with registered_templates(wave, reverse):
        check_physical_templates(
            ["p22_wave", "p22_reverse"],
            beat_grid=_GRID,
            fixture_group=rig,
            initial_states=_job(ids).moving_heads.initial_states,
            failure_mode="error",
        )
        pipeline = RenderingPipeline(
            choreography_plan=physical_sections(("p22_wave", 1, 1), ("p22_reverse", 2, 2)),
            beat_grid=_GRID,
            fixture_group=rig,
            job_config=_job(ids),
        )
        segments = pipeline.render()

    centre = [s for s in segments if s.fixture_id == "MH2" and s.step_id == "wave"]
    assert len(centre) == 1
    assert {value for _, value in _points(centre[0], _PAN)} == {0.0}
    record = pipeline.render_record
    assert record["topology"] == {"source": "declared", "canonical_order": ["MH3", "MH2", "MH1"]}
    phases = {(r["step_id"], r["fixture_id"]): r for r in record["phase_distribution"]}
    assert phases[("wave", "MH3")]["pan_sign"] == -1
    assert phases[("wave", "MH2")]["pan_sign"] == 0
    assert phases[("wave", "MH1")]["offsets"]["dimmer"] == "0"
    assert phases[("reverse", "MH3")]["offsets"]["pan"] == "1/2"
    assert phases[("reverse", "MH1")]["offsets"]["pan"] == "0"


# --- Registry evidence for the new config paths ---------------------------------------

Component = Literal["rejected", "compiled"]

_COMPONENT_NOTES: dict[Component, str] = {
    "rejected": "exact path's alternative is rejected by physical validation or compile",
    "compiled": "exact path changes the physical compile result",
}

Mutation = Callable[[dict[str, Any], dict[str, Any]], Any]
"""Mutates (topology payload holder, step payload) in place."""

_MEMBERS = "fixture.topology.members"
_DISTRIBUTION = "template.template.steps.physical_distribution"


def _member(holder: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    return next(m for m in holder["topology"]["members"] if m["fixture_id"] == fixture_id)


def _swap_ids(holder: dict[str, Any]) -> None:
    first, last = _member(holder, "MH1"), _member(holder, "MH3")
    first["fixture_id"], last["fixture_id"] = "MH3", "MH1"


_MUTATIONS: dict[str, tuple[Component, Mutation]] = {
    "fixture.topology": ("rejected", lambda h, s: h.pop("topology")),
    _MEMBERS: (
        "compiled",
        lambda h, s: h["topology"].update(
            members=topology_payload(("MH3", "MH2", "MH1"))["members"]
        ),
    ),
    f"{_MEMBERS}.fixture_id": ("compiled", lambda h, s: _swap_ids(h)),
    f"{_MEMBERS}.row": ("compiled", lambda h, s: _member(h, "MH1").update(row=1)),
    f"{_MEMBERS}.column": ("compiled", lambda h, s: _member(h, "MH1").update(column=5)),
    f"{_MEMBERS}.ordinal": ("compiled", lambda h, s: _member(h, "MH2").update(ordinal=5)),
    _DISTRIBUTION: ("compiled", lambda h, s: s.pop("physical_distribution")),
    f"{_DISTRIBUTION}.domains": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(domains=["dimmer"]),
    ),
    f"{_DISTRIBUTION}.block_size": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(block_size=2),
    ),
    f"{_DISTRIBUTION}.group_count": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(group_count=2),
    ),
    f"{_DISTRIBUTION}.wings": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(wings=2),
    ),
    f"{_DISTRIBUTION}.spread_cycles": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(spread_cycles=0.25),
    ),
    f"{_DISTRIBUTION}.direction": (
        "compiled",
        lambda h, s: s["physical_distribution"][0].update(direction="reverse"),
    ),
}
"""Per config path: the one component its alternative must change."""

TOPOLOGY_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_topology_field_changes_compile[" in disposition.test_nodeid
)


def _evidence_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    """Three heads, MH2 and MH3 tied on row and column so the ordinal orders them, and a
    sine pan with a dimmer pulse whose pan phase spreads half a cycle."""
    topology = topology_payload(_ids(3))
    topology["members"][2]["column"] = 1
    step = sine_step(
        "wave",
        0.0,
        20.0,
        distribution=[{"domains": ["pan"], "spread_cycles": 0.5}],
        dimmer={"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
    )
    return {"topology": topology}, step


def _compile_snapshot(holder: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    try:
        rig = topology_rig(_ids(3), topology=holder.get("topology"))
        segments = _compile(_template(step), rig)
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": [segment.model_dump(mode="json") for segment in segments]}


def test_topology_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and the mutation table describe the same evidence."""
    assert set(TOPOLOGY_PATHS) == set(_MUTATIONS)
    for path, (component, _) in _MUTATIONS.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", TOPOLOGY_PATHS, ids=TOPOLOGY_PATHS)
def test_topology_field_changes_compile(config_path: str) -> None:
    """Each topology or distribution path changes the one compile component its note
    names, and moves at least one pan, tilt, dimmer or shutter value."""
    component, mutate = _MUTATIONS[config_path]
    holder, step = _evidence_inputs()
    mutate(holder, step)

    base = _compile_snapshot(*_evidence_inputs())
    changed = _compile_snapshot(holder, step)

    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
        return
    assert "rejected" not in changed, changed

    def channels(snapshot: dict[str, Any]) -> list[Any]:
        return [segment["channels"] for segment in snapshot["compiled"]]

    assert channels(changed) != channels(base)
