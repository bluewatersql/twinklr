"""Effect handler protocol and result models.

Defines the EffectHandler protocol that all effect handlers must
implement, along with the EffectSettings result model and
RenderContext for handler dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.display.models.render_event import RenderEvent


class EffectSettings(BaseModel):
    """Result of an EffectHandler's build_settings call.

    Contains the xLights EffectDB settings string and metadata
    about the rendering.

    Attributes:
        settings_string: Comma-separated EffectDB settings (E_/B_/T_ keys).
        effect_name: xLights effect type name for the <Effect> tag.
        requires_assets: List of asset paths this effect depends on.
        warnings: Non-fatal warnings from rendering.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_string: str = Field(description="xLights EffectDB settings string")
    effect_name: str = Field(description="xLights effect type name")
    requires_assets: list[str] = Field(
        default_factory=list,
        description="Asset paths required by this effect",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal rendering warnings",
    )


class RenderContext(BaseModel):
    """Context provided to EffectHandlers during rendering.

    Contains global rendering state and configuration needed by
    handlers to produce correct settings strings.

    Attributes:
        sequence_duration_ms: Total sequence duration.
        asset_base_path: Base directory for image/video assets.
        default_buffer_style: Default buffer style for effects.
        frame_interval_ms: xLights timing grid interval.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence_duration_ms: int = Field(ge=0, description="Sequence duration in ms")
    asset_base_path: Path = Field(
        default=Path("."),
        description="Base directory for assets",
    )
    default_buffer_style: str = Field(
        default="Per Model Default",
        description="Default xLights buffer style",
    )
    frame_interval_ms: int = Field(
        default=20,
        ge=10,
        description="xLights timing grid interval in ms",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for specialized handlers",
    )


@runtime_checkable
class EffectHandler(Protocol):
    """Protocol for xLights effect handlers.

    Each handler is responsible for one xLights effect type. It
    translates a RenderEvent (with normalized parameters) into
    an xLights EffectDB settings string.
    """

    @property
    def effect_type(self) -> str:
        """xLights effect type name this handler produces."""
        ...

    @property
    def handler_version(self) -> str:
        """Handler version string for deterministic output tracking."""
        ...

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build xLights EffectDB settings for a render event.

        Args:
            event: The render event to process.
            ctx: Rendering context with global state.

        Returns:
            EffectSettings with the settings string and metadata.
        """
        ...


__all__ = [
    "EffectHandler",
    "EffectSettings",
    "RenderContext",
]
