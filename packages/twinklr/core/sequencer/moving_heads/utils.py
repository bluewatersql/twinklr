from __future__ import annotations

from collections.abc import Iterable, Sequence

from twinklr.core.sequencer.models.enum import SemanticGroupType, TemplateRole

# Canonical left→right ordering (covers your current TemplateRole set)
_ROLE_ORDER: list[TemplateRole] = [
    TemplateRole.FAR_LEFT,
    TemplateRole.OUTER_LEFT,
    TemplateRole.CENTER_LEFT,
    TemplateRole.MID_LEFT,
    TemplateRole.INNER_LEFT,
    TemplateRole.CENTER,
    TemplateRole.INNER_RIGHT,
    TemplateRole.MID_RIGHT,
    TemplateRole.CENTER_RIGHT,
    TemplateRole.OUTER_RIGHT,
    TemplateRole.FAR_RIGHT,
]
_ROLE_ORDER_INDEX = {r: i for i, r in enumerate(_ROLE_ORDER)}


def canonical_sort_roles(roles: Iterable[TemplateRole]) -> list[TemplateRole]:
    """Deterministic ordering for role lists (stable across runs)."""
    uniq = set(roles)
    return sorted(
        uniq,
        key=lambda r: (_ROLE_ORDER_INDEX.get(r, 10_000), str(r.value)),
    )


def _is_left(role: TemplateRole) -> bool:
    return role.value.endswith("_LEFT") or role is TemplateRole.FAR_LEFT


def _is_right(role: TemplateRole) -> bool:
    return role.value.endswith("_RIGHT") or role is TemplateRole.FAR_RIGHT


def resolve_semantic_group(
    group: SemanticGroupType,
    available_roles: Sequence[TemplateRole],
) -> list[TemplateRole]:
    """
    Resolve SemanticGroupType -> concrete TemplateRole list.

    Canonical rules:
      - ALL: all available roles
      - LEFT/RIGHT: roles ending with _LEFT/_RIGHT (+ FAR_LEFT/FAR_RIGHT)
      - OUTER: prefers explicit OUTER_*/FAR_* roles if present; otherwise extremes (first+last)
      - INNER: prefers explicit INNER_* roles if present; otherwise (available - OUTER)
      - ODD/EVEN: based on canonical left→right ordering, 1-indexed (ODD=1st,3rd,...)
    """
    ordered = canonical_sort_roles(available_roles)
    avail_set = set(ordered)

    if not ordered:
        raise ValueError("No available roles to resolve semantic group against.")

    if group is SemanticGroupType.ALL:
        resolved = ordered

    elif group is SemanticGroupType.LEFT:
        resolved = [r for r in ordered if _is_left(r)]

    elif group is SemanticGroupType.RIGHT:
        resolved = [r for r in ordered if _is_right(r)]

    elif group is SemanticGroupType.OUTER:
        explicit = [
            r for r in ordered if r.value.startswith("OUTER_") or r.value.startswith("FAR_")
        ]
        if explicit:
            resolved = explicit
        else:
            # Fallback: outermost fixtures by position
            resolved = [ordered[0], ordered[-1]] if len(ordered) >= 2 else [ordered[0]]

    elif group is SemanticGroupType.INNER:
        explicit = [r for r in ordered if r.value.startswith("INNER_")]
        if explicit:
            resolved = explicit
        else:
            outer = set(resolve_semantic_group(SemanticGroupType.OUTER, ordered))
            resolved = [r for r in ordered if r not in outer]

    elif group is SemanticGroupType.ODD:
        # 1-indexed odd positions: 1st,3rd,5th...
        resolved = [r for i, r in enumerate(ordered, start=1) if i % 2 == 1]

    elif group is SemanticGroupType.EVEN:
        # 1-indexed even positions: 2nd,4th,6th...
        resolved = [r for i, r in enumerate(ordered, start=1) if i % 2 == 0]

    else:
        raise ValueError(f"Unsupported semantic group: {group}")

    # Final safety checks
    resolved = canonical_sort_roles(resolved)
    unknown = [r for r in resolved if r not in avail_set]
    if unknown:
        raise ValueError(f"Resolved roles not in available set: {[r.value for r in unknown]}")
    if not resolved:
        raise ValueError(f"Semantic group {group.value} resolved to an empty role set.")

    return resolved
