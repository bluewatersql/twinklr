"""Sequence feature vector builder for embedding retrieval baseline."""

from __future__ import annotations

import statistics
from collections import Counter

from twinklr.core.feature_engineering.embeddings.models import SequenceFeatureVector
from twinklr.core.feature_engineering.models.bundle import FeatureBundle
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)


class SequenceFeatureVectorBuilder:
    """Constructs dense feature vectors from per-sequence FE output.

    Feature groups:
    1. Phrase distribution: effect_family frequencies (top-known families),
       motion_class dist, color_class dist, energy_class dist
    2. Taxonomy: taxonomy count, unknown ratio
    3. Target roles: role type frequencies, target count
    4. Temporal: phrase duration stats (mean, std, min, max),
       total active time, phrase count
    5. Style: layer count, distinct target count
    """

    # Fixed known effect families for consistent dimensionality
    _KNOWN_FAMILIES = (
        "BARS",
        "BEAM",
        "CHASE",
        "COLOR",
        "DIMMER",
        "FLASH",
        "MOTION",
        "PATTERN",
        "STATIC",
        "STROBE",
        "unknown",
    )
    _KNOWN_ROLES = ("lead", "accent", "fill", "background", "solo")

    def build(
        self,
        phrases: tuple[EffectPhrase, ...],
        taxonomy: tuple[PhraseTaxonomyRecord, ...],
        target_roles: tuple[TargetRoleAssignment, ...],
        bundle: FeatureBundle,
    ) -> SequenceFeatureVector:
        """Build feature vector from per-sequence artifacts.

        Args:
            phrases: Encoded effect phrases for the sequence.
            taxonomy: Taxonomy records keyed per phrase.
            target_roles: Target role assignments for the sequence.
            bundle: Feature bundle providing package/sequence identifiers.

        Returns:
            A fixed-dimensional SequenceFeatureVector with aligned names and values.
        """
        names: list[str] = []
        values: list[float] = []
        total = len(phrases) or 1  # avoid div by zero

        # --- Group 1: Phrase distribution ---
        family_counts = Counter(p.effect_family for p in phrases)
        for fam in self._KNOWN_FAMILIES:
            names.append(f"family_freq_{fam}")
            values.append(family_counts.get(fam, 0) / total)

        for mc in MotionClass:
            names.append(f"motion_freq_{mc.value}")
            values.append(sum(1 for p in phrases if p.motion_class == mc) / total)

        for cc in ColorClass:
            names.append(f"color_freq_{cc.value}")
            values.append(sum(1 for p in phrases if p.color_class == cc) / total)

        for ec in EnergyClass:
            names.append(f"energy_freq_{ec.value}")
            values.append(sum(1 for p in phrases if p.energy_class == ec) / total)

        # --- Group 2: Taxonomy ---
        names.append("taxonomy_count")
        values.append(float(len(taxonomy)))
        unknown_count = sum(1 for p in phrases if p.effect_family == "unknown")
        names.append("unknown_family_ratio")
        values.append(unknown_count / total)

        # --- Group 3: Target roles ---
        role_counts = Counter(r.role.value for r in target_roles)
        role_total = len(target_roles) or 1
        for role in self._KNOWN_ROLES:
            names.append(f"role_freq_{role}")
            values.append(role_counts.get(role, 0) / role_total)
        names.append("target_count")
        values.append(float(len(target_roles)))

        # --- Group 4: Temporal ---
        durations = [p.duration_ms for p in phrases] if phrases else [0]
        names.append("duration_mean")
        values.append(statistics.mean(durations))
        names.append("duration_std")
        values.append(statistics.stdev(durations) if len(durations) > 1 else 0.0)
        names.append("duration_min")
        values.append(float(min(durations)))
        names.append("duration_max")
        values.append(float(max(durations)))
        names.append("phrase_count")
        values.append(float(len(phrases)))
        total_active = sum(p.duration_ms for p in phrases)
        names.append("total_active_ms")
        values.append(float(total_active))

        # --- Group 5: Style ---
        names.append("distinct_layers")
        values.append(float(len({p.layer_index for p in phrases})) if phrases else 0.0)
        names.append("distinct_targets")
        values.append(float(len({p.target_name for p in phrases})) if phrases else 0.0)

        return SequenceFeatureVector(
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            feature_names=tuple(names),
            values=tuple(values),
            dimensionality=len(values),
        )
