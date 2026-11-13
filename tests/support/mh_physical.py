"""Synthetic physical-renderer inputs: a fixture profile and a known initial state.

In-memory payloads only; no owner profile or measured data.
"""

from __future__ import annotations

from typing import Any


def profile_payload() -> dict[str, Any]:
    """A synthetic 8-channel spot: 16-bit pan/tilt, dimmer, shutter, color and a spare."""
    return {
        "profile_id": "synthetic_spot",
        "provenance": "synthetic",
        "footprint": 8,
        "defaults": {1: 128, 2: 0, 3: 22, 4: 0, 5: 0, 6: 64, 7: 0, 8: 0},
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


def motion_profile_payload() -> dict[str, Any]:
    """`profile_payload` with configured pan/tilt travel speeds and settled shutter states."""
    payload = profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis]["travel_speed_per_s"] = 720.0
    for state in payload["discrete"]["shutter"]["states"].values():
        state["settle_ms"] = 0
    return payload


def discrete_profile_payload() -> dict[str, Any]:
    """`motion_profile_payload` with the shutter on channel 17 and color and gobo wheels.

    Closed is byte 64 and open byte 8, inside ranges whose bounds are not the selected
    bytes; each wheel has a state between its first and last selected bytes.
    """
    payload = motion_profile_payload()
    payload["footprint"] = 18
    payload["defaults"] = {
        **payload["defaults"],
        **dict.fromkeys(range(9, 17), 0),
        17: 64,
        18: 0,
    }
    payload["discrete"]["shutter"].update(
        offset=17,
        states={
            "closed": {"range_min": 60, "range_max": 95, "value": 64, "settle_ms": 0},
            "open": {"range_min": 0, "range_max": 31, "value": 8, "settle_ms": 0},
        },
    )
    payload["discrete"]["color"]["states"] = {
        "white": {"range_min": 0, "range_max": 9, "value": 0, "settle_ms": 120},
        "red": {"range_min": 10, "range_max": 19, "value": 14, "settle_ms": 120},
        "blue": {"range_min": 20, "range_max": 29, "value": 26, "settle_ms": 140},
    }
    payload["discrete"]["gobo"] = {
        "offset": 18,
        "states": {
            "open": {"range_min": 0, "range_max": 7, "value": 0, "settle_ms": 150},
            "dots": {"range_min": 8, "range_max": 15, "value": 10, "settle_ms": 150},
            "star": {"range_min": 16, "range_max": 23, "value": 20, "settle_ms": 160},
        },
        "default_state": "open",
    }
    return payload


def discrete_step_payload() -> dict[str, Any]:
    """A physical step holding its pose with static shutter, color and gobo states."""
    return {
        "step_id": "look",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "hold",
                "mode": "periodic",
                "start_pan_deg": 0.0,
                "start_tilt_deg": 0.0,
            }
        },
        "dimmer": {},
        "physical_shutter_state": "open",
        "physical_color": "white",
        "physical_gobo": "open",
    }


def physical_step_payload() -> dict[str, Any]:
    """A physical-only template step: finite linear pan/tilt plus dimmer and shutter pulses."""
    return {
        "step_id": "main",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "linear",
                "mode": "finite",
                "start_pan_deg": 10.0,
                "start_tilt_deg": 20.0,
                "pan_extent_deg": 30.0,
                "tilt_extent_deg": 10.0,
                "period_beats": 1.0,
            }
        },
        "dimmer": {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        "physical_shutter": {
            "period_beats": 2.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    }
