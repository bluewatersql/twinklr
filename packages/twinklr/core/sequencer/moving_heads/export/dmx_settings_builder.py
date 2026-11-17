"""DMX settings string builder for xLights EffectDB entries.

Builds the constant DMX effect settings string for one encoded physical frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame

from twinklr.core.config.fixtures.capabilities import MAX_DMX_EFFECT_CHANNELS
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.moving_heads.export.frame_encoder import PhysicalOutputError


class DmxSettingsBuilder:
    """Builds xLights DMX effect settings strings from encoded physical frames."""

    @staticmethod
    def build_frame_settings(frame: EncodedFixtureFrame) -> str:
        """Build a constant DMX effect settings string for one complete physical frame.

        Writes every channel 1..n explicitly, so nothing falls back to xLights' zero
        for an absent channel, and sets no inversion flag: the physical encoder has
        already applied inversion to the bytes. No value curve is written.

        Raises:
            PhysicalOutputError: If the frame's channels are not exactly 1..n, n <= 48.
            ValueError: If a channel's value is not a DMX byte.
        """
        offsets = [offset for offset, _ in frame.channels]
        if (
            not offsets
            or offsets != list(range(1, len(offsets) + 1))
            or len(offsets) > MAX_DMX_EFFECT_CHANNELS
        ):
            raise PhysicalOutputError(
                MHDiagnostic(
                    code="unsupported_backend_channel",
                    severity="error",
                    message=(
                        f"{frame.fixture_id} frame at {frame.time_ms} ms has channels "
                        f"{offsets}; a DMX effect takes exactly channels 1..n, n <= "
                        f"{MAX_DMX_EFFECT_CHANNELS}"
                    ),
                    fixture_id=frame.fixture_id,
                    action="rejected",
                )
            )
        for offset, value in frame.channels:
            if not 0 <= value <= 255:
                raise ValueError(f"channel {offset} value {value} is not a DMX byte")

        parts = ["B_CHOICE_BufferStyle=Per Model Default"]
        parts += [f"E_CHECKBOX_INVDMX{offset}=0" for offset in offsets]
        parts.append("E_NOTEBOOK1=Channels 1-16")
        parts += [f"E_SLIDER_DMX{offset}={value}" for offset, value in frame.channels]
        return ",".join(parts)
