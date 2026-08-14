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
    """A template document does not describe a renderable, searchable template."""


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

    # Multi-step timing must cover the cycle without a hole. Overlap remains valid:
    # multiple steps can deliberately run in parallel against the same or disjoint
    # fixture groups, as pinned by the original repeat-contract tests.
    if len(loop_step_ids) > 1:
        intervals: list[tuple[float, float, str]] = []
        for step in template.steps:
            if step.step_id not in loop_step_ids:
                continue
            timing = step.timing.base_timing
            intervals.append(
                (
                    timing.start_offset_bars,
                    timing.start_offset_bars + timing.duration_bars,
                    step.step_id,
                )
            )

        cursor = 0.0
        for start, end, step_id in sorted(intervals):
            if start > cursor + _EPSILON_BARS:
                raise InvalidTemplateError(
                    f"template '{template.template_id}': loop schedule has an unscheduled "
                    f"gap from {cursor} to {start} bars before step '{step_id}'"
                )
            cursor = max(cursor, end)


def validate_template_document(document: TemplateDoc) -> None:
    """Lint source-independent template properties required by selection/rendering.

    Registration calls this function for both Python factories and data documents,
    so neither source can bypass the repeat-contract checks or the annotations used
    by deterministic template selection.
    """
    template = document.template
    validate_repeat_contract(template)

    metadata = template.metadata
    if metadata is None or metadata.energy_range is None:
        raise InvalidTemplateError(
            f"template '{template.template_id}': metadata.energy_range is required"
        )
    minimum, maximum = metadata.energy_range
    if minimum > maximum:
        raise InvalidTemplateError(
            f"template '{template.template_id}': metadata.energy_range must be ordered "
            f"(got {minimum}, {maximum})"
        )
    if not metadata.recommended_sections:
        raise InvalidTemplateError(
            f"template '{template.template_id}': metadata.recommended_sections must not be empty"
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
        self._source_by_id: dict[str, str] = {}

    def register(
        self,
        factory: Callable[[], TemplateDoc],
        *,
        template_id: str | None = None,
        aliases: Iterable[str] = (),
        source: str = "python",
        allow_override: bool = False,
    ) -> bool:
        t = factory()  # materialize once for validation + metadata
        tid = template_id or t.template.template_id

        # Disabled templates are skipped only after proving they are otherwise valid.
        # A disabled flag is not an escape hatch around the source-independent linter:
        # invalid dormant data tends to become a production failure when re-enabled.
        validate_template_document(t)

        if not t.enabled:
            logger.warning(f"Template {tid} is disabled, skipping registration")
            return False

        alias_keys = {_norm_key(alias) for alias in (tid, t.template.name, *aliases)}
        if "" in alias_keys:
            raise ValueError(
                f"Template {tid!r} has an empty normalized alias (new source={source})"
            )

        exact_incumbent = tid if tid in self._factories_by_id else None
        if exact_incumbent is not None and not allow_override:
            raise self._collision_error(
                normalized_key=_norm_key(tid),
                incumbent_id=exact_incumbent,
                new_id=tid,
                new_source=source,
            )

        # Preflight *every* normalized lookup key before mutating any registry map.
        # An override may reuse keys owned by its exact incumbent and nothing else;
        # in particular, `fan-pulse` cannot be shadowed by `fan_pulse`, and a
        # replacement cannot steal another template's display name or explicit alias.
        for alias_key in sorted(alias_keys):
            incumbent_id = self._aliases.get(alias_key)
            if incumbent_id is None:
                continue
            replacing_exact_incumbent = (
                allow_override and exact_incumbent == tid and incumbent_id == tid
            )
            if not replacing_exact_incumbent:
                raise self._collision_error(
                    normalized_key=alias_key,
                    incumbent_id=incumbent_id,
                    new_id=tid,
                    new_source=source,
                )

        # Mutation starts only after validation and the complete collision preflight.
        if exact_incumbent is not None:
            self._remove_registration(exact_incumbent)

        self._factories_by_id[tid] = factory

        # Add default aliases: id and display name
        for alias_key in alias_keys:
            self._aliases[alias_key] = tid

        # Store lightweight info for list/search
        tags = tuple(getattr(t.template.metadata, "tags", []) or [])

        self._info_by_id[tid] = TemplateInfo(
            template_id=tid,
            version=t.template.version,
            name=t.template.name,
            category=t.template.category,
            tags=tags,
        )
        self._source_by_id[tid] = source
        return True

    def _collision_error(
        self,
        *,
        normalized_key: str,
        incumbent_id: str,
        new_id: str,
        new_source: str,
    ) -> ValueError:
        """Describe a collision with enough provenance to resolve it."""
        incumbent_source = self._source_by_id[incumbent_id]
        return ValueError(
            f"Template normalized key collision: {normalized_key!r} belongs to "
            f"template {incumbent_id!r} (existing source={incumbent_source}); "
            f"cannot register template {new_id!r} (new source={new_source})"
        )

    def register_document(
        self,
        document: TemplateDoc,
        *,
        aliases: Iterable[str] = (),
        source: str = "data",
        allow_override: bool = False,
    ) -> bool:
        """Register a validated data document through the factory path.

        The captured model is copied on every lookup, preserving the registry's
        existing fresh-instance guarantee for data and Python sources alike.
        """
        captured = document.model_copy(deep=True)

        def factory() -> TemplateDoc:
            return captured.model_copy(deep=True)

        return self.register(
            factory,
            aliases=aliases,
            source=source,
            allow_override=allow_override,
        )

    def _remove_registration(self, template_id: str) -> None:
        """Remove one registration and every alias that points to it."""
        self._factories_by_id.pop(template_id, None)
        self._info_by_id.pop(template_id, None)
        self._source_by_id.pop(template_id, None)
        self._aliases = {
            alias: target for alias, target in self._aliases.items() if target != template_id
        }

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
