"""Contract tests for the moving-head true-up synthetic cases (P0-T3).

The cases in `tests/support/mh_true_up.py` are shared inputs for later phases, so
their content is pinned exactly here. Cases marked `legacy_runnable` are also run
through the real legacy `RenderingPipeline`; the assertion is only that each one
reaches its recorded baseline outcome deterministically. `physical_inputs` are input
definitions: nothing here claims the physical behavior they describe is implemented.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator, MutableMapping
import io
import itertools
import os
import pathlib

import pytest

from tests.support.mh_true_up import CASE_IDS, SyntheticMHCase, synthetic_case
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    UnsupportedRigShapeError,
)
from twinklr.core.sequencer.moving_heads.handlers.wheels import PLAN_INTENT_CHANNEL_WINDOW_MAX
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates

RUNNABLE_CASE_IDS = ("counts", "fine_carry", "channel_edges", "tempo", "meter3", "finite")


# --- Case catalogue --------------------------------------------------------------


def test_case_ids_are_the_eight_named_cases() -> None:
    assert CASE_IDS == (
        "counts",
        "fine_carry",
        "channel_edges",
        "tempo",
        "meter3",
        "finite",
        "state",
        "locks",
    )


def test_unknown_case_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="no_such_case"):
        synthetic_case("no_such_case")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_case_identity_and_legacy_marking(case_id: str) -> None:
    case = synthetic_case(case_id)

    assert isinstance(case, SyntheticMHCase)
    assert case.case_id == case_id
    assert case.legacy_runnable is (case_id in RUNNABLE_CASE_IDS)
    if case.legacy_runnable:
        assert case.plan is not None
        assert case.template_id is not None
        assert len(case.legacy_outcomes) == len(case.fixture_groups)
        assert [section.template_id for section in case.plan.sections] == [case.template_id]
    else:
        assert case.plan is None
        assert case.template_id is None
        assert case.legacy_outcomes == ()


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_ids_are_unique_and_ordered(case_id: str) -> None:
    for group in synthetic_case(case_id).fixture_groups:
        fixture_ids = [fixture.fixture_id for fixture in group.expand_fixtures()]
        assert fixture_ids == [f"MH{index + 1}" for index in range(len(fixture_ids))]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_physical_inputs_are_plain_values(case_id: str) -> None:
    def plain(value: object) -> bool:
        if isinstance(value, tuple):
            return all(plain(item) for item in value)
        return isinstance(value, bool | int | float | str)

    for key, value in synthetic_case(case_id).physical_inputs.items():
        assert isinstance(key, str)
        assert plain(value), f"{case_id}.{key} is not a plain typed value: {value!r}"


class _NoEnvironment(MutableMapping[str, str]):
    """Stands in for `os.environ`; any access fails the test."""

    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"case construction read environment variable {key!r}")

    def __setitem__(self, key: str, value: str) -> None:
        raise AssertionError(f"case construction set environment variable {key!r}")

    def __delitem__(self, key: str) -> None:
        raise AssertionError(f"case construction deleted environment variable {key!r}")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("case construction enumerated the environment")

    def __len__(self) -> int:
        raise AssertionError("case construction measured the environment")


def test_case_construction_reads_no_environment_or_local_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    for name in ("config.json", "job_config.json", "fixture_config.json"):
        (tmp_path / name).write_text("not json", encoding="utf-8")

    def no_open(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"case construction opened a file: {args!r}")

    with monkeypatch.context() as patch:
        patch.chdir(tmp_path)
        patch.setattr(os, "environ", _NoEnvironment())
        patch.setattr(builtins, "open", no_open)
        patch.setattr(io, "open", no_open)
        patch.setattr(pathlib.Path, "open", no_open)
        cases = [synthetic_case(case_id) for case_id in CASE_IDS]

    assert [case.case_id for case in cases] == list(CASE_IDS)


# --- Per-case content ------------------------------------------------------------


def _fixture_counts(case: SyntheticMHCase) -> list[int]:
    return [len(group.expand_fixtures()) for group in case.fixture_groups]


def test_counts_case_spans_one_to_eight_heads() -> None:
    case = synthetic_case("counts")

    assert _fixture_counts(case) == [1, 2, 3, 4, 6, 8]
    assert case.template_id == "split_lr_sweep_counter"


def test_fine_carry_case_maps_nonadjacent_coarse_and_fine_channels() -> None:
    case = synthetic_case("fine_carry")
    (group,) = case.fixture_groups
    fixtures = group.expand_fixtures()

    assert len(fixtures) == 2
    for fixture in fixtures:
        mapping = fixture.config.dmx_mapping
        assert mapping.use_16bit_pan_tilt is True
        assert mapping.pan_fine is not None and mapping.tilt_fine is not None
        assert abs(mapping.pan_fine - mapping.pan) > 1
        assert abs(mapping.tilt_fine - mapping.tilt) > 1
        channels = [mapping.pan, mapping.pan_fine, mapping.tilt, mapping.tilt_fine, mapping.dimmer]
        assert len(set(channels)) == len(channels)

    plain, inverted = fixtures
    assert (plain.config.inversions.pan, plain.config.inversions.tilt) == (False, False)
    assert (inverted.config.inversions.pan, inverted.config.inversions.tilt) == (True, True)


def test_fine_carry_vectors_cross_the_byte_boundary() -> None:
    inputs = synthetic_case("fine_carry").physical_inputs

    assert inputs["carry_words"] == (255, 256)
    assert inputs["carry_bytes"] == ((0, 255), (1, 0))
    assert inputs["inverted_carry_bytes"] == ((255, 0), (254, 255))
    # The expected bytes are the coarse/fine split of each word, and the inverted
    # bytes are the split of the inverted 16-bit word.
    for word, coarse_fine, inverted in zip(
        inputs["carry_words"], inputs["carry_bytes"], inputs["inverted_carry_bytes"], strict=True
    ):
        assert coarse_fine == divmod(word, 256)
        assert inverted == divmod(0xFFFF - word, 256)


def test_channel_edges_case_places_shutter_intent_above_the_plan_window() -> None:
    case = synthetic_case("channel_edges")
    (group,) = case.fixture_groups

    for fixture in group.expand_fixtures():
        assert fixture.config.dmx_mapping.shutter == 17
    assert PLAN_INTENT_CHANNEL_WINDOW_MAX + 1 == 17
    assert case.plan is not None
    (section,) = case.plan.sections
    assert section.shutter_events, "the shutter channel needs intent to be an edge"
    assert case.physical_inputs["shutter_channel_supported_max"] == 48
    assert case.physical_inputs["shutter_channel_unsupported"] == 49


def test_tempo_case_has_the_exact_changing_grid() -> None:
    grid = synthetic_case("tempo").beat_grid

    assert grid.beat_boundaries == [0, 500, 1000, 1500, 2000, 2400, 2800, 3200, 3600]
    assert grid.bar_boundaries == [0, 2000, 3600]
    assert grid.beats_per_bar == 4
    assert grid.eighth_boundaries[:4] == [0, 250, 500, 750]
    assert grid.eighth_boundaries[8:11] == [2000, 2200, 2400]
    assert grid.sixteenth_boundaries[16:19] == [2000, 2100, 2200]
    assert grid.duration_ms == 3600


def test_meter3_case_has_three_beats_per_bar_at_a_constant_interval() -> None:
    grid = synthetic_case("meter3").beat_grid
    beats = grid.beat_boundaries

    assert grid.beats_per_bar == 3
    assert {later - earlier for earlier, later in itertools.pairwise(beats)} == {500.0}
    assert grid.bar_boundaries == beats[::3]


def test_finite_case_section_is_shorter_than_its_template_cycle() -> None:
    case = synthetic_case("finite")
    assert case.plan is not None and case.template_id is not None
    (section,) = case.plan.sections
    load_builtin_templates()
    template = get_template(case.template_id).template

    section_bars = section.end_bar - section.start_bar + 1
    assert section_bars < template.repeat.cycle_bars
    dimmers = {step.step_id: step.dimmer.dimmer_type for step in template.steps}
    assert dimmers["build"] is DimmerType.FADE_IN
    assert dimmers["recover"] is DimmerType.FADE_OUT
    steps = {step.step_id: step for step in template.steps}
    # The ACCENT_SNAP step fits inside the section once, and the cycle never repeats.
    drop = steps["drop"]
    assert drop.movement.movement_type is MovementType.ACCENT_SNAP
    drop_start = drop.timing.base_timing.start_offset_bars
    assert drop_start + drop.timing.base_timing.duration_bars <= section_bars
    # The FADE_OUT step starts inside the section but ends after it.
    recover = steps["recover"]
    start = recover.timing.base_timing.start_offset_bars
    assert start < section_bars < start + recover.timing.base_timing.duration_bars


def test_state_case_dark_gap_is_too_short_for_the_reposition() -> None:
    inputs = synthetic_case("state").physical_inputs

    assert inputs["initial_pose_known"] is False
    assert inputs["initial_dimmer_known"] is True
    assert inputs["initial_dimmer"] == 0.0
    gap_ms = inputs["dark_gap_end_ms"] - inputs["dark_gap_start_ms"]
    move_deg = abs(inputs["gap_pan_to_deg"] - inputs["gap_pan_from_deg"])
    needed_ms = 1000.0 * move_deg / inputs["synthetic_pan_speed_deg_per_s"]
    assert gap_ms == 100
    assert needed_ms == 500.0
    assert gap_ms < needed_ms


def test_locks_case_changes_intensity_inside_a_motion_lock() -> None:
    inputs = synthetic_case("locks").physical_inputs

    assert inputs["locked_channels"] == ("pan", "tilt")
    lock_start, lock_end = inputs["lock_start_ms"], inputs["lock_end_ms"]
    keyframes = inputs["dimmer_keyframes"]
    assert keyframes == ((0, 0.25), (2000, 1.0), (4000, 0.5))
    assert all(lock_start <= at_ms <= lock_end for at_ms, _ in keyframes)
    assert len({level for _, level in keyframes}) > 1
    assert "dimmer" not in inputs["locked_channels"]


# --- Legacy baseline -------------------------------------------------------------


def _render(case: SyntheticMHCase, group: FixtureGroup) -> list[dict[str, object]]:
    assert case.plan is not None
    pipeline = RenderingPipeline(
        choreography_plan=case.plan,
        beat_grid=case.beat_grid,
        fixture_group=group,
        job_config=JobConfig(),
    )
    return [segment.model_dump(mode="json") for segment in pipeline.render()]


def test_counts_baseline_rejects_one_head_and_renders_the_rest() -> None:
    case = synthetic_case("counts")

    assert dict(zip(_fixture_counts(case), case.legacy_outcomes, strict=True)) == {
        1: "unsupported_rig_shape",
        2: "rendered",
        3: "rendered",
        4: "rendered",
        6: "rendered",
        8: "rendered",
    }


@pytest.mark.parametrize("case_id", RUNNABLE_CASE_IDS)
def test_legacy_runnable_case_reaches_its_baseline_deterministically(case_id: str) -> None:
    first = synthetic_case(case_id)
    second = synthetic_case(case_id)

    for index, outcome in enumerate(first.legacy_outcomes):
        if outcome == "unsupported_rig_shape":
            for case in (first, second):
                with pytest.raises(UnsupportedRigShapeError, match=first.template_id):
                    _render(case, case.fixture_groups[index])
            continue

        assert outcome == "rendered"
        rendered = _render(first, first.fixture_groups[index])
        assert rendered, f"{case_id}[{index}] rendered no segments"
        assert rendered == _render(second, second.fixture_groups[index])
