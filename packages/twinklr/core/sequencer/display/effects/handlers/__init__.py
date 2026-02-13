"""Built-in effect handlers for the display renderer."""

from twinklr.core.sequencer.display.effects.handlers.chase import ChaseHandler
from twinklr.core.sequencer.display.effects.handlers.color_wash import (
    ColorWashHandler,
)
from twinklr.core.sequencer.display.effects.handlers.fan import FanHandler
from twinklr.core.sequencer.display.effects.handlers.marquee import (
    MarqueeHandler,
)
from twinklr.core.sequencer.display.effects.handlers.meteors import (
    MeteorsHandler,
)
from twinklr.core.sequencer.display.effects.handlers.on import OnHandler
from twinklr.core.sequencer.display.effects.handlers.pictures import (
    PicturesHandler,
)
from twinklr.core.sequencer.display.effects.handlers.shockwave import (
    ShockwaveHandler,
)
from twinklr.core.sequencer.display.effects.handlers.snowflakes import (
    SnowflakesHandler,
)
from twinklr.core.sequencer.display.effects.handlers.spirals import (
    SpiralsHandler,
)
from twinklr.core.sequencer.display.effects.handlers.strobe import (
    StrobeHandler,
)
from twinklr.core.sequencer.display.effects.handlers.twinkle import (
    TwinkleHandler,
)
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry


def load_builtin_handlers() -> HandlerRegistry:
    """Create a HandlerRegistry with all built-in handlers registered.

    Returns:
        HandlerRegistry with all P1+P2 handlers. On is the default
        fallback handler for unknown effect types.
    """
    registry = HandlerRegistry()

    on_handler = OnHandler()

    # P1: Core handlers
    registry.register(on_handler)
    registry.register(ColorWashHandler())
    registry.register(ChaseHandler())
    registry.register(SpiralsHandler())
    registry.register(PicturesHandler())

    # P2: Extended handlers
    registry.register(FanHandler())
    registry.register(ShockwaveHandler())
    registry.register(StrobeHandler())
    registry.register(TwinkleHandler())
    registry.register(SnowflakesHandler())
    registry.register(MarqueeHandler())
    registry.register(MeteorsHandler())

    # On is the fallback for unknown effect types
    registry.set_default(on_handler)

    return registry


__all__ = [
    "ChaseHandler",
    "ColorWashHandler",
    "FanHandler",
    "MarqueeHandler",
    "MeteorsHandler",
    "OnHandler",
    "PicturesHandler",
    "ShockwaveHandler",
    "SnowflakesHandler",
    "SpiralsHandler",
    "StrobeHandler",
    "TwinkleHandler",
    "load_builtin_handlers",
]
