"""Load moving-head templates from strict JSON documents.

Python builtins load first and configured data directories load second. Collisions
across normalized template IDs, display names, or explicit aliases are a loud error
with both sources named. Callers must pass ``allow_overrides=True`` to shadow the
exact same template ID with a data document; even then, aliases owned by any other
template cannot be stolen. The registry preflights the entire key set before removing
the old source's aliases/factory/metadata, so a failed override leaves it intact.

Tracked template data lives under the existing repository catalog root at
``catalog/templates/moving_heads``. That shares P1K-T3's data home without pretending
that ``TemplateDoc`` and ``EffectRecipe`` already have one schema. Structurally they
are converging on one catalog with two renderers, later; unifying them is deliberately
outside this loader.

The physical family catalog lives beside it, at
``catalog/templates/moving_heads_physical``, and loads only for a ``physical_v2`` job
(``admit_physical_catalog``), between the builtins and any ``--template-dir``.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates.library import (
    REGISTRY,
    TemplateNotFoundError,
    TemplateRegistry,
)

if TYPE_CHECKING:
    from twinklr.core.config.models import JobConfig

DEFAULT_DATA_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[6] / "catalog" / "templates" / "moving_heads"
)
PHYSICAL_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[6] / "catalog" / "templates" / "moving_heads_physical"
)
"""The physical family catalog: outside `DEFAULT_DATA_TEMPLATE_DIR`, whose documents
must stay model-equal to Python builtins and which loads recursively."""


class TemplateDataError(ValueError):
    """A data template file is not strict JSON or a valid ``TemplateDoc``."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise TemplateDataError(f"duplicate JSON object key: {key!r}")
        document[key] = value
    return document


def _reject_nonfinite(value: str) -> None:
    raise TemplateDataError(f"non-finite JSON number is not allowed: {value}")


def load_template_document(path: Path) -> TemplateDoc:
    """Parse one strict JSON file and validate the full ``TemplateDoc`` schema."""
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
        if not isinstance(payload, dict):
            raise TemplateDataError("top-level JSON value must be an object")
        template = payload.get("template")
        repeat = template.get("repeat") if isinstance(template, dict) else None
        if not isinstance(repeat, dict) or "remainder_policy" not in repeat:
            raise TemplateDataError("template.repeat.remainder_policy must be declared")
        return TemplateDoc.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError, TemplateDataError) as error:
        detail = str(error).replace("\n", "; ")
        raise TemplateDataError(f"invalid template document {path}: {detail}") from error


def discover_template_documents(directory: Path) -> list[Path]:
    """Return JSON documents below ``directory`` in deterministic path order."""
    if not directory.exists():
        raise FileNotFoundError(f"Template data directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Template data path is not a directory: {directory}")
    return sorted(path for path in directory.rglob("*.json") if path.is_file())


def load_templates_from_directory(
    directory: Path,
    *,
    registry: TemplateRegistry = REGISTRY,
    allow_overrides: bool = False,
    aliases: dict[str, Iterable[str]] | None = None,
) -> list[str]:
    """Load and register every JSON ``TemplateDoc`` below a configured directory.

    Files are processed in sorted order. A failure is intentionally loud and stops
    loading; silent shadowing would make a selected template depend on filesystem
    traversal order.
    """
    registered: list[str] = []
    aliases_by_id = aliases or {}
    for path in discover_template_documents(directory):
        document = load_template_document(path)
        template_id = document.template.template_id
        if registry.register_document(
            document,
            aliases=aliases_by_id.get(template_id, ()),
            source=f"data:{path}",
            allow_override=allow_overrides,
        ):
            registered.append(template_id)
    return registered


def admit_physical_catalog(
    job_config: JobConfig, *, registry: TemplateRegistry = REGISTRY
) -> list[str]:
    """Hold the physical family catalog in `registry` exactly when the job is `physical_v2`.

    A physical job registers each catalog document, keeping one an earlier run in the
    same process already admitted from the catalog; any other job removes every catalog
    document again. Nothing else loads `PHYSICAL_TEMPLATE_DIR`, so a legacy run, the
    deterministic selector and the shared registry's 37 builtins are unchanged.

    Returns:
        The catalog's template IDs now registered, in path order; none for a legacy job.
    """
    if job_config.moving_heads.mode != "physical_v2":
        for info in registry.list_all():
            if in_physical_catalog(info.template_id, registry=registry):
                registry.unregister(info.template_id)
        return []
    admitted: list[str] = []
    for path in discover_template_documents(PHYSICAL_TEMPLATE_DIR):
        document = load_template_document(path)
        template_id = document.template.template_id
        source = f"data:{path}"
        try:
            already = registry.source(template_id) == source
        except TemplateNotFoundError:
            already = False
        if already or registry.register_document(document, source=source):
            admitted.append(template_id)
    return admitted


def in_physical_catalog(template_id: str, *, registry: TemplateRegistry = REGISTRY) -> bool:
    """Whether the registered template was loaded from `PHYSICAL_TEMPLATE_DIR`: the
    templates the pre-planning gate may leave out of the offer instead of refusing."""
    source = registry.source(template_id)
    return source.startswith("data:") and Path(source.removeprefix("data:")).is_relative_to(
        PHYSICAL_TEMPLATE_DIR
    )
