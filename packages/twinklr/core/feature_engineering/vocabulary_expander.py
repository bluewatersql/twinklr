"""Vocabulary expander — discovers compound terms from effect stack signatures.

Analyzes multi-layer stack signatures from an EffectStackCatalog to discover
compound motion and energy vocabulary beyond the hardcoded single-effect enums.
Output is a VocabularyExtensions sidecar that downstream components can optionally
consume without changes to the core EffectPhrase schema.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.stacks import EffectStackCatalog
from twinklr.core.feature_engineering.models.vocabulary import (
    CompoundEnergyTerm,
    CompoundMotionTerm,
    VocabularyExtensions,
)
from twinklr.core.feature_engineering.phrase_encoder import _DEFAULT_MAP

# ---------------------------------------------------------------------------
# Compound motion term lookup: (base_motion, accent_motion) -> (term, desc)
# ---------------------------------------------------------------------------

_COMPOUND_MOTION_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("static", "sweep"): ("wash_and_chase", "Static wash with sweep overlay"),
    ("static", "sparkle"): ("wash_and_sparkle", "Static wash with sparkle overlay"),
    ("static", "pulse"): ("wash_and_pulse", "Static wash with pulse overlay"),
    ("sweep", "sweep"): ("dual_chase", "Two synchronized chase patterns"),
    ("sweep", "sparkle"): ("chase_and_sparkle", "Chase pattern with sparkle overlay"),
    ("pulse", "sweep"): ("pulse_and_chase", "Pulse pattern with sweep overlay"),
    ("static", "static"): ("layered_wash", "Multiple layered static washes"),
}

# ---------------------------------------------------------------------------
# Compound energy term lookup: (base_energy, accent_energy) -> (term, desc, combined)
# ---------------------------------------------------------------------------

_COMPOUND_ENERGY_MAP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("low", "burst"): ("wash_burst", "Sustained wash with burst overlay", "burst"),
    ("low", "high"): ("subtle_drive", "Low base with high-energy accent", "mid"),
    ("mid", "high"): ("building", "Mid base building to high accent", "high"),
    ("mid", "burst"): ("mid_impact", "Mid base with burst impact", "high"),
    ("low", "mid"): ("gentle_layer", "Low base with gentle mid overlay", "low"),
}

# Default minimum corpus support for including a term.
_DEFAULT_MIN_SUPPORT: int = 10


@dataclass(frozen=True)
class ParsedSignature:
    """Result of parsing a stack signature string.

    Attributes:
        families: Effect family names in layer order.
        roles: Single-letter role abbreviations in layer order.
        blends: Blend mode strings in layer order.
    """

    families: tuple[str, ...]
    roles: tuple[str, ...]
    blends: tuple[str, ...]


def _build_family_to_axes() -> dict[str, dict[str, str]]:
    """Build a reverse lookup from effect_family -> axis values.

    The PhraseEncoder._DEFAULT_MAP is keyed by normalized effect name
    (e.g. "colorwash") with an "effect_family" value (e.g. "color_wash").
    This function inverts that to map from effect_family to axis values.

    Returns:
        Dict mapping effect_family to its axis classification dict.
    """
    result: dict[str, dict[str, str]] = {}
    for _key, axes in _DEFAULT_MAP.items():
        family = axes.get("effect_family", "")
        if family and family not in result:
            result[family] = dict(axes)
    return result


class VocabularyExpander:
    """Analyze stack signatures to discover compound vocabulary.

    Parses multi-layer stack signatures from an EffectStackCatalog,
    looks up motion and energy classes for each component family,
    and produces compound motion/energy terms based on the combination
    rules defined in the spec.

    Args:
        min_support: Minimum corpus support count for inclusion.
            Defaults to 10.
    """

    def __init__(self, *, min_support: int = _DEFAULT_MIN_SUPPORT) -> None:
        self._min_support = min_support
        self._family_axes = _build_family_to_axes()

    def expand(
        self,
        *,
        stack_catalog: EffectStackCatalog,
    ) -> VocabularyExtensions:
        """Expand vocabulary from stack catalog.

        Args:
            stack_catalog: Catalog of detected effect stacks.

        Returns:
            VocabularyExtensions with discovered compound terms.
        """
        if not stack_catalog.stacks:
            return VocabularyExtensions(
                total_stack_signatures_analyzed=0,
                total_multi_layer_stacks=0,
            )

        # Count occurrences of each unique signature (multi-layer only).
        sig_counts: dict[str, int] = defaultdict(int)
        multi_layer_count = 0
        for stack in stack_catalog.stacks:
            if stack.layer_count < 2:
                continue
            multi_layer_count += 1
            sig_counts[stack.stack_signature] += 1

        # Discover compound terms from each unique signature.
        motion_terms: list[CompoundMotionTerm] = []
        energy_terms: list[CompoundEnergyTerm] = []

        for sig, count in sorted(sig_counts.items(), key=lambda x: -x[1]):
            if count < self._min_support:
                continue

            parsed = self.parse_signature(sig)
            if len(parsed.families) < 2:
                continue

            # Look up axes for each family.  Skip if any family is unknown.
            family_axes_list: list[dict[str, str]] = []
            all_known = True
            for fam in parsed.families:
                axes = self._family_axes.get(fam)
                if axes is None:
                    all_known = False
                    break
                family_axes_list.append(axes)

            if not all_known:
                continue

            # Use first layer as base, last layer as accent for 2-layer.
            # For 3+ layers, still use first and last.
            base_axes = family_axes_list[0]
            accent_axes = family_axes_list[-1]

            base_motion = base_axes.get("motion_class", "unknown")
            accent_motion = accent_axes.get("motion_class", "unknown")
            base_energy = base_axes.get("energy_class", "unknown")
            accent_energy = accent_axes.get("energy_class", "unknown")

            # Discover compound motion term.
            motion_key = (base_motion, accent_motion)
            if motion_key in _COMPOUND_MOTION_MAP:
                term_name, description = _COMPOUND_MOTION_MAP[motion_key]
                motion_terms.append(
                    CompoundMotionTerm(
                        term=term_name,
                        description=description,
                        component_families=parsed.families,
                        component_roles=tuple(_role_label(r) for r in parsed.roles),
                        motion_axis=f"{base_motion}+{accent_motion}",
                        corpus_support=count,
                        canonical_signature=sig,
                    )
                )

            # Discover compound energy term.
            energy_key = (base_energy, accent_energy)
            if energy_key in _COMPOUND_ENERGY_MAP:
                term_name, description, combined = _COMPOUND_ENERGY_MAP[energy_key]
                energy_terms.append(
                    CompoundEnergyTerm(
                        term=term_name,
                        description=description,
                        base_energy=base_energy,
                        accent_energy=accent_energy,
                        combined_energy=combined,
                        corpus_support=count,
                        canonical_signature=sig,
                    )
                )

        return VocabularyExtensions(
            compound_motion_terms=tuple(motion_terms),
            compound_energy_terms=tuple(energy_terms),
            total_stack_signatures_analyzed=len(sig_counts),
            total_multi_layer_stacks=multi_layer_count,
        )

    @staticmethod
    def parse_signature(signature: str) -> ParsedSignature:
        """Parse a stack signature into component families and roles.

        Signature format: ``family@role|blend+family@role|blend+...``

        Args:
            signature: Canonical stack signature string.

        Returns:
            ParsedSignature with families, roles, and blends.
        """
        families: list[str] = []
        roles: list[str] = []
        blends: list[str] = []

        parts = signature.split("+")
        for part in parts:
            # Split "family@role|blend" into components.
            if "@" not in part:
                continue
            family, remainder = part.split("@", 1)
            if "|" in remainder:
                role, blend = remainder.split("|", 1)
            else:
                role = remainder
                blend = "normal"
            families.append(family)
            roles.append(role)
            blends.append(blend)

        return ParsedSignature(
            families=tuple(families),
            roles=tuple(roles),
            blends=tuple(blends),
        )


def _role_label(abbreviation: str) -> str:
    """Convert single-letter role abbreviation to full label.

    Args:
        abbreviation: Single-letter role code (b, r, a, h, f, t, c).

    Returns:
        Full role label string.
    """
    _map = {
        "b": "base",
        "r": "rhythm",
        "a": "accent",
        "h": "highlight",
        "f": "fill",
        "t": "texture",
        "c": "custom",
    }
    return _map.get(abbreviation, abbreviation)
