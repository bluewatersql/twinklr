"""Owner-declared corpus partitions for style-fingerprint extraction.

The declaration deliberately selects stable corpus identities, rather than
attempting to infer an author's style from effect content. A sequence key is
``<package_id>/<sequence_file_id>``; package and sequence IDs originate from
the P1K-T1 content-hash identity pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.transitions import TransitionGraph

STYLE_GROUP_SCHEMA_VERSION = "twinklr.style-groups.v1"


class StyleGroupSelector(BaseModel):
    """Explicit stable corpus identities that belong to one owner-selected style."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_ids: tuple[str, ...] = ()
    sequence_file_ids: tuple[str, ...] = ()
    sequence_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_at_least_one_selector(self) -> StyleGroupSelector:
        """Reject a group that would otherwise silently match the full corpus."""
        if not (self.package_ids or self.sequence_file_ids or self.sequence_keys):
            raise ValueError(
                "style-group selector needs package_ids, sequence_file_ids, or sequence_keys"
            )
        return self

    def matches(self, package_id: str, sequence_file_id: str) -> bool:
        """Return whether a sequence belongs to this explicit selector union."""
        return (
            package_id in self.package_ids
            or sequence_file_id in self.sequence_file_ids
            or f"{package_id}/{sequence_file_id}" in self.sequence_keys
        )


class StyleGroup(BaseModel):
    """One named, owner-defined style partition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    style_name: str = Field(min_length=1)
    selector: StyleGroupSelector


class StyleGroupDeclaration(BaseModel):
    """JSON declaration supplied by the owner before a real grouped refresh."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["twinklr.style-groups.v1"] = "twinklr.style-groups.v1"
    groups: tuple[StyleGroup, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_output_names(self) -> StyleGroupDeclaration:
        """Avoid two owner labels resolving to the same artifact path."""
        names = [style_group_slug(group.style_name) for group in self.groups]
        if len(set(names)) != len(names):
            raise ValueError("style-group names must produce unique artifact slugs")
        return self


def style_group_slug(style_name: str) -> str:
    """Make a stable, filesystem-safe artifact component from an owner label."""
    slug = re.sub(r"[^a-z0-9]+", "_", style_name.strip().lower()).strip("_")
    if not slug:
        raise ValueError("style-group name must contain at least one letter or number")
    return slug


def load_style_group_declaration(path: Path) -> StyleGroupDeclaration:
    """Load a required owner declaration, with actionable errors for real runs."""
    if not path.is_file():
        raise FileNotFoundError(f"style-group declaration is required and was not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid style-group declaration JSON: {path}: {exc.msg}") from exc
    return StyleGroupDeclaration.model_validate(payload)


def filter_style_group_inputs(
    *,
    group: StyleGroup,
    phrases: tuple[EffectPhrase, ...],
    layering_rows: tuple[LayeringFeatureRow, ...],
    color_rows: tuple[ColorNarrativeRow, ...],
    transition_graph: TransitionGraph | None,
) -> tuple[
    tuple[EffectPhrase, ...],
    tuple[LayeringFeatureRow, ...],
    tuple[ColorNarrativeRow, ...],
    TransitionGraph | None,
]:
    """Filter every style-fingerprint input to a single declared group."""
    selector = group.selector
    grouped_phrases = tuple(
        phrase for phrase in phrases if selector.matches(phrase.package_id, phrase.sequence_file_id)
    )
    grouped_layering = tuple(
        row for row in layering_rows if selector.matches(row.package_id, row.sequence_file_id)
    )
    grouped_color = tuple(
        row for row in color_rows if selector.matches(row.package_id, row.sequence_file_id)
    )
    if transition_graph is None:
        return grouped_phrases, grouped_layering, grouped_color, None
    transitions = tuple(
        transition
        for transition in transition_graph.transitions
        if selector.matches(transition.package_id, transition.sequence_file_id)
    )
    grouped_transitions = transition_graph.model_copy(
        update={"transitions": transitions, "total_transitions": len(transitions)}
    )
    return grouped_phrases, grouped_layering, grouped_color, grouped_transitions


__all__ = [
    "STYLE_GROUP_SCHEMA_VERSION",
    "StyleGroup",
    "StyleGroupDeclaration",
    "StyleGroupSelector",
    "filter_style_group_inputs",
    "load_style_group_declaration",
    "style_group_slug",
]
