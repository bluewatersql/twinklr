"""Transition system for template step blending.

Follows established framework patterns:
- Handler/Provider pattern for extensibility
- Registry for handler management
- Dependency injection via context
- Separation of concerns
"""

from blinkb0t.core.domains.sequencing.moving_heads.transitions.context import TransitionContext
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.base import (
    TransitionHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.crossfade import (
    CrossfadeHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.fade_through_black import (
    FadeThroughBlackHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.snap import SnapHandler
from blinkb0t.core.domains.sequencing.moving_heads.transitions.registry import (
    TransitionHandlerRegistry,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.renderer import TransitionRenderer

__all__ = [
    "TransitionRenderer",
    "TransitionHandler",
    "TransitionContext",
    "TransitionHandlerRegistry",
    "CrossfadeHandler",
    "FadeThroughBlackHandler",
    "SnapHandler",
]
