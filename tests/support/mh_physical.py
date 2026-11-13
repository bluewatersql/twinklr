"""Synthetic physical-renderer inputs: a fixture profile, a known initial state and
physical fixture segments.

In-memory payloads only; no owner profile or measured data.
"""

from __future__ import annotations

from typing import Any

from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import PhysicalValue
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment


def physical_segment(
    channels: dict[ChannelName, PhysicalValue],
    *,
    t0_ms: int,
    t1_ms: int,
    fixture_id: str = "MH1",
    segment_id: str = "seg",
) -> FixtureSegment:
    """A fixture segment whose channels hold only typed physical values."""
    return FixtureSegment(
        section_id="section",
        segment_id=segment_id,
        step_id="step",
        template_id="template",
        fixture_id=fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        channels={
            name: ChannelValue(channel=name, physical=value) for name, value in channels.items()
        },
    )


def profile_payload() -> dict[str, Any]:
    """A synthetic 8-channel spot: 16-bit pan/tilt, dimmer, shutter, color and a spare."""
    return {
        "profile_id": "synthetic_spot",
        "provenance": "synthetic",
        "footprint": 8,
        "defaults": {1: 128, 2: 0, 3: 128, 4: 0, 5: 0, 6: 64, 7: 0, 8: 0},
        "axes": {
            "pan": {
                "unit": "degree",
                "physical_min": -270.0,
                "physical_max": 270.0,
                "coarse_offset": 1,
                "fine_offset": 2,
            },
            "tilt": {
                "unit": "degree",
                "physical_min": -135.0,
                "physical_max": 135.0,
                "coarse_offset": 3,
                "fine_offset": 4,
            },
            "dimmer": {
                "unit": "normalized",
                "physical_min": 0.0,
                "physical_max": 1.0,
                "coarse_offset": 5,
            },
        },
        "discrete": {
            "shutter": {
                "offset": 6,
                "states": {
                    "closed": {"range_min": 64, "range_max": 95, "value": 64},
                    "open": {"range_min": 0, "range_max": 31, "value": 8},
                },
                "default_state": "closed",
                "closed_state": "closed",
                "open_state": "open",
            },
            "color": {
                "offset": 7,
                "states": {
                    "white": {"range_min": 0, "range_max": 9, "value": 0},
                    "red": {"range_min": 10, "range_max": 19, "value": 14},
                },
                "default_state": "white",
            },
        },
        "visibility": {
            "dimmer_zero_extinguishes": True,
            "extinguishing_shutter_states": ["closed"],
            "close_latency_ms": 0,
            "open_latency_ms": 0,
        },
    }


def initial_state_payload() -> dict[str, Any]:
    """A known, settled, dark time-zero state the profile above accepts."""
    return {
        "pan_deg": 0.0,
        "tilt_deg": 0.0,
        "dimmer": 0.0,
        "discrete_states": {"shutter": "closed", "color": "red"},
        "settled": True,
        "dark": True,
    }
