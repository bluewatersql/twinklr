"""Effect handler system for pluggable movement patterns.

This module provides a registry-based handler system for movement patterns,
enabling modular, testable effect implementations.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.base import (
    EffectHandler,
    SequencerContext,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)

__all__ = [
    "EffectHandler",
    "SequencerContext",
    "DefaultMovementHandler",
]
