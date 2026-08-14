"""Deterministic Python-form ``TemplateDoc`` to JSON data-form conversion."""

from __future__ import annotations

import json
from pathlib import Path
import re

from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY, TemplateRegistry

_SAFE_TEMPLATE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def dump_template_document(document: TemplateDoc) -> str:
    """Return canonical, human-reviewable JSON that round-trips exactly."""
    payload = document.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_registry(
    output_directory: Path,
    *,
    registry: TemplateRegistry = REGISTRY,
    template_ids: list[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Write one deterministic JSON document per selected registered template."""
    selected_ids = template_ids or sorted(info.template_id for info in registry.list_all())
    output_directory.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for template_id in sorted(selected_ids):
        if _SAFE_TEMPLATE_ID.fullmatch(template_id) is None:
            raise ValueError(f"Template id is not safe as a filename: {template_id!r}")
        path = output_directory / f"{template_id}.json"
        content = dump_template_document(registry.get(template_id))
        if path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite template document: {path}")
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
