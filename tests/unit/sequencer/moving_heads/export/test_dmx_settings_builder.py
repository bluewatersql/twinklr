"""Unit tests for the channel-default policy in `DmxSettingsBuilder` (P1P-T6).

These pin the emit-loop policy directly, at the `FixtureSegment` -> settings-string
level, without going through the full rendering pipeline the golden suite exercises.
See `tests/golden/test_settings_golden.py` and `tests/golden/test_shutter_channel_emission.py`
for the end-to-end pins of the same behavior.
"""

from __future__ import annotations

import pytest

from twinklr.core.config.fixtures.dmx import ChannelInversions, DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder


def _fixture(dmx_mapping: DmxMapping) -> FixtureInstance:
    config = FixtureConfig(fixture_id="MH1", dmx_mapping=dmx_mapping)
    return FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")


def _segment(channels: dict[ChannelName, ChannelValue]) -> FixtureSegment:
    return FixtureSegment(
        section_id="s",
        segment_id="seg",
        step_id="step",
        template_id="tmpl",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=1000,
        channels=channels,
    )


def _pan_tilt_dimmer(
    extra: dict[ChannelName, ChannelValue] | None = None,
) -> dict[ChannelName, ChannelValue]:
    channels = {
        ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=100),
        ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=100),
        ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
    }
    channels.update(extra or {})
    return channels


def _sliders(settings: str) -> dict[int, int]:
    return {
        int(part.removeprefix("E_SLIDER_DMX").split("=")[0]): int(part.split("=")[1])
        for part in settings.split(",")
        if part.startswith("E_SLIDER_DMX")
    }


def test_mapped_unwritten_shutter_emits_declared_default() -> None:
    """The headline: an unwritten but mapped shutter emits 255, not 0."""
    mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15, shutter_channel=6)
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(_pan_tilt_dimmer())

    sliders = _sliders(builder.build_settings_string(segment))

    assert sliders[6] == 255


def test_unmapped_channel_is_omitted() -> None:
    """No `E_SLIDER_DMX<n>=0` token for a channel the fixture does not map."""
    mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15)
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(_pan_tilt_dimmer())

    settings = builder.build_settings_string(segment)
    sliders = _sliders(settings)

    # get_max_channel(mapping) == 15 here (max of 11/13/15), so channel 16 -- never
    # declared by this mapping at all -- must not appear.
    assert 16 not in sliders
    assert "E_SLIDER_DMX16=" not in settings


@pytest.mark.parametrize(
    ("shutter_channel", "color_channel", "expected_max"),
    [
        (None, None, 15),  # mh4_minimal-shaped: pan/tilt/dimmer only
        (6, 7, 15),  # mh4_shutter_in_window-shaped: below dimmer
        (17, 18, 18),  # mh4_shutter_out_of_window-shaped: above the old floor-16
    ],
)
def test_window_derived_from_get_max_channel(
    shutter_channel: int | None, color_channel: int | None, expected_max: int
) -> None:
    """The emitted E_SLIDER_DMX window matches `get_max_channel`, not floor-16."""
    mapping = DmxMapping(
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=shutter_channel,
        color_channel=color_channel,
    )
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(_pan_tilt_dimmer())

    sliders = _sliders(builder.build_settings_string(segment))

    assert max(sliders) == expected_max


def test_written_channels_unchanged() -> None:
    """PAN/TILT/DIMMER resolution is untouched by the default policy."""
    mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15, shutter_channel=6)
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(
        {
            ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=77),
            ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=88),
            ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
        }
    )

    sliders = _sliders(builder.build_settings_string(segment))

    assert sliders[11] == 77
    assert sliders[13] == 88
    assert sliders[15] == 200


def test_inversions_and_16bit_flag_change_emitted_settings() -> None:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        pan_fine_channel=4,
        tilt_fine_channel=5,
        use_16bit_pan_tilt=True,
        shutter_channel=6,
        color_channel=7,
        gobo_channel=8,
    )
    config = FixtureConfig(
        fixture_id="MH1",
        dmx_mapping=mapping,
        inversions=ChannelInversions(
            pan=True,
            tilt=True,
            dimmer=True,
            shutter=True,
            color=True,
            gobo=True,
        ),
    )
    fixture = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")

    settings = DmxSettingsBuilder(fixture).build_settings_string(_segment(_pan_tilt_dimmer()))

    assert all(f"E_CHECKBOX_INVDMX{channel}=1" in settings for channel in range(1, 9))


def test_color_gobo_defaults_from_fixture_map() -> None:
    """Mapped-but-unwritten colour/gobo emit their fixture map's configured
    `"open"` value, not 0 as a coincidence and not an invented constant."""
    mapping = DmxMapping(
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        color_channel=7,
        gobo_channel=8,
        color_map={"open": 5, "red": 20},
        gobo_map={"open": 9, "gobo1": 30},
    )
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(_pan_tilt_dimmer())

    sliders = _sliders(builder.build_settings_string(segment))

    assert sliders[7] == 5
    assert sliders[8] == 9


def test_written_shutter_overrides_the_declared_default() -> None:
    """A shutter the renderer *did* write to keeps its written value (item 1 wins
    over item 2 -- the default only applies when the renderer wrote nothing)."""
    mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15, shutter_channel=6)
    builder = DmxSettingsBuilder(_fixture(mapping))
    segment = _segment(
        _pan_tilt_dimmer(
            {ChannelName.SHUTTER: ChannelValue(channel=ChannelName.SHUTTER, static_dmx=64)}
        )
    )

    sliders = _sliders(builder.build_settings_string(segment))

    assert sliders[6] == 64


def test_channel_defaults_wired_or_absent() -> None:
    """`ChannelDefaults` / `JobConfig.is_channel_enabled` are gone, not dead code.

    P1P-T6 deleted them rather than wiring them: the rig config's
    `DmxMapping.shutter_default`/`color_map`/`gobo_map` already express the same
    "declared default" concept at the layer the exporter reads (see the note left
    at their old location in `config/models.py`).
    """
    import twinklr.core.config.models as config_models

    assert not hasattr(config_models, "ChannelDefaults")
    assert not hasattr(config_models.JobConfig, "is_channel_enabled")
    assert "channel_defaults" not in config_models.JobConfig.model_fields
