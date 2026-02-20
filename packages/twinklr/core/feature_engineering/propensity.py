"""Propensity Miner — mines effect-to-model affinity from corpus data."""

from __future__ import annotations

import re
from collections import defaultdict

from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    EffectModelAntiAffinity,
    PropensityIndex,
)

# Known model type patterns in target names (order matters — first match wins).
_MODEL_TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("megatree", r"mega\s*tree"),
    ("matrix", r"matrix"),
    ("arch", r"arch"),
    ("candy_cane", r"candy\s*cane"),
    ("snowflake", r"snowflake"),
    ("wreath", r"wreath"),
    ("star", r"star"),
    ("icicle", r"icicle"),
    ("spiral", r"spiral"),
    ("mini_tree", r"mini\s*tree"),
    ("fence", r"fence"),
    ("roofline", r"roof\s*line"),
    ("window", r"window"),
    ("bush", r"bush"),
    ("pillar", r"pillar"),
    ("stake", r"stake"),
    ("spinner", r"spinner"),
    ("flood", r"flood"),
    ("pixel_tree", r"pixel\s*tree"),
)

# Minimum corpus support to emit an affinity/anti-affinity.
_MIN_SUPPORT = 3

# Frequency threshold below which a pair is considered anti-affinity.
_ANTI_AFFINITY_THRESHOLD = 0.05


class PropensityMiner:
    """Mine effect-family → display-model-type affinity from corpus phrases."""

    def mine(self, *, phrases: tuple[EffectPhrase, ...]) -> PropensityIndex:
        if not phrases:
            return PropensityIndex(affinities=(), anti_affinities=())

        # Count (effect_family, model_type) co-occurrences.
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        family_counts: dict[str, int] = defaultdict(int)
        model_counts: dict[str, int] = defaultdict(int)

        for phrase in phrases:
            model_type = self._extract_model_type(phrase.target_name)
            if model_type is None:
                continue
            family = phrase.effect_family
            pair_counts[(family, model_type)] += 1
            family_counts[family] += 1
            model_counts[model_type] += 1

        if not pair_counts:
            return PropensityIndex(affinities=(), anti_affinities=())

        total = sum(pair_counts.values())
        all_families = set(family_counts.keys())
        all_models = set(model_counts.keys())

        affinities: list[EffectModelAffinity] = []
        anti_affinities: list[EffectModelAntiAffinity] = []

        for family in sorted(all_families):
            for model_type in sorted(all_models):
                count = pair_counts.get((family, model_type), 0)
                family_total = family_counts[family]
                model_total = model_counts[model_type]

                if count >= _MIN_SUPPORT:
                    # Frequency: how often this effect appears on this model
                    # relative to all appearances of this effect.
                    frequency = count / family_total if family_total > 0 else 0.0
                    # Exclusivity: how much of this model's usage is this effect
                    # relative to total model usage.
                    exclusivity = count / model_total if model_total > 0 else 0.0

                    affinities.append(
                        EffectModelAffinity(
                            effect_family=family,
                            model_type=model_type,
                            frequency=round(frequency, 4),
                            exclusivity=round(exclusivity, 4),
                            corpus_support=count,
                        )
                    )
                elif count == 0 and family_total >= _MIN_SUPPORT and model_total >= _MIN_SUPPORT:
                    # Anti-affinity: effect family exists, model exists,
                    # but they never appear together.
                    anti_affinities.append(
                        EffectModelAntiAffinity(
                            effect_family=family,
                            model_type=model_type,
                            corpus_support=family_total + model_total,
                        )
                    )

        return PropensityIndex(
            affinities=tuple(affinities),
            anti_affinities=tuple(anti_affinities),
        )

    @staticmethod
    def _extract_model_type(target_name: str) -> str | None:
        """Extract model type from target name using pattern matching."""
        lower = target_name.lower().strip()
        for model_type, pattern in _MODEL_TYPE_PATTERNS:
            if re.search(pattern, lower):
                return model_type
        return None
