"""Unit tests for the plan's categorical section transition."""

from pydantic import ValidationError
import pytest

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import TransitionMode
from twinklr.core.sequencer.models.transition import (
    ChannelTransition,
    PlanTransition,
    TransitionChannel,
    TransitionEdge,
    TransitionLength,
    TransitionSplit,
    TransitionStrategy,
)


def test_all_strategies_defined() -> None:
    assert TransitionStrategy.SNAP == "snap"
    assert TransitionStrategy.SMOOTH_INTERPOLATION == "smooth"
    assert TransitionStrategy.CROSSFADE == "crossfade"
    assert TransitionStrategy.FADE_VIA_BLACK == "fade_via_black"
    assert TransitionStrategy.SEQUENCE == "sequence"


def test_modes_keep_the_old_set_and_add_blackout() -> None:
    assert {mode.value for mode in TransitionMode} == {
        "snap",
        "crossfade",
        "morph",
        "fade_via_black",
        "sweep",
        "blackout",
    }


def test_lengths_span_a_beat_to_eight_bars() -> None:
    assert [length.value for length in TransitionLength] == [
        "BEAT",
        "HALF_BAR",
        "BAR",
        "ONE_AND_HALF_BARS",
        "TWO_BARS",
        "THREE_BARS",
        "FOUR_BARS",
        "SIX_BARS",
        "EIGHT_BARS",
    ]


def test_splits_name_the_fade_out_share_from_a_quarter_to_three_quarters() -> None:
    assert [split.value for split in TransitionSplit] == [
        "QUARTER",
        "THIRD",
        "HALF",
        "TWO_THIRDS",
        "THREE_QUARTERS",
    ]


def _transition(**fields: object) -> PlanTransition:
    return PlanTransition.model_validate(
        {
            "edge": "ENTRY",
            "mode": "crossfade",
            "length": "BAR",
            "curve": "linear",
            "split": "QUARTER",
            "channels": [],
            **fields,
        }
    )


def test_a_crossfade_with_channel_strategies() -> None:
    transition = _transition(
        channels=[
            {"channel": "dimmer", "strategy": "fade_via_black"},
            {"channel": "color", "strategy": "snap"},
        ]
    )

    assert transition.edge is TransitionEdge.ENTRY
    assert transition.mode is TransitionMode.CROSSFADE
    assert transition.curve is CurveLibrary.LINEAR
    assert transition.split is TransitionSplit.QUARTER
    assert transition.channels == [
        ChannelTransition(
            channel=TransitionChannel.DIMMER, strategy=TransitionStrategy.FADE_VIA_BLACK
        ),
        ChannelTransition(channel=TransitionChannel.COLOR, strategy=TransitionStrategy.SNAP),
    ]
    assert transition.describe() == (
        "crossfade over BAR, curve linear, split QUARTER; dimmer fade_via_black, color snap"
    )


def test_every_channel_may_have_its_own_strategy_once() -> None:
    every = [{"channel": channel.value, "strategy": "snap"} for channel in TransitionChannel]

    assert len(_transition(channels=every).channels) == 6
    with pytest.raises(ValidationError, match="at most once"):
        _transition(channels=[*every[:1], *every[:1]])
