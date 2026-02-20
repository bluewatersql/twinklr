"""Deterministic color narrative extraction (V1.8)."""

from __future__ import annotations

from collections import Counter, defaultdict

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow


class ColorNarrativeExtractor:
    """Compute section-level palette progression and contrast shifts."""

    def extract(self, phrases: tuple[EffectPhrase, ...]) -> tuple[ColorNarrativeRow, ...]:
        grouped: dict[tuple[str, str], dict[str, list[EffectPhrase]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for phrase in phrases:
            section = phrase.section_label or "__none__"
            grouped[(phrase.package_id, phrase.sequence_file_id)][section].append(phrase)

        rows: list[ColorNarrativeRow] = []
        for (package_id, sequence_file_id), sections in sorted(grouped.items()):
            ordered_section_labels = sorted(sections.keys())
            previous_dominant = "unknown"
            for idx, section_label in enumerate(ordered_section_labels):
                section_rows = sorted(
                    sections[section_label],
                    key=lambda row: (row.start_ms, row.layer_index, row.phrase_id),
                )
                color_counts = Counter(row.color_class.value for row in section_rows)
                dominant = sorted(color_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
                contrast = 0.0 if idx == 0 else self._contrast(previous_dominant, dominant)
                rows.append(
                    ColorNarrativeRow(
                        schema_version="v1.8.0",
                        package_id=package_id,
                        sequence_file_id=sequence_file_id,
                        section_label=section_label,
                        section_index=idx,
                        phrase_count=len(section_rows),
                        dominant_color_class=dominant,
                        contrast_shift_from_prev=contrast,
                        hue_family_movement=self._movement(previous_dominant, dominant, idx),
                    )
                )
                previous_dominant = dominant

        return tuple(rows)

    @staticmethod
    def _contrast(left: str, right: str) -> float:
        if left == right:
            return 0.0
        if "unknown" in {left, right}:
            return 0.35
        if {left, right} == {"mono", "multi"}:
            return 1.0
        if {left, right} == {"mono", "palette"}:
            return 0.65
        if {left, right} == {"palette", "multi"}:
            return 0.5
        return 0.4

    @staticmethod
    def _movement(left: str, right: str, idx: int) -> str:
        if idx == 0:
            return "section_start"
        if left == right:
            return "hold"
        if "unknown" in {left, right}:
            return "uncertain"
        return f"{left}_to_{right}"
