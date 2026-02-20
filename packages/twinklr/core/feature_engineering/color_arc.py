"""Color Arc Engine — extracts song-level color narrative from FE artifacts."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    ColorTransitionRule,
    NamedPalette,
    SectionColorAssignment,
    SongColorArc,
)
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.phrases import EffectPhrase, EnergyClass

# Holiday-themed palette templates keyed by dominant_color_class.
_PALETTE_TEMPLATES: dict[str, list[dict[str, object]]] = {
    "mono": [
        {
            "suffix": "cool_white",
            "name": "Cool White",
            "colors": ("#FFFFFF",),
            "mood_tags": ("minimal", "elegant"),
            "temperature": "cool",
        },
        {
            "suffix": "warm_white",
            "name": "Warm White",
            "colors": ("#FFF8E7",),
            "mood_tags": ("warm", "classic"),
            "temperature": "warm",
        },
    ],
    "palette": [
        {
            "suffix": "classic_holiday",
            "name": "Classic Holiday",
            "colors": ("#FF0000", "#00FF00", "#FFFFFF"),
            "mood_tags": ("festive", "christmas"),
            "temperature": "neutral",
        },
        {
            "suffix": "icy_blue",
            "name": "Icy Blue",
            "colors": ("#A8D8EA", "#E0F7FA", "#FFFFFF"),
            "mood_tags": ("calm", "winter"),
            "temperature": "cool",
        },
    ],
    "multi": [
        {
            "suffix": "rainbow_burst",
            "name": "Rainbow Burst",
            "colors": ("#FF0000", "#FF8800", "#FFFF00", "#00FF00", "#0088FF", "#8800FF"),
            "mood_tags": ("energetic", "vibrant"),
            "temperature": "warm",
        },
        {
            "suffix": "carnival",
            "name": "Carnival",
            "colors": ("#FF0066", "#00CCFF", "#FFCC00", "#66FF00"),
            "mood_tags": ("fun", "party"),
            "temperature": "neutral",
        },
    ],
}

# Energy → temperature mapping for arc curve keyframes.
_ENERGY_TEMPERATURE: dict[EnergyClass, float] = {
    EnergyClass.LOW: 0.3,
    EnergyClass.MID: 0.5,
    EnergyClass.HIGH: 0.7,
    EnergyClass.BURST: 0.9,
    EnergyClass.UNKNOWN: 0.5,
}

# Contrast threshold above which we emit a transition rule.
_CONTRAST_THRESHOLD = 0.3


class ColorArcExtractor:
    """Transform ColorNarrativeRow + EffectPhrase data into a SongColorArc."""

    def extract(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        color_narrative: tuple[ColorNarrativeRow, ...],
    ) -> SongColorArc:
        if not color_narrative:
            return SongColorArc(
                palette_library=(),
                section_assignments=(),
                arc_curve=(),
                transition_rules=(),
            )

        sorted_rows = sorted(color_narrative, key=lambda r: r.section_index)

        # Build palettes and assignments per section.
        palettes: dict[str, NamedPalette] = {}
        assignments: list[SectionColorAssignment] = []
        energy_by_section = self._compute_section_energy(phrases)

        for row in sorted_rows:
            palette_id = self._palette_id_for(row)
            if palette_id not in palettes:
                palettes[palette_id] = self._build_palette(palette_id, row.dominant_color_class)

            spatial = self._build_spatial_mapping(phrases, row.section_label)
            assignments.append(
                SectionColorAssignment(
                    schema_version="v1.0.0",
                    package_id=row.package_id,
                    sequence_file_id=row.sequence_file_id,
                    section_label=row.section_label,
                    section_index=row.section_index,
                    palette_id=palette_id,
                    spatial_mapping=spatial,
                    shift_timing="section_boundary",
                    contrast_target=row.contrast_shift_from_prev,
                )
            )

        # Build transition rules from contrast shifts.
        transition_rules = self._build_transition_rules(sorted_rows, assignments)

        # Build arc curve keyframes from section energy progression.
        arc_curve = self._build_arc_curve(sorted_rows, energy_by_section)

        return SongColorArc(
            schema_version="v1.0.0",
            palette_library=tuple(palettes.values()),
            section_assignments=tuple(assignments),
            arc_curve=arc_curve,
            transition_rules=tuple(transition_rules),
        )

    @staticmethod
    def _palette_id_for(row: ColorNarrativeRow) -> str:
        dominant = row.dominant_color_class if row.dominant_color_class in _PALETTE_TEMPLATES else "palette"
        templates = _PALETTE_TEMPLATES[dominant]
        # Rotate through available templates by section index.
        template = templates[row.section_index % len(templates)]
        return f"pal_{template['suffix']}"

    @staticmethod
    def _build_palette(palette_id: str, dominant_color_class: str) -> NamedPalette:
        dominant = dominant_color_class if dominant_color_class in _PALETTE_TEMPLATES else "palette"
        for template in _PALETTE_TEMPLATES[dominant]:
            if palette_id == f"pal_{template['suffix']}":
                return NamedPalette(
                    palette_id=palette_id,
                    name=str(template["name"]),
                    colors=tuple(str(c) for c in template["colors"]),  # type: ignore[union-attr]
                    mood_tags=tuple(str(t) for t in template["mood_tags"]),  # type: ignore[union-attr]
                    temperature=template["temperature"],  # type: ignore[arg-type]
                )
        # Fallback — shouldn't happen with correct _palette_id_for logic.
        return NamedPalette(
            palette_id=palette_id,
            name="Default",
            colors=("#FFFFFF",),
            mood_tags=(),
            temperature="neutral",
        )

    @staticmethod
    def _build_spatial_mapping(
        phrases: tuple[EffectPhrase, ...],
        section_label: str,
    ) -> dict[str, str]:
        section_phrases = [p for p in phrases if p.section_label == section_label]
        if not section_phrases:
            return {}
        targets: dict[str, int] = defaultdict(int)
        for p in section_phrases:
            targets[p.target_name] += 1
        sorted_targets = sorted(targets.items(), key=lambda t: (-t[1], t[0]))
        mapping: dict[str, str] = {}
        for i, (target, _) in enumerate(sorted_targets):
            mapping[target] = "primary" if i == 0 else "accent"
        return mapping

    @staticmethod
    def _compute_section_energy(
        phrases: tuple[EffectPhrase, ...],
    ) -> dict[str, EnergyClass]:
        from collections import Counter

        by_section: dict[str, list[EnergyClass]] = defaultdict(list)
        for p in phrases:
            label = p.section_label or "__none__"
            by_section[label].append(p.energy_class)
        result: dict[str, EnergyClass] = {}
        for section, energies in by_section.items():
            counts = Counter(energies)
            dominant = max(counts, key=lambda e: (counts[e], e.value))
            result[section] = dominant
        return result

    @staticmethod
    def _build_transition_rules(
        sorted_rows: list[ColorNarrativeRow],
        assignments: list[SectionColorAssignment],
    ) -> list[ColorTransitionRule]:
        rules: list[ColorTransitionRule] = []
        for i in range(1, len(sorted_rows)):
            row = sorted_rows[i]
            if row.contrast_shift_from_prev >= _CONTRAST_THRESHOLD:
                from_palette = assignments[i - 1].palette_id
                to_palette = assignments[i].palette_id
                if from_palette != to_palette:
                    style: Literal["crossfade", "cut", "ripple"] = (
                        "cut" if row.contrast_shift_from_prev >= 0.8 else "crossfade"
                    )
                    rules.append(
                        ColorTransitionRule(
                            from_palette_id=from_palette,
                            to_palette_id=to_palette,
                            transition_style=style,
                            duration_bars=2 if style == "crossfade" else 1,
                        )
                    )
        return rules

    @staticmethod
    def _build_arc_curve(
        sorted_rows: list[ColorNarrativeRow],
        energy_by_section: dict[str, EnergyClass],
    ) -> tuple[ArcKeyframe, ...]:
        if not sorted_rows:
            return ()
        n = len(sorted_rows)
        keyframes: list[ArcKeyframe] = []
        for i, row in enumerate(sorted_rows):
            position = i / max(n - 1, 1)
            energy = energy_by_section.get(row.section_label, EnergyClass.MID)
            temp = _ENERGY_TEMPERATURE.get(energy, 0.5)
            # Saturation rises with energy, contrast from narrative.
            sat = min(1.0, 0.4 + temp * 0.6)
            keyframes.append(
                ArcKeyframe(
                    position_pct=round(position, 4),
                    temperature=temp,
                    saturation=round(sat, 4),
                    contrast=row.contrast_shift_from_prev,
                )
            )
        return tuple(keyframes)
