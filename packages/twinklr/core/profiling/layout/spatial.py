"""Spatial and topology utilities for layout profiles."""

from __future__ import annotations

import re
import statistics

from twinklr.core.profiling.models.enums import ModelCategory, StartChannelFormat
from twinklr.core.profiling.models.layout import ModelProfile, SpatialStatistics

_TRAILING_NUMBER_RE = re.compile(r"^(.+?)\s*[-_ ]?\s*(\d+)$")


def reconstruct_chain_sequences(models: list[ModelProfile]) -> tuple[tuple[str, ...], ...]:
    """Reconstruct model/address chain sequences from profiled models."""
    mc_next: dict[str, str] = {}
    mc_targets: set[str] = set()
    ac_next: dict[str, str] = {}

    for model in models:
        if model.chain_next:
            mc_next[model.name] = model.chain_next
            mc_targets.add(model.chain_next)

        start_channel = model.start_channel
        if (
            start_channel is not None
            and start_channel.format is StartChannelFormat.CHAINED
            and start_channel.chained_to
        ):
            ac_next[model.name] = start_channel.chained_to

    sequences: list[list[str]] = []

    # Model-chain traversal.
    visited_mc: set[str] = set()
    for head in sorted([name for name in mc_next if name not in mc_targets]):
        seq = [head]
        visited_mc.add(head)
        current = head
        while current in mc_next:
            nxt = mc_next[current]
            if nxt in visited_mc:
                break
            seq.append(nxt)
            visited_mc.add(nxt)
            current = nxt
        if len(seq) > 1:
            sequences.append(seq)

    # Address-chain traversal (parent -> children breadth-first).
    children: dict[str, list[str]] = {}
    for child, parent in ac_next.items():
        children.setdefault(parent, []).append(child)
    for child_list in children.values():
        child_list.sort()

    heads = sorted([parent for parent in children if parent not in ac_next])
    visited_ac: set[str] = set()
    for head in heads:
        seq = [head]
        visited_ac.add(head)
        queue = [head]
        while queue:
            current = queue.pop(0)
            for child in children.get(current, []):
                if child in visited_ac:
                    continue
                visited_ac.add(child)
                seq.append(child)
                queue.append(child)
        if len(seq) > 1:
            sequences.append(seq)

    return tuple(tuple(seq) for seq in sequences)


def detect_model_families(models: list[ModelProfile]) -> dict[str, int]:
    """Detect numbered-model families such as 'Arch 1', 'Arch 2'."""
    base_to_members: dict[str, list[str]] = {}
    for model in models:
        match = _TRAILING_NUMBER_RE.match(model.name)
        if not match:
            continue
        base = match.group(1).strip()
        base_to_members.setdefault(base, []).append(model.name)

    return {base: len(members) for base, members in base_to_members.items() if len(members) >= 2}


def compute_spatial_statistics(models: list[ModelProfile]) -> SpatialStatistics | None:
    """Compute spatial distribution metrics for display models."""
    display_models = [m for m in models if m.category is ModelCategory.DISPLAY]
    if not display_models:
        return None

    xs = [m.position["world_x"] for m in display_models]
    ys = [m.position["world_y"] for m in display_models]
    zs = [m.position["world_z"] for m in display_models]

    return SpatialStatistics(
        bounding_box={
            "x_range": [round(min(xs), 2), round(max(xs), 2)],
            "y_range": [round(min(ys), 2), round(max(ys), 2)],
            "z_range": [round(min(zs), 2), round(max(zs), 2)],
        },
        center_of_mass={
            "x": round(statistics.mean(xs), 2),
            "y": round(statistics.mean(ys), 2),
            "z": round(statistics.mean(zs), 2),
        },
        spread={
            "x_std": round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0,
            "y_std": round(statistics.pstdev(ys), 2) if len(ys) > 1 else 0.0,
            "z_std": round(statistics.pstdev(zs), 2) if len(zs) > 1 else 0.0,
        },
        is_3d_layout=any(z != 0 for z in zs),
    )
