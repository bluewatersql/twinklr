"""Template system for moving head choreography.

Provides template loading and validation for multi-step lighting patterns.

Components:
- ResolverRegistry: Movement resolver registry
- GeometryEngine: Geometry transformation engine
- Handlers: Effect handlers
- BoundaryEnforcer: DMX boundary enforcement
- MovementResolver: Base resolver class
"""

from blinkb0t.core.domains.sequencing.moving_heads.templates.context_builder import (
    ResolverContextBuilder,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.factory import TemplateProcessorFactory
from blinkb0t.core.domains.sequencing.moving_heads.templates.loader import (
    TemplateLoader,
    TemplateLoadError,
    TemplateValidationError,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.pipeline import TemplatePipeline
from blinkb0t.core.domains.sequencing.moving_heads.templates.processor import PatternStepProcessor
from blinkb0t.core.domains.sequencing.moving_heads.transitions import (
    CrossfadeHandler,
    FadeThroughBlackHandler,
    SnapHandler,
    TransitionContext,
    TransitionHandler,
    TransitionHandlerRegistry,
    TransitionRenderer,
)

__all__ = [
    "TemplateLoader",
    "TemplateLoadError",
    "TemplateValidationError",
    "PatternStepProcessor",
    "TemplateProcessorFactory",
    "ResolverContextBuilder",
    "TemplatePipeline",
    # Transition system
    "TransitionRenderer",
    "TransitionHandler",
    "TransitionContext",
    "TransitionHandlerRegistry",
    "CrossfadeHandler",
    "FadeThroughBlackHandler",
    "SnapHandler",
]
