"""Pictures effect handler.

Displays image assets on models — the primary effect for showing
cutouts, textures, and generated imagery from the asset pipeline.
"""

from __future__ import annotations

from pathlib import Path

from twinklr.core.sequencer.display.effects.protocol import (
    EffectSettings,
    RenderContext,
)
from twinklr.core.sequencer.display.effects.settings_builder import (
    SettingsStringBuilder,
)
from twinklr.core.sequencer.display.models.render_event import RenderEvent


class PicturesHandler:
    """Handler for the xLights 'Pictures' effect.

    Displays an image file on the model. Supports:
    - File path specification
    - Movement direction and speed
    - Scaling mode
    """

    @property
    def effect_type(self) -> str:
        return "Pictures"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Pictures effect settings.

        Supported parameters in event.parameters:
            - filename: str (image file path, relative to asset_base_path)
            - movement: str (default "none")
              Options: "none", "left", "right", "up", "down",
                       "peekaboo", "wiggle", "zoom in", "zoom out"
            - speed: int (0-100, default 10)
            - frame_rate: int (1-60, default 10)
            - scale_to_fit: bool (default True)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Pictures settings string.
        """
        params = event.parameters

        filename = params.get("filename", "")
        movement = params.get("movement", "none")
        speed = params.get("speed", 10)
        frame_rate = params.get("frame_rate", 10)
        scale_to_fit = params.get("scale_to_fit", True)

        # Resolve file path relative to asset base
        if filename and not Path(filename).is_absolute():
            resolved = str(ctx.asset_base_path / filename)
        else:
            resolved = filename

        warnings: list[str] = []
        requires_assets: list[str] = []

        if resolved:
            requires_assets.append(resolved)
            if not Path(resolved).exists():
                warnings.append(f"Asset file not found: {resolved}")

        builder = SettingsStringBuilder()
        builder.add("E_FILEPICKER_Pictures_Filename", resolved)
        builder.add("E_CHOICE_Pictures_Direction", movement)
        builder.add("E_SLIDER_Pictures_Speed", speed)
        builder.add("E_SLIDER_Pictures_FrameRateAdj", frame_rate)
        builder.add(
            "E_CHECKBOX_Pictures_ScaleToFit", 1 if scale_to_fit else 0
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Pictures",
            requires_assets=requires_assets,
            warnings=warnings,
        )


__all__ = ["PicturesHandler"]
