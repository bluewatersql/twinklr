"""`.xmap` writer — model-name mapping hints for the effect import.

Importing a donor `.xsq` into the user's own sequence requires mapping each model the
donor names onto a model in the user's layout. That mapping is the friction in the
import flow, and xLights can take it from an `.xmap` file
(`importXLightsSequence` with `mapmethod: file`) instead of asking for it row by row.

Twinklr cannot know the user's layout, so the hint it ships is the identity mapping:
every model Twinklr emitted, proposed against a target of the same name. When the user's
layout uses those names (the fixture config's `xlights_model_name` values normally come
*from* that layout) the import needs no manual mapping at all; when it does not, the
file is a pre-filled starting point rather than an empty grid.

Row format is tab-separated `model / strand / node / target / colour`, preceded by the
legacy leading flag line. UNVERIFIED against a real xLights — P1P-T12 owns that check.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

XMAP_SUFFIX = ".xmap"

XMAP_LEADING_FLAG = "false"
"""First line of an `.xmap`: the legacy "map by strand" flag, false for model mapping."""


def build_xmap_text(model_names: Iterable[str], *, targets: Mapping[str, str] | None = None) -> str:
    """Build the `.xmap` body mapping each emitted model to a layout model.

    Args:
        model_names: Models Twinklr emitted, in emission order. Duplicates are dropped,
            keeping the first occurrence.
        targets: Optional override of the target name per emitted model; anything not
            named here maps to itself.

    Returns:
        The file text, ending in a newline.
    """
    targets = targets or {}
    lines = [XMAP_LEADING_FLAG]
    seen: set[str] = set()
    for name in model_names:
        if name in seen:
            continue
        seen.add(name)
        # model, strand, node, target, colour — Twinklr maps whole models, so the
        # strand/node columns are empty and the colour column is left to xLights.
        lines.append(f"{name}\t\t\t{targets.get(name, name)}\t")
    return "\n".join(lines) + "\n"


def write_xmap(
    model_names: Iterable[str], path: Path, *, targets: Mapping[str, str] | None = None
) -> Path:
    """Write the mapping hint to `path`.

    Args:
        model_names: Models Twinklr emitted.
        path: Destination `.xmap` file; parent directories are created.
        targets: Optional per-model target overrides.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = build_xmap_text(model_names, targets=targets)
    path.write_text(text, encoding="utf-8")
    logger.debug("Wrote mapping hints for %d models to %s", len(text.splitlines()) - 1, path)
    return path
