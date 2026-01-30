# twinklr/core/domains/sequencer/moving_heads/templates/__init__.py
from __future__ import annotations

from twinklr.core.sequencer.moving_heads.templates.library import (
    REGISTRY,
    get_template,
    list_templates,
)

all = [REGISTRY, get_template, list_templates]

_loaded = False


def load_builtin_templates() -> None:
    global _loaded
    if _loaded:
        return

    # Importing registers builtins
    from twinklr.core.sequencer.moving_heads.templates import builtins as _builtins  # noqa: F401

    _loaded = True
