"""Effect metadata profile builder.

Builds per-family metadata profiles from corpus data: duration distributions,
classification distributions, parameter profiles, model affinities, layering
behavior, and section placement patterns.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np

from twinklr.core.feature_engineering.models.metadata import (
    DurationDistribution,
    EffectMetadataProfile,
    EffectMetadataProfiles,
    LayeringBehavior,
    ParamFrequency,
    ParamProfile,
    SectionPlacement,
)
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_engineering.models.stacks import EffectStackCatalog

_CLASSIFICATION_AXES: tuple[str, ...] = (
    "motion_class",
    "color_class",
    "energy_class",
    "continuity_class",
    "spatial_class",
)

_MAX_PARAM_KEYS: int = 10
_MAX_PARAM_VALUES: int = 5
_MAX_AFFINITY_COUNT: int = 3
_MAX_PREFERRED_SECTIONS: int = 3


class EffectMetadataProfileBuilder:
    """Build per-family metadata profiles from corpus data.

    Groups phrases by effect_family and computes sub-profiles for duration,
    classification, parameters, model affinities, layering, and section
    placement.
    """

    def build(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        stacks: EffectStackCatalog | None = None,
        propensity: PropensityIndex | None = None,
    ) -> EffectMetadataProfiles:
        """Build metadata profiles from corpus data.

        Args:
            phrases: All effect phrases from the corpus.
            stacks: Optional stack catalog for layering/param analysis.
            propensity: Optional propensity index for model affinities.

        Returns:
            Collection of per-family metadata profiles.
        """
        grouped: dict[str, list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            grouped[phrase.effect_family].append(phrase)

        # Pre-index stack data per family for efficient lookup
        family_stack_data = self._index_stacks_by_family(stacks)

        # Pre-index propensity data per family
        family_affinities = self._index_affinities(propensity)

        profiles: list[EffectMetadataProfile] = []
        for family, family_phrases in sorted(grouped.items()):
            stack_data = family_stack_data.get(family)
            affinities = family_affinities.get(family, ())
            profile = self._build_family_profile(
                family=family,
                family_phrases=family_phrases,
                stack_data=stack_data,
                affinities=affinities,
            )
            profiles.append(profile)

        return EffectMetadataProfiles(
            schema_version="v1.0.0",
            profile_count=len(profiles),
            total_phrase_count=len(phrases),
            profiles=tuple(profiles),
        )

    def _build_family_profile(
        self,
        *,
        family: str,
        family_phrases: list[EffectPhrase],
        stack_data: _FamilyStackData | None,
        affinities: tuple[str, ...],
    ) -> EffectMetadataProfile:
        """Build a single family profile."""
        sequence_ids = {p.sequence_file_id for p in family_phrases}
        duration = self._compute_duration(family_phrases)
        classification, classification_dist = self._compute_classification(family_phrases)
        top_params = self._compute_param_profiles(family, stack_data)
        layering = self._compute_layering(stack_data)
        section = self._compute_section_placement(family_phrases)

        return EffectMetadataProfile(
            effect_family=family,
            corpus_phrase_count=len(family_phrases),
            corpus_sequence_count=len(sequence_ids),
            duration=duration,
            classification=classification,
            classification_distribution=classification_dist,
            top_params=top_params,
            model_affinities=affinities,
            layering=layering,
            section_placement=section,
        )

    @staticmethod
    def _compute_duration(phrases: list[EffectPhrase]) -> DurationDistribution:
        """Compute duration distribution using NumPy percentiles."""
        durations = np.array([p.duration_ms for p in phrases], dtype=np.float64)
        return DurationDistribution(
            p10_ms=int(np.percentile(durations, 10)),
            p25_ms=int(np.percentile(durations, 25)),
            p50_ms=int(np.percentile(durations, 50)),
            p75_ms=int(np.percentile(durations, 75)),
            p90_ms=int(np.percentile(durations, 90)),
            mean_ms=float(np.mean(durations)),
            min_ms=int(np.min(durations)),
            max_ms=int(np.max(durations)),
            sample_count=len(phrases),
        )

    @staticmethod
    def _compute_classification(
        phrases: list[EffectPhrase],
    ) -> tuple[dict[str, str], dict[str, dict[str, float]]]:
        """Compute classification modal values and distributions."""
        total = len(phrases)
        classification: dict[str, str] = {}
        classification_dist: dict[str, dict[str, float]] = {}

        for axis in _CLASSIFICATION_AXES:
            counter: Counter[str] = Counter()
            for p in phrases:
                value = getattr(p, axis)
                counter[value.value if hasattr(value, "value") else str(value)] += 1

            modal = counter.most_common(1)[0][0]
            classification[axis] = modal
            classification_dist[axis] = {
                val: round(count / total, 10) for val, count in counter.most_common()
            }

        return classification, classification_dist

    @staticmethod
    def _compute_param_profiles(
        family: str,
        stack_data: _FamilyStackData | None,
    ) -> tuple[ParamProfile, ...]:
        """Compute parameter profiles from preserved_params in stacks."""
        if stack_data is None or not stack_data.param_values:
            return ()

        param_values = stack_data.param_values
        param_counts = stack_data.param_layer_counts

        # Sort params by prevalence (total occurrences), take top _MAX_PARAM_KEYS
        sorted_params = sorted(
            param_values.keys(),
            key=lambda k: param_counts[k],
            reverse=True,
        )[:_MAX_PARAM_KEYS]

        profiles: list[ParamProfile] = []
        for param_name in sorted_params:
            value_counter = param_values[param_name]
            if not value_counter:
                continue
            total = sum(value_counter.values())
            distinct = len(value_counter)
            top = value_counter.most_common(_MAX_PARAM_VALUES)
            top_freqs = tuple(
                ParamFrequency(
                    param_name=param_name,
                    value=val,
                    frequency=round(count / total, 10),
                    corpus_count=count,
                )
                for val, count in top
            )
            profiles.append(
                ParamProfile(
                    param_name=param_name,
                    distinct_value_count=distinct,
                    top_values=top_freqs,
                )
            )

        return tuple(profiles)

    @staticmethod
    def _compute_layering(
        stack_data: _FamilyStackData | None,
    ) -> LayeringBehavior:
        """Compute layering behavior from stack data."""
        if stack_data is None or stack_data.total_stacks == 0:
            return LayeringBehavior(
                typical_layer_role="UNKNOWN",
                role_distribution={},
                common_partners=(),
                mean_stack_position=0.0,
                solo_ratio=1.0,
            )

        total = stack_data.total_stacks
        role_counter = stack_data.role_counter
        partner_counter = stack_data.partner_counter
        position_sum = stack_data.position_sum
        solo_count = stack_data.solo_count

        # Role distribution
        role_dist = {role: round(count / total, 10) for role, count in role_counter.most_common()}
        typical_role = role_counter.most_common(1)[0][0] if role_counter else "UNKNOWN"

        # Common partners (sorted by frequency, all partners)
        common_partners = tuple(p for p, _ in partner_counter.most_common())

        mean_pos = position_sum / total if total > 0 else 0.0
        solo_ratio = round(solo_count / total, 10)

        return LayeringBehavior(
            typical_layer_role=typical_role,
            role_distribution=role_dist,
            common_partners=common_partners,
            mean_stack_position=round(mean_pos, 10),
            solo_ratio=solo_ratio,
        )

    @staticmethod
    def _compute_section_placement(
        phrases: list[EffectPhrase],
    ) -> SectionPlacement:
        """Compute section placement distribution."""
        labeled = [p for p in phrases if p.section_label is not None]
        if not labeled:
            return SectionPlacement(
                section_distribution={},
                preferred_sections=(),
            )

        total = len(labeled)
        counter: Counter[str] = Counter()
        for p in labeled:
            assert p.section_label is not None  # guaranteed by filter
            counter[p.section_label] += 1

        dist = {label: round(count / total, 10) for label, count in counter.most_common()}
        preferred = tuple(label for label, _ in counter.most_common(_MAX_PREFERRED_SECTIONS))

        return SectionPlacement(
            section_distribution=dist,
            preferred_sections=preferred,
        )

    @staticmethod
    def _index_stacks_by_family(
        stacks: EffectStackCatalog | None,
    ) -> dict[str, _FamilyStackData]:
        """Pre-index stack data by effect family for O(1) lookup."""
        if stacks is None:
            return {}

        result: dict[str, _FamilyStackData] = {}

        for stack in stacks.stacks:
            families_in_stack: set[str] = set()
            for layer in stack.layers:
                family = layer.phrase.effect_family
                families_in_stack.add(family)

                if family not in result:
                    result[family] = _FamilyStackData()

                data = result[family]
                data.total_stacks += 1
                data.role_counter[layer.layer_role.value] += 1
                data.position_sum += layer.phrase.layer_index

                # Track preserved params
                for key, value in layer.preserved_params.items():
                    data.param_values[key][value] += 1
                    data.param_layer_counts[key] += 1

            # Track solo vs multi-layer
            is_single = stack.layer_count == 1
            for family in families_in_stack:
                if is_single:
                    result[family].solo_count += 1

            # Track partners
            for family in families_in_stack:
                for other in families_in_stack:
                    if other != family:
                        result[family].partner_counter[other] += 1

        return result

    @staticmethod
    def _index_affinities(
        propensity: PropensityIndex | None,
    ) -> dict[str, tuple[str, ...]]:
        """Pre-index model affinities by family, sorted by frequency desc."""
        if propensity is None:
            return {}

        family_affinities: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for aff in propensity.affinities:
            family_affinities[aff.effect_family].append((aff.frequency, aff.model_type))

        result: dict[str, tuple[str, ...]] = {}
        for family, items in family_affinities.items():
            items.sort(key=lambda x: x[0], reverse=True)
            result[family] = tuple(model for _, model in items[:_MAX_AFFINITY_COUNT])

        return result


class _FamilyStackData:
    """Mutable accumulator for per-family stack statistics.

    Used internally during stack indexing; not part of public API.
    """

    __slots__ = (
        "total_stacks",
        "solo_count",
        "role_counter",
        "partner_counter",
        "position_sum",
        "param_values",
        "param_layer_counts",
    )

    def __init__(self) -> None:
        self.total_stacks: int = 0
        self.solo_count: int = 0
        self.role_counter: Counter[str] = Counter()
        self.partner_counter: Counter[str] = Counter()
        self.position_sum: float = 0.0
        self.param_values: dict[str, Counter[Any]] = defaultdict(Counter)
        self.param_layer_counts: Counter[str] = Counter()
