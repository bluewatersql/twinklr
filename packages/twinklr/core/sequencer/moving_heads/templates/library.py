from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import Any

from twinklr.core.sequencer.models.template import Template, TemplateDoc

logger = logging.getLogger(__name__)

_EPSILON_BARS = 1e-9


class TemplateNotFoundError(KeyError):
    pass


class InvalidTemplateError(ValueError):
    """A template's repeat contract does not describe a renderable cycle."""


def validate_repeat_contract(template: Template) -> None:
    """Reject repeat contracts the scheduler cannot honor.

    Two families of defect shipped undetected because nothing checked the contract
    against the steps it names:

    - a step defined on the template but absent from ``loop_step_ids`` is never
      scheduled, so the whole arc of a narrative template was dead data (P4-F5);
    - loop steps whose placements run past ``cycle_bars`` schedule more bars than
      the cycle claims, and the section overruns (P4-F6).

    The cycle span is ``max(start_offset_bars + duration_bars)``, not the sum of the
    durations: steps that target disjoint fixture groups run at the same time.

    Args:
        template: The template to check.

    Raises:
        InvalidTemplateError: If the contract is unrenderable.
    """
    # `Template` already rejects a loop_step_id with no matching step, so the only
    # direction left to check is the other one.
    step_ids = [step.step_id for step in template.steps]
    loop_step_ids = list(template.repeat.loop_step_ids)

    unreachable = [step_id for step_id in step_ids if step_id not in loop_step_ids]
    if unreachable:
        raise InvalidTemplateError(
            f"template '{template.template_id}': steps {unreachable} are declared but "
            "absent from loop_step_ids, so they would never be scheduled"
        )

    if not loop_step_ids:
        return

    placements = {
        step.step_id: (
            step.timing.base_timing.start_offset_bars,
            step.timing.base_timing.duration_bars,
        )
        for step in template.steps
        if step.step_id in loop_step_ids
    }
    cycle_bars = template.repeat.cycle_bars
    span = max(offset + duration for offset, duration in placements.values())

    if abs(span - cycle_bars) > _EPSILON_BARS:
        raise InvalidTemplateError(
            f"template '{template.template_id}': loop steps span {span} bars "
            f"(max start_offset_bars + duration_bars) but cycle_bars is {cycle_bars}; "
            "the cycle must be exactly the span its steps occupy"
        )


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

        validate_repeat_contract(t.template)

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
