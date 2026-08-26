"""Behavioral contracts for the public template phase-offset fields."""

from twinklr.core.sequencer.models.template import PhaseOffset, PhaseOffsetMode
from twinklr.core.sequencer.moving_heads.compile.phase_offset import calculate_fixture_offsets


def test_phase_offset_fields_change_calculated_schedule() -> None:
    fixture_ids = ["MH1", "MH2", "MH3"]

    disabled = calculate_fixture_offsets(
        PhaseOffset(mode=PhaseOffsetMode.NONE, spread_bars=2.0, wrap=True), fixture_ids
    )
    enabled = calculate_fixture_offsets(
        PhaseOffset(mode=PhaseOffsetMode.GROUP_ORDER, spread_bars=2.0, wrap=False), fixture_ids
    )
    narrower = calculate_fixture_offsets(
        PhaseOffset(mode=PhaseOffsetMode.GROUP_ORDER, spread_bars=1.0, wrap=False), fixture_ids
    )

    assert disabled.offsets == {"MH1": 0.0, "MH2": 0.0, "MH3": 0.0}
    assert enabled.offsets == {"MH1": 0.0, "MH2": 1.0, "MH3": 2.0}
    assert narrower.offsets == {"MH1": 0.0, "MH2": 0.5, "MH3": 1.0}
    assert disabled.wrap is True
    assert enabled.wrap is False
