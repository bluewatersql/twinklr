from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from twinklr.core.sequencer.models.template import TemplateDoc

logger = logging.getLogger(__name__)


class TemplateNotFoundError(KeyError):
    pass


def _norm_key(s: str) -> str:
    """Normalize user-provided keys (id/name/alias) to a stable lookup key."""
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_")


@dataclass(frozen=True)
class TemplateInfo:
    """Lightweight metadata for listing/search without materializing new instances."""

    template_id: str
    version: int
    name: str
    category: Any  # keep Any if Category enum lives elsewhere
    tags: tuple[str, ...]


class TemplateRegistry:
    """
    Registry stores factories so callers always get a fresh Template instance.

    Factories return Template objects (Pydantic models).
    """

    def __init__(self) -> None:
        self._factories_by_id: dict[str, Callable[[], TemplateDoc]] = {}
        self._aliases: dict[str, str] = {}  # alias_key -> template_id
        self._info_by_id: dict[str, TemplateInfo] = {}

    def register(
        self,
        factory: Callable[[], TemplateDoc],
        *,
        template_id: str | None = None,
        aliases: Iterable[str] = (),
    ) -> None:
        t = factory()  # materialize once for validation + metadata
        tid = template_id or t.template.template_id

        if not t.enabled:
            logger.warning(f"Template {tid} is disabled, skipping registration")
            return

        if tid in self._factories_by_id:
            raise ValueError(f"Template already registered: {tid}")

        self._factories_by_id[tid] = factory

        # Add default aliases: id and display name
        all_aliases = {tid, t.template.name, *aliases}
        for a in all_aliases:
            self._aliases[_norm_key(a)] = tid

        # Store lightweight info for list/search
        tags = tuple(getattr(t.template.metadata, "tags", []) or [])

        self._info_by_id[tid] = TemplateInfo(
            template_id=tid,
            version=t.template.version,
            name=t.template.name,
            category=t.template.category,
            tags=tags,
        )

    def get(self, key: str, *, deep_copy: bool = True) -> TemplateDoc:
        """
        Lookup by template_id OR name/alias (case/format insensitive).

        deep_copy=True ensures no shared state between callers.
        """
        tid = self._aliases.get(_norm_key(key), key)
        factory = self._factories_by_id.get(tid)
        if not factory:
            raise TemplateNotFoundError(f"Unknown template: {key}")

        t = factory()

        return t.model_copy(deep=True) if deep_copy else t

    def list_all(self) -> list[TemplateInfo]:
        """List all registered templates sorted by category and name."""
        return sorted(self._info_by_id.values(), key=lambda x: (x.category, x.name))

    def find(
        self,
        *,
        category: Any | None = None,
        has_tag: str | None = None,
        name_contains: str | None = None,
    ) -> list[TemplateInfo]:
        tag_key = has_tag.lower() if has_tag else None
        name_key = name_contains.lower() if name_contains else None

        out: list[TemplateInfo] = []
        for info in self._info_by_id.values():
            if category is not None and info.category != category:
                continue
            if tag_key is not None and tag_key not in {t.lower() for t in info.tags}:
                continue
            if name_key is not None and name_key not in info.name.lower():
                continue
            out.append(info)

        return sorted(out, key=lambda x: (x.category, x.name))


# Global registry instance (simple + ergonomic)
REGISTRY = TemplateRegistry()


def register_template(*, aliases: Iterable[str] = ()):
    """
    Decorator for registering template factory functions.

    Usage:
        @register_template(aliases=["Bounce Fan Pulse"])
        def make_template() -> TemplateDoc: ...
    """

    def deco(fn: Callable[[], TemplateDoc]) -> Callable[[], TemplateDoc]:
        # factory is fn; use fn() to pull template_id/name/etc
        REGISTRY.register(fn, aliases=aliases)
        return fn

    return deco


def get_template(key: str) -> TemplateDoc:
    return REGISTRY.get(key)


def list_templates() -> list[TemplateInfo]:
    return REGISTRY.list_all()
