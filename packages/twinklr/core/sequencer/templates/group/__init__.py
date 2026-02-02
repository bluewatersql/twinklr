"""Group template package initialization.

Provides auto-discovery of builtin templates and exports public API.
"""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.library import (
    REGISTRY,
    get_group_template,
    list_group_templates,
)

__all__ = ["REGISTRY", "get_group_template", "list_group_templates", "load_builtin_group_templates"]

_loaded = False


def load_builtin_group_templates() -> None:
    """Load builtin group templates via auto-discovery.

    Importing the builtins package triggers @register_group_template
    decorator side effects, registering all templates.

    This function is idempotent - calling multiple times is safe.
    """
    global _loaded
    if _loaded:
        return

    # Importing triggers @register_group_template decorators
    from twinklr.core.sequencer.templates.group import builtins as _  # noqa: F401

    _loaded = True
