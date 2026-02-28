"""Analyze real-world xLights sequence profiles for cross-layer target reuse.

Checks whether the heuristic validator's cross-lane rules match real-world
sequencing practice by examining enriched effect events from extracted profiles.

Design rules under test:
  1. CROSS_LANE_BASE_REUSE: BASE layer targets should not overlap with other lanes
  2. CROSS_LANE_REUSE_GROUP: Targets in RHYTHM+ACCENT should be disjoint
  3. TARGET_SELF_OVERLAP: Same target, same layer, overlapping time
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys


def load_events(profile_dir: Path) -> list[dict]:
    """Load enriched effect events from a profile directory."""
    path = profile_dir / "enriched_effect_events.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def analyze_profile(profile_dir: Path) -> dict:
    """Analyze a single profile for cross-layer target reuse patterns."""
    events = load_events(profile_dir)
    if not events:
        return {"name": profile_dir.name, "error": "no events"}

    # Map: target_name -> set of layer indices
    target_layers: dict[str, set[int]] = defaultdict(set)
    # Map: target_name -> list of (start_ms, end_ms, layer_index)
    target_timings: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    # Map: target_name -> target_kind
    target_kinds: dict[str, str] = {}

    for event in events:
        name = event["target_name"]
        layer = event["layer_index"]
        target_layers[name].add(layer)
        target_timings[name].append((event["start_ms"], event["end_ms"], layer))
        target_kinds[name] = event.get("target_kind", "unknown")

    total_targets = len(target_layers)
    single_layer_targets = sum(1 for layers in target_layers.values() if len(layers) == 1)
    multi_layer_targets = sum(1 for layers in target_layers.values() if len(layers) > 1)

    # Analyze simultaneous cross-layer usage (temporal overlap on different layers)
    simultaneous_cross_layer: dict[str, int] = {}
    for name, timings in target_timings.items():
        if len(target_layers[name]) <= 1:
            continue

        # Sort by start time
        sorted_t = sorted(timings, key=lambda x: x[0])
        overlap_count = 0

        for i in range(len(sorted_t)):
            for j in range(i + 1, len(sorted_t)):
                s_i, e_i, l_i = sorted_t[i]
                s_j, e_j, l_j = sorted_t[j]
                if s_j >= e_i:
                    break
                if l_i != l_j:
                    overlap_count += 1

        if overlap_count > 0:
            simultaneous_cross_layer[name] = overlap_count

    # Identify "group" targets (vs individual models) — groups are our lane analogy
    group_targets = {n for n, k in target_kinds.items() if k == "group"}
    model_targets = {n for n, k in target_kinds.items() if k == "model"}

    group_multi_layer = {n for n in group_targets if len(target_layers[n]) > 1}
    group_simultaneous = {n for n in group_targets if n in simultaneous_cross_layer}

    model_multi_layer = {n for n in model_targets if len(target_layers[n]) > 1}
    model_simultaneous = {n for n in model_targets if n in simultaneous_cross_layer}

    # Layer distribution for multi-layer targets
    multi_layer_details = []
    for name in sorted(simultaneous_cross_layer.keys()):
        layers = sorted(target_layers[name])
        kind = target_kinds[name]
        overlaps = simultaneous_cross_layer[name]
        multi_layer_details.append(
            {
                "target": name,
                "kind": kind,
                "layers": layers,
                "layer_count": len(layers),
                "simultaneous_overlaps": overlaps,
            }
        )

    return {
        "name": profile_dir.name,
        "total_events": len(events),
        "total_targets": total_targets,
        "single_layer_targets": single_layer_targets,
        "multi_layer_targets": multi_layer_targets,
        "multi_layer_pct": round(multi_layer_targets / total_targets * 100, 1)
        if total_targets
        else 0,
        "targets_with_simultaneous_cross_layer": len(simultaneous_cross_layer),
        "simultaneous_pct": round(len(simultaneous_cross_layer) / total_targets * 100, 1)
        if total_targets
        else 0,
        "group_targets": len(group_targets),
        "group_multi_layer": len(group_multi_layer),
        "group_simultaneous": len(group_simultaneous),
        "model_targets": len(model_targets),
        "model_multi_layer": len(model_multi_layer),
        "model_simultaneous": len(model_simultaneous),
        "top_cross_layer_targets": sorted(
            multi_layer_details, key=lambda x: x["simultaneous_overlaps"], reverse=True
        )[:10],
    }


def main():
    profiles_dir = Path("data/profiles")
    if not profiles_dir.exists():
        print(f"Profiles directory not found: {profiles_dir}")
        sys.exit(1)

    profile_dirs = sorted(
        [d for d in profiles_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    print("=" * 90)
    print("CROSS-LAYER TARGET REUSE ANALYSIS — REAL-WORLD xLights SEQUENCES")
    print("=" * 90)
    print()

    all_results = []
    for pd in profile_dirs:
        result = analyze_profile(pd)
        all_results.append(result)

    # Summary table
    print(
        f"{'Profile':<14} {'Events':>7} {'Targets':>8} {'Multi-L':>8} {'%':>6} "
        f"{'Simul':>6} {'%':>6} | {'Grp':>4} {'G-ML':>5} {'G-Sim':>6} | "
        f"{'Mdl':>4} {'M-ML':>5} {'M-Sim':>6}"
    )
    print("-" * 110)

    totals = defaultdict(int)
    for r in all_results:
        if "error" in r:
            print(f"{r['name']:<14} {r['error']}")
            continue

        print(
            f"{r['name']:<14} {r['total_events']:>7} {r['total_targets']:>8} "
            f"{r['multi_layer_targets']:>8} {r['multi_layer_pct']:>5.1f}% "
            f"{r['targets_with_simultaneous_cross_layer']:>6} {r['simultaneous_pct']:>5.1f}% | "
            f"{r['group_targets']:>4} {r['group_multi_layer']:>5} {r['group_simultaneous']:>6} | "
            f"{r['model_targets']:>4} {r['model_multi_layer']:>5} {r['model_simultaneous']:>6}"
        )

        for key in [
            "total_events",
            "total_targets",
            "multi_layer_targets",
            "targets_with_simultaneous_cross_layer",
            "group_targets",
            "group_multi_layer",
            "group_simultaneous",
            "model_targets",
            "model_multi_layer",
            "model_simultaneous",
        ]:
            totals[key] += r[key]

    print("-" * 110)
    total_t = totals["total_targets"]
    print(
        f"{'TOTALS':<14} {totals['total_events']:>7} {total_t:>8} "
        f"{totals['multi_layer_targets']:>8} "
        f"{totals['multi_layer_targets'] / total_t * 100 if total_t else 0:>5.1f}% "
        f"{totals['targets_with_simultaneous_cross_layer']:>6} "
        f"{totals['targets_with_simultaneous_cross_layer'] / total_t * 100 if total_t else 0:>5.1f}% | "
        f"{totals['group_targets']:>4} {totals['group_multi_layer']:>5} {totals['group_simultaneous']:>6} | "
        f"{totals['model_targets']:>4} {totals['model_multi_layer']:>5} {totals['model_simultaneous']:>6}"
    )

    # Detailed cross-layer examples
    print()
    print("=" * 90)
    print("TOP SIMULTANEOUS CROSS-LAYER TARGETS (per profile)")
    print("=" * 90)
    print()
    print("These are targets that have effects on MULTIPLE layers at the SAME TIME.")
    print("This is directly analogous to a group appearing in multiple lanes (BASE+RHYTHM, etc.)")
    print()

    for r in all_results:
        if "error" in r or not r.get("top_cross_layer_targets"):
            continue
        print(f"--- {r['name']} ---")
        for entry in r["top_cross_layer_targets"]:
            print(
                f"  {entry['target']:<45} [{entry['kind']}] "
                f"layers={entry['layers']} "
                f"overlaps={entry['simultaneous_overlaps']}"
            )
        print()

    # Verdict
    print("=" * 90)
    print("VERDICT: Do cross-lane exclusivity rules match real-world practice?")
    print("=" * 90)
    print()

    multi_pct = (totals["multi_layer_targets"] / total_t * 100) if total_t else 0
    simul_pct = (totals["targets_with_simultaneous_cross_layer"] / total_t * 100) if total_t else 0
    grp_simul_pct = (
        (totals["group_simultaneous"] / totals["group_targets"] * 100)
        if totals["group_targets"]
        else 0
    )

    print(f"  Multi-layer target rate:       {multi_pct:.1f}% of targets appear on >1 layer")
    print(
        f"  Simultaneous cross-layer rate:  {simul_pct:.1f}% of targets have temporal overlap across layers"
    )
    print(
        f"  Group-level simultaneous rate:  {grp_simul_pct:.1f}% of group targets overlap across layers"
    )
    print()

    if grp_simul_pct > 30:
        print("  >> CONCLUSION: Cross-layer group sharing is COMMON in real sequences.")
        print("     The CROSS_LANE_REUSE rules may be overly strict.")
    elif grp_simul_pct > 10:
        print("  >> CONCLUSION: Cross-layer group sharing is MODERATE in real sequences.")
        print("     The CROSS_LANE_REUSE rules are reasonable but may need an allowlist.")
    else:
        print("  >> CONCLUSION: Cross-layer group sharing is RARE in real sequences.")
        print("     The CROSS_LANE_REUSE rules are well-grounded.")


if __name__ == "__main__":
    main()
