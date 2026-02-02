"""Asset template package initialization.

Provides auto-discovery of builtin templates and exports public API.
"""

from __future__ import annotations

from twinklr.core.sequencer.templates.assets.library import (
    REGISTRY,
    get_asset_template,
    list_asset_templates,
)

__all__ = ["REGISTRY", "get_asset_template", "list_asset_templates", "load_builtin_asset_templates"]

_loaded = False


def load_builtin_asset_templates() -> None:
    """Load builtin asset templates via auto-discovery.

    Importing the builtins package triggers @register_asset_template
    decorator side effects, registering all templates.

    This function is idempotent - calling multiple times is safe.
    """
    global _loaded
    if _loaded:
        return

    # Importing triggers @register_asset_template decorators
    from twinklr.core.sequencer.templates.assets import builtins as _  # noqa: F401

    _loaded = True
