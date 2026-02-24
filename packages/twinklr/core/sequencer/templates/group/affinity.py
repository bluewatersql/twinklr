"""AffinityScorer — computed template-context compatibility.

Derives compatibility from template features (tags, template_type,
visual_intent) at query time. Affinity tags decompose into three
categories derivable from existing template metadata:

- ``motif.*``  — direct overlap with template tags
- ``style.*``  — derivable from visual_intent + tags
- ``setting.*`` — derivable from template_type + energy
- ``constraint.*`` — universal or inferrable from template type
"""

from __future__ import annotations

from dataclasses import dataclass, field

from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent


@dataclass(frozen=True)
class AffinityQuery:
    """Query context for affinity scoring.

    Attributes:
        motif_ids: Motif identifiers from the section plan.
    """

    motif_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AffinityResult:
    """Computed affinity scores.

    Attributes:
        motif_score: How well template tags overlap with query motifs (0-1).
        overall: Combined affinity score (0-1).
    """

    motif_score: float = 0.0
    overall: float = 0.0


_VISUAL_INTENT_STYLE_MAP: dict[GroupVisualIntent, list[str]] = {
    GroupVisualIntent.ABSTRACT: ["style.bold_shapes", "style.clean_vector"],
    GroupVisualIntent.GEOMETRIC: ["style.bold_shapes", "style.clean_vector"],
    GroupVisualIntent.IMAGERY: ["style.bold_shapes"],
    GroupVisualIntent.TEXTURE: ["style.minimal"],
    GroupVisualIntent.ORGANIC: ["style.minimal"],
    GroupVisualIntent.HYBRID: ["style.bold_shapes"],
}

_TYPE_SETTING_MAP: dict[GroupTemplateType, list[str]] = {
    GroupTemplateType.BASE: ["setting.calm"],
    GroupTemplateType.RHYTHM: ["setting.hype"],
    GroupTemplateType.ACCENT: ["setting.hype", "setting.triumphant"],
    GroupTemplateType.TRANSITION: ["setting.dreamy"],
    GroupTemplateType.SPECIAL: ["setting.triumphant", "setting.playful"],
}

_UNIVERSAL_CONSTRAINTS: list[str] = [
    "constraint.clean_edges",
    "constraint.low_detail",
]


class AffinityScorer:
    """Stateless scorer that derives template-context compatibility."""

    @staticmethod
    def score(info: TemplateInfo, query: AffinityQuery) -> AffinityResult:
        """Compute affinity between a template and a query context.

        Args:
            info: Template metadata.
            query: Query context with motif_ids.

        Returns:
            AffinityResult with computed scores.
        """
        motif_score = AffinityScorer._score_motifs(info, query.motif_ids)
        overall = motif_score
        return AffinityResult(motif_score=motif_score, overall=overall)

    @staticmethod
    def has_motif_affinity(info: TemplateInfo, *, motif_ids: list[str]) -> bool:
        """Check if template has affinity for any of the given motifs.

        Args:
            info: Template metadata.
            motif_ids: Motif identifiers to check against.

        Returns:
            True if any template tag matches any motif_id.
        """
        if not motif_ids:
            return False
        return AffinityScorer._score_motifs(info, motif_ids) > 0.0

    @staticmethod
    def derive_affinity_tags(info: TemplateInfo) -> list[str]:
        """Derive affinity tags from template features.

        Generates motif, style, setting, and constraint tags from
        template metadata for use in planner prompts.

        Args:
            info: Template metadata.

        Returns:
            Computed affinity tags.
        """
        tags: list[str] = []

        for t in info.tags:
            tags.append(f"motif.{t}")

        style_tags = _VISUAL_INTENT_STYLE_MAP.get(info.visual_intent, [])
        tags.extend(style_tags)

        setting_tags = _TYPE_SETTING_MAP.get(info.template_type, [])
        tags.extend(setting_tags)

        tags.extend(_UNIVERSAL_CONSTRAINTS)

        return tags

    @staticmethod
    def _score_motifs(info: TemplateInfo, motif_ids: list[str]) -> float:
        """Score motif overlap between template tags and query motifs."""
        if not motif_ids:
            return 0.0

        tag_set = {t.lower() for t in info.tags}
        motif_set = {m.lower() for m in motif_ids}

        overlap = tag_set & motif_set
        if not overlap:
            return 0.0

        return len(overlap) / len(motif_set)
