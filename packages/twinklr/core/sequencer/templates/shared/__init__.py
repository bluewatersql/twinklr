"""Shared template infrastructure.

Provides generic registry infrastructure used by both
group and asset template systems.

NOTE: Theming and timing models have moved to:
- twinklr.core.sequencer.theming
- twinklr.core.sequencer.timing
- twinklr.core.sequencer.vocabulary
"""

from twinklr.core.sequencer.templates.shared.registry import (
    BaseTemplateInfo,
    TemplateNotFoundError,
    TemplateProtocol,
    TemplateRegistry,
    normalize_key,
)

__all__ = [
    "BaseTemplateInfo",
    "TemplateNotFoundError",
    "TemplateProtocol",
    "TemplateRegistry",
    "normalize_key",
]
