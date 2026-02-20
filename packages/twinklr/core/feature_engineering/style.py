"""Style Fingerprint Extractor — aggregates FE artifacts into creator style profiles."""

from __future__ import annotations

from collections import Counter, defaultdict

from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.feature_engineering.models.transitions import (
    TransitionGraph,
    TransitionType,
)

# Color class → palette complexity score mapping.
_COLOR_COMPLEXITY: dict[str, float] = {
    "mono": 0.2,
    "palette": 0.5,
    "multi": 0.9,
    "unknown": 0.5,
}

# Temperature heuristic from dominant color classes.
_COLOR_TEMPERATURE: dict[str, float] = {
    "mono": 0.5,  # neutral
    "palette": 0.5,
    "multi": 0.6,  # slightly warm (more colors = more vibrant)
    "unknown": 0.5,
}


class StyleFingerprintExtractor:
    """Aggregate existing FE artifacts into a StyleFingerprint."""

    def extract(
        self,
        *,
        creator_id: str,
        phrases: tuple[EffectPhrase, ...],
        layering_rows: tuple[LayeringFeatureRow, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
        transition_graph: TransitionGraph | None,
    ) -> StyleFingerprint:
        if not phrases:
            return StyleFingerprint(
                creator_id=creator_id,
                recipe_preferences={},
                transition_style=TransitionStyleProfile(
                    preferred_gap_ms=0.0, overlap_tendency=0.5, variety_score=0.5
                ),
                color_tendencies=ColorStyleProfile(
                    palette_complexity=0.5, contrast_preference=0.5, temperature_preference=0.5
                ),
                timing_style=TimingStyleProfile(
                    beat_alignment_strictness=0.5,
                    density_preference=0.5,
                    section_change_aggression=0.5,
                ),
                layering_style=LayeringStyleProfile(
                    mean_layers=1.0, max_layers=1, blend_mode_preference="normal"
                ),
                corpus_sequence_count=0,
            )

        sequence_ids = {p.sequence_file_id for p in phrases}

        return StyleFingerprint(
            creator_id=creator_id,
            recipe_preferences=self._compute_recipe_preferences(phrases),
            transition_style=self._compute_transition_style(transition_graph),
            color_tendencies=self._compute_color_tendencies(phrases, color_rows),
            timing_style=self._compute_timing_style(phrases),
            layering_style=self._compute_layering_style(layering_rows),
            corpus_sequence_count=len(sequence_ids),
        )

    @staticmethod
    def _compute_recipe_preferences(
        phrases: tuple[EffectPhrase, ...],
    ) -> dict[str, float]:
        counts: Counter[str] = Counter()
        for p in phrases:
            counts[p.effect_family] += 1
        total = sum(counts.values())
        if total == 0:
            return {}
        return {family: round(count / total, 4) for family, count in sorted(counts.items())}

    @staticmethod
    def _compute_transition_style(
        transition_graph: TransitionGraph | None,
    ) -> TransitionStyleProfile:
        if transition_graph is None or not transition_graph.transitions:
            return TransitionStyleProfile(
                preferred_gap_ms=0.0, overlap_tendency=0.5, variety_score=0.5
            )

        gaps = [t.gap_ms for t in transition_graph.transitions]
        preferred_gap = sum(gaps) / len(gaps) if gaps else 0.0

        overlap_count = sum(1 for g in gaps if g < 0)
        overlap_tendency = overlap_count / len(gaps) if gaps else 0.5

        type_counts: Counter[TransitionType] = Counter()
        for t in transition_graph.transitions:
            type_counts[t.transition_type] += 1
        total = sum(type_counts.values())
        # Variety = 1 - dominance of the most common type.
        max_count = max(type_counts.values()) if type_counts else 0
        variety_score = 1.0 - (max_count / total) if total > 0 else 0.5

        return TransitionStyleProfile(
            preferred_gap_ms=round(max(0.0, preferred_gap), 2),
            overlap_tendency=round(min(1.0, max(0.0, overlap_tendency)), 4),
            variety_score=round(min(1.0, max(0.0, variety_score)), 4),
        )

    @staticmethod
    def _compute_color_tendencies(
        phrases: tuple[EffectPhrase, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
    ) -> ColorStyleProfile:
        # Palette complexity from phrase color classes.
        color_counts: Counter[str] = Counter()
        for p in phrases:
            color_counts[p.color_class.value] += 1
        total = sum(color_counts.values())
        if total > 0:
            palette_complexity = sum(
                _COLOR_COMPLEXITY.get(cc, 0.5) * count / total for cc, count in color_counts.items()
            )
            temperature = sum(
                _COLOR_TEMPERATURE.get(cc, 0.5) * count / total
                for cc, count in color_counts.items()
            )
        else:
            palette_complexity = 0.5
            temperature = 0.5

        # Contrast from color narrative rows.
        if color_rows:
            contrast_values = [r.contrast_shift_from_prev for r in color_rows]
            contrast_preference = sum(contrast_values) / len(contrast_values)
        else:
            contrast_preference = 0.5

        return ColorStyleProfile(
            palette_complexity=round(min(1.0, max(0.0, palette_complexity)), 4),
            contrast_preference=round(min(1.0, max(0.0, contrast_preference)), 4),
            temperature_preference=round(min(1.0, max(0.0, temperature)), 4),
        )

    @staticmethod
    def _compute_timing_style(
        phrases: tuple[EffectPhrase, ...],
    ) -> TimingStyleProfile:
        # Beat alignment from onset_sync_score.
        sync_scores = [p.onset_sync_score for p in phrases if p.onset_sync_score is not None]
        beat_alignment = sum(sync_scores) / len(sync_scores) if sync_scores else 0.5

        # Density from phrase count per section.
        sections: dict[str, int] = defaultdict(int)
        for p in phrases:
            label = p.section_label or "__none__"
            sections[label] += 1
        if sections:
            avg_density = sum(sections.values()) / len(sections)
            # Normalize: assume 20+ phrases/section = density 1.0.
            density = min(1.0, avg_density / 20.0)
        else:
            density = 0.5

        # Section change aggression from energy variance across sections.
        section_energies: dict[str, list[int]] = defaultdict(list)
        energy_map = {"low": 1, "mid": 2, "high": 3, "burst": 4, "unknown": 2}
        for p in phrases:
            label = p.section_label or "__none__"
            section_energies[label].append(energy_map.get(p.energy_class.value, 2))
        if len(section_energies) > 1:
            section_means = [sum(v) / len(v) for v in section_energies.values()]
            # Variance of section means, normalized.
            mean_of_means = sum(section_means) / len(section_means)
            variance = sum((m - mean_of_means) ** 2 for m in section_means) / len(section_means)
            aggression = min(1.0, variance / 2.0)  # normalize
        else:
            aggression = 0.5

        return TimingStyleProfile(
            beat_alignment_strictness=round(min(1.0, max(0.0, beat_alignment)), 4),
            density_preference=round(min(1.0, max(0.0, density)), 4),
            section_change_aggression=round(min(1.0, max(0.0, aggression)), 4),
        )

    @staticmethod
    def _compute_layering_style(
        layering_rows: tuple[LayeringFeatureRow, ...],
    ) -> LayeringStyleProfile:
        if not layering_rows:
            return LayeringStyleProfile(
                mean_layers=1.0, max_layers=1, blend_mode_preference="normal"
            )

        mean_layers = sum(r.mean_concurrent_layers for r in layering_rows) / len(layering_rows)
        max_layers = max(r.max_concurrent_layers for r in layering_rows)

        # Blend mode preference heuristic based on collision score.
        avg_collision = sum(r.collision_score for r in layering_rows) / len(layering_rows)
        if avg_collision > 0.5:
            blend_mode = "screen"
        elif avg_collision > 0.2:
            blend_mode = "add"
        else:
            blend_mode = "normal"

        return LayeringStyleProfile(
            mean_layers=round(mean_layers, 2),
            max_layers=max_layers,
            blend_mode_preference=blend_mode,
        )
