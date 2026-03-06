"""Corpus builder for unknown effect entries — Phase B of Profiling V2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.normalization.models import (
    UnknownEffectCorpus,
    UnknownEffectEntry,
)


class UnknownEffectCorpusBuilder:
    """Extracts and structures unknown effect entries for embedding.

    Reads an ``unknown_diagnostics.json`` artifact (produced by
    ``ArtifactWriter.build_unknown_diagnostics``) and returns a typed
    ``UnknownEffectCorpus`` suitable for downstream embedding and clustering.

    Example::

        builder = UnknownEffectCorpusBuilder()
        corpus = builder.build(Path("output/unknown_diagnostics.json"))
    """

    def build(self, diagnostics_path: Path) -> UnknownEffectCorpus:
        """Parse unknown_diagnostics.json and build a structured corpus.

        Args:
            diagnostics_path: Path to the ``unknown_diagnostics.json`` file.

        Returns:
            An ``UnknownEffectCorpus`` with entries sorted by count descending.

        Raises:
            FileNotFoundError: If the diagnostics file does not exist.
            ValueError: If the file cannot be parsed as valid JSON.
        """
        raw: dict[str, Any] = json.loads(diagnostics_path.read_text(encoding="utf-8"))

        total_unknown_phrases: int = raw.get("unknown_effect_family_count", 0)
        unknown_effect_family_ratio: float = float(raw.get("unknown_effect_family_ratio", 0.0))
        unknown_motion_ratio: float = float(raw.get("unknown_motion_ratio", 0.0))

        top_entries: list[dict[str, Any]] = raw.get("top_unknown_effect_types", [])
        entries: list[UnknownEffectEntry] = []

        for item in top_entries:
            effect_type: str = item["effect_type"]
            normalized_key: str = item["normalized_key"]
            count: int = int(item["count"])
            sample_rows: list[dict[str, Any]] = item.get("sample_rows", [])

            sample_params: tuple[dict[str, Any], ...] = tuple(sample_rows)
            context_text: str = _build_context_text(effect_type, sample_rows)

            entries.append(
                UnknownEffectEntry(
                    effect_type=effect_type,
                    normalized_key=normalized_key,
                    count=count,
                    sample_params=sample_params,
                    context_text=context_text,
                )
            )

        entries.sort(key=lambda e: e.count, reverse=True)

        return UnknownEffectCorpus(
            entries=tuple(entries),
            total_unknown_phrases=total_unknown_phrases,
            unknown_effect_family_ratio=unknown_effect_family_ratio,
            unknown_motion_ratio=unknown_motion_ratio,
        )


def _build_context_text(effect_type: str, sample_rows: list[dict[str, Any]]) -> str:
    """Build a context string from an effect type and its sample rows.

    Args:
        effect_type: The raw effect type name.
        sample_rows: List of sample row dicts from the diagnostics artifact.

    Returns:
        A space-joined context string including the effect name and all
        scalar values from the sample rows.
    """
    values: list[str] = [effect_type]
    for row in sample_rows:
        for v in row.values():
            values.append(str(v))
    return " ".join(values)


__all__ = ["UnknownEffectCorpusBuilder"]
