"""Built-in effect handlers for the display renderer."""

from twinklr.core.sequencer.display.effects.handlers.bars_handler import BarsHandler
from twinklr.core.sequencer.display.effects.handlers.butterfly_handler import ButterflyHandler
from twinklr.core.sequencer.display.effects.handlers.chase import ChaseHandler
from twinklr.core.sequencer.display.effects.handlers.circles_handler import CirclesHandler
from twinklr.core.sequencer.display.effects.handlers.color_wash import (
    ColorWashHandler,
)
from twinklr.core.sequencer.display.effects.handlers.fan import FanHandler
from twinklr.core.sequencer.display.effects.handlers.fire import FireHandler
from twinklr.core.sequencer.display.effects.handlers.fireworks_handler import FireworksHandler
from twinklr.core.sequencer.display.effects.handlers.lightning_handler import LightningHandler
from twinklr.core.sequencer.display.effects.handlers.marquee import (
    MarqueeHandler,
)
from twinklr.core.sequencer.display.effects.handlers.meteors import (
    MeteorsHandler,
)
from twinklr.core.sequencer.display.effects.handlers.morph_handler import MorphHandler
from twinklr.core.sequencer.display.effects.handlers.on import OnHandler
from twinklr.core.sequencer.display.effects.handlers.pictures import (
    PicturesHandler,
)
from twinklr.core.sequencer.display.effects.handlers.pinwheel import (
    PinwheelHandler,
)
from twinklr.core.sequencer.display.effects.handlers.ripple import (
    RippleHandler,
)
from twinklr.core.sequencer.display.effects.handlers.shimmer_handler import ShimmerHandler
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
from twinklr.core.sequencer.display.effects.handlers.warp_handler import WarpHandler
from twinklr.core.sequencer.display.effects.handlers.wave_handler import WaveHandler
from twinklr.core.sequencer.display.effects.registry import HandlerRegistry


def load_builtin_handlers() -> HandlerRegistry:
    """Create a HandlerRegistry with all built-in handlers registered.

    Returns:
        HandlerRegistry with all P1+P2+P3 handlers. On is the default
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
    registry.register(RippleHandler())
    registry.register(FireHandler())
    registry.register(PinwheelHandler())

    # P3: Tier 1 expansion handlers
    registry.register(BarsHandler())
    registry.register(ButterflyHandler())
    registry.register(CirclesHandler())
    registry.register(LightningHandler())
    registry.register(MorphHandler())
    registry.register(ShimmerHandler())
    registry.register(WaveHandler())
    registry.register(WarpHandler())
    registry.register(FireworksHandler())

    # On is the fallback for unknown effect types
    registry.set_default(on_handler)

    return registry


__all__ = [
    "BarsHandler",
    "ButterflyHandler",
    "ChaseHandler",
    "CirclesHandler",
    "ColorWashHandler",
    "FanHandler",
    "FireHandler",
    "FireworksHandler",
    "LightningHandler",
    "MarqueeHandler",
    "MeteorsHandler",
    "MorphHandler",
    "OnHandler",
    "PicturesHandler",
    "PinwheelHandler",
    "RippleHandler",
    "ShimmerHandler",
    "ShockwaveHandler",
    "SnowflakesHandler",
    "SpiralsHandler",
    "StrobeHandler",
    "TwinkleHandler",
    "WarpHandler",
    "WaveHandler",
    "load_builtin_handlers",
]
