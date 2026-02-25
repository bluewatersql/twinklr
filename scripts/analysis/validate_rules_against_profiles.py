"""Validate ALL heuristic rules against real-world xLights sequence profiles.

Extracts every enforced design rule from the validator and judges,
then checks each against enriched_effect_events.json from extracted profiles.

Rules are categorized as:
  - SCHEMA: ID/enum integrity (always valid, no profile check)
  - TIMING: Placement bounds (always valid, no profile check)
  - OVERLAP: Same-target temporal overlap rules (needs real-world check)
  - OWNERSHIP: Same-target multi-plan rules (needs real-world check)
  - DIVERSITY: Template variety constraints (needs real-world check)
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuleResult:
    rule_code: str
    category: str
    description: str
    needs_profile_check: bool
    profile_support: str = ""  # SUPPORTED, CONTRADICTED, N/A
    evidence: str = ""


@dataclass
class ProfileStats:
    name: str
    total_events: int = 0
    total_targets: int = 0
    # Same-layer overlap stats
    same_layer_overlap_targets: int = 0
    same_layer_overlap_events: int = 0
    # Multi-plan-like stats (multiple effect groups on same target+layer)
    multi_group_same_layer: int = 0
    # Effect diversity
    unique_effects_per_target: dict[str, int] = field(default_factory=dict)
    effects_per_target: dict[str, int] = field(default_factory=dict)
    max_consecutive_same_effect: int = 0
    top2_effect_share: float = 0.0
    # Cross-layer (already proven)
    cross_layer_targets: int = 0
    simultaneous_cross_layer: int = 0


def load_events(profile_dir: Path) -> list[dict]:
    path = profile_dir / "enriched_effect_events.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def analyze_same_layer_overlap(events: list[dict]) -> dict:
    """Check if same target on same layer has temporal overlap.

    This validates:
    - TARGET_SELF_OVERLAP
    - WITHIN_COORDINATION_OVERLAP
    - Section judge rule: "same-target self-overlap"
    """
    by_target_layer: dict[tuple[str, int], list[tuple[int, int, str]]] = defaultdict(list)

    for e in events:
        key = (e["target_name"], e["layer_index"])
        by_target_layer[key].append((e["start_ms"], e["end_ms"], e.get("effect_name", "?")))

    overlap_count = 0
    overlap_target_layers = 0
    total_target_layers = len(by_target_layer)
    examples: list[str] = []

    for (target, layer), timings in by_target_layer.items():
        if len(timings) < 2:
            continue
        sorted_t = sorted(timings, key=lambda x: x[0])
        has_overlap = False
        for i in range(len(sorted_t) - 1):
            s1, e1, eff1 = sorted_t[i]
            s2, e2, eff2 = sorted_t[i + 1]
            if s2 < e1:
                overlap_ms = min(e1, e2) - s2
                if overlap_ms > 500:
                    overlap_count += 1
                    has_overlap = True
                    if len(examples) < 5:
                        examples.append(
                            f"  {target} layer={layer}: "
                            f"{eff1}({s1}-{e1}) overlaps {eff2}({s2}-{e2}) "
                            f"by {overlap_ms}ms"
                        )
        if has_overlap:
            overlap_target_layers += 1

    return {
        "total_target_layers": total_target_layers,
        "overlapping_target_layers": overlap_target_layers,
        "overlap_pct": round(overlap_target_layers / total_target_layers * 100, 1)
        if total_target_layers
        else 0,
        "total_overlaps": overlap_count,
        "examples": examples,
    }


def analyze_multi_effect_groups_same_layer(events: list[dict]) -> dict:
    """Check if same target on same layer has effects from multiple 'groups'.

    In xLights, effects are placed in sequences. If the same model has
    multiple non-contiguous effect blocks on the same layer, it's analogous
    to our "target in multiple coordination plans in same lane."
    """
    by_target_layer: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
    for e in events:
        key = (e["target_name"], e["layer_index"])
        by_target_layer[key].append((e["start_ms"], e["end_ms"]))

    multi_block_count = 0
    total_target_layers = len(by_target_layer)

    for key, timings in by_target_layer.items():
        if len(timings) < 2:
            continue
        sorted_t = sorted(timings, key=lambda x: x[0])
        gaps = 0
        for i in range(len(sorted_t) - 1):
            _, e1 = sorted_t[i]
            s2, _ = sorted_t[i + 1]
            if s2 > e1 + 100:
                gaps += 1
        if gaps >= 1:
            multi_block_count += 1

    return {
        "total_target_layers": total_target_layers,
        "multi_block_target_layers": multi_block_count,
        "multi_block_pct": round(multi_block_count / total_target_layers * 100, 1)
        if total_target_layers
        else 0,
    }


def analyze_effect_diversity(events: list[dict]) -> dict:
    """Check template/effect diversity patterns.

    Validates:
    - INSUFFICIENT_UNIQUE_TEMPLATES
    - TEMPLATE_OVERUSED
    - CONSECUTIVE_REUSE_VIOLATION
    - TOP_HEAVY_DISTRIBUTION
    """
    by_target: dict[str, list[str]] = defaultdict(list)
    for e in events:
        by_target[e["target_name"]].append(e.get("effect_name", "unknown"))

    all_effects: list[str] = []
    for target, effects in by_target.items():
        all_effects.extend(effects)

    if not all_effects:
        return {}

    counts = Counter(all_effects)
    unique = len(counts)
    total = len(all_effects)
    max_uses = max(counts.values()) if counts else 0

    sorted_vals = sorted(counts.values(), reverse=True)
    top2 = sum(sorted_vals[:2]) / total if total else 0

    max_consecutive = 1
    current = 1
    for i in range(1, len(all_effects)):
        if all_effects[i] == all_effects[i - 1]:
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 1

    return {
        "total_effects": total,
        "unique_effects": unique,
        "max_uses_single": max_uses,
        "max_uses_pct": round(max_uses / total * 100, 1) if total else 0,
        "top2_share": round(top2 * 100, 1),
        "max_consecutive_same": max_consecutive,
    }


def analyze_cross_layer(events: list[dict]) -> dict:
    """Cross-layer overlap (already proven in previous analysis, include for completeness)."""
    target_layers: dict[str, set[int]] = defaultdict(set)
    target_timings: dict[str, list[tuple[int, int, int]]] = defaultdict(list)

    for e in events:
        name = e["target_name"]
        layer = e["layer_index"]
        target_layers[name].add(layer)
        target_timings[name].append((e["start_ms"], e["end_ms"], layer))

    total = len(target_layers)
    multi = sum(1 for ls in target_layers.values() if len(ls) > 1)

    simul = 0
    for name, timings in target_timings.items():
        if len(target_layers[name]) <= 1:
            continue
        sorted_t = sorted(timings, key=lambda x: x[0])
        for i in range(len(sorted_t)):
            for j in range(i + 1, len(sorted_t)):
                si, ei, li = sorted_t[i]
                sj, ej, lj = sorted_t[j]
                if sj >= ei:
                    break
                if li != lj:
                    simul += 1
                    break

    return {
        "total_targets": total,
        "multi_layer": multi,
        "multi_layer_pct": round(multi / total * 100, 1) if total else 0,
        "simultaneous_cross": simul,
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

    print("=" * 100)
    print("COMPREHENSIVE RULE VALIDATION AGAINST REAL-WORLD xLights PROFILES")
    print("=" * 100)

    # =====================================================================
    # PART 1: Catalog all enforced rules
    # =====================================================================
    print()
    print("PART 1: ALL ENFORCED RULES (Validator + Judge)")
    print("-" * 100)

    rules = [
        # Schema rules (clearly valid)
        RuleResult("UNKNOWN_GROUP", "SCHEMA", "Target group ID must exist in ChoreographyGraph", False, "N/A", "Data integrity — always valid"),
        RuleResult("UNKNOWN_ZONE", "SCHEMA", "Zone target must be valid ChoreoTag", False, "N/A", "Data integrity — always valid"),
        RuleResult("UNKNOWN_SPLIT", "SCHEMA", "Split target must be valid SplitDimension", False, "N/A", "Data integrity — always valid"),
        RuleResult("UNKNOWN_TEMPLATE", "SCHEMA", "Template must exist in catalog", False, "N/A", "Data integrity — always valid"),
        RuleResult("TEMPLATE_LANE_MISMATCH", "SCHEMA", "Template must be compatible with lane", False, "N/A", "Data integrity — always valid"),
        RuleResult("INVALID_INTENSITY_LEVEL", "SCHEMA", "Intensity must be valid enum", False, "N/A", "Data integrity — always valid"),
        RuleResult("INVALID_DURATION", "SCHEMA", "Duration must be valid enum", False, "N/A", "Data integrity — always valid"),
        RuleResult("INVALID_PLANNING_TIMEREF", "SCHEMA", "Time ref must be resolvable", False, "N/A", "Data integrity — always valid"),
        RuleResult("SEQUENCED_MISSING_WINDOW_CONFIG", "SCHEMA", "SEQUENCED mode requires window+config", False, "N/A", "Structural requirement — always valid"),
        RuleResult("CALL_RESPONSE_MISSING_GROUP_ORDER", "SCHEMA", "CALL_RESPONSE requires group_order", False, "N/A", "Structural requirement — always valid"),
        RuleResult("DUPLICATE_GROUP_ORDER", "SCHEMA", "No duplicates in group_order", False, "N/A", "Data integrity — always valid"),
        RuleResult("SEQUENCED_CONFIG_GROUP_MISMATCH", "SCHEMA", "group_order entries must be in targets", False, "N/A", "Data integrity — always valid"),
        # Timing rules (clearly valid)
        RuleResult("PLACEMENT_OUTSIDE_SECTION", "TIMING", "Placement start must be within section bounds", False, "N/A", "Physical constraint — always valid"),
        RuleResult("WINDOW_OUTSIDE_SECTION", "TIMING", "Window start must be within section bounds", False, "N/A", "Physical constraint — always valid"),
        # Overlap rules (NEED CHECK)
        RuleResult("TARGET_SELF_OVERLAP", "OVERLAP", "Same target must not overlap itself within same lane", True),
        RuleResult("TARGET_SELF_OVERLAP_MINOR", "OVERLAP", "Minor same-target overlap within lane (warning)", True),
        RuleResult("WITHIN_COORDINATION_OVERLAP", "OVERLAP", "Same target must not overlap within same coordination plan", True),
        # Ownership rules (NEED CHECK)
        RuleResult("TARGET_IN_MULTIPLE_COORDINATION_PLANS_IN_LANE", "OWNERSHIP", "Same target must be in only one coordination plan per lane", True),
        # Diversity rules (NEED CHECK)
        RuleResult("INSUFFICIENT_UNIQUE_TEMPLATES", "DIVERSITY", "Minimum unique templates per lane", True),
        RuleResult("TEMPLATE_OVERUSED", "DIVERSITY", "Maximum uses per template", True),
        RuleResult("CONSECUTIVE_REUSE_VIOLATION", "DIVERSITY", "No consecutive same template", True),
        RuleResult("TOP_HEAVY_DISTRIBUTION", "DIVERSITY", "Top 2 templates can't dominate (warning)", True),
        # Judge-only rules (NEED CHECK)
        RuleResult("JUDGE:ACCENT_SELF_OVERLAP_HARD_FAIL", "OVERLAP", "Section judge: ACCENT same-target overlap is automatic HARD_FAIL", True),
        RuleResult("JUDGE:COORD_PLAN_OWNERSHIP_HARD_FAIL", "OWNERSHIP", "Section judge: target in multiple coord plans same lane is HARD_FAIL", True),
        # Warnings (already advisory)
        RuleResult("IDENTICAL_ACCENT_ON_PRIMARIES", "QUALITY", "All primaries with identical accent (warning)", False, "N/A", "Advisory only — already a warning"),
        RuleResult("TIMING_DRIVER_MISMATCH", "QUALITY", "timing_driver doesn't match placements (warning)", False, "N/A", "Advisory only — already a warning"),
    ]

    for r in rules:
        status = r.profile_support if r.profile_support else "CHECKING..."
        print(f"  [{r.category:10s}] {r.rule_code:<50s} {status}")

    # =====================================================================
    # PART 2: Profile analysis
    # =====================================================================
    print()
    print("=" * 100)
    print("PART 2: REAL-WORLD PROFILE ANALYSIS")
    print("=" * 100)

    all_same_layer = []
    all_multi_group = []
    all_diversity = []
    all_cross_layer = []

    for pd in profile_dirs:
        events = load_events(pd)
        if not events:
            continue

        same_layer = analyze_same_layer_overlap(events)
        same_layer["name"] = pd.name
        all_same_layer.append(same_layer)

        multi_group = analyze_multi_effect_groups_same_layer(events)
        multi_group["name"] = pd.name
        all_multi_group.append(multi_group)

        diversity = analyze_effect_diversity(events)
        diversity["name"] = pd.name
        all_diversity.append(diversity)

        cross_layer = analyze_cross_layer(events)
        cross_layer["name"] = pd.name
        all_cross_layer.append(cross_layer)

    # --- Same-layer overlap ---
    print()
    print("TEST: TARGET_SELF_OVERLAP / WITHIN_COORDINATION_OVERLAP")
    print("  Rule: Same target on same layer must not have overlapping time ranges")
    print("-" * 100)
    print(f"  {'Profile':<14} {'Target+Layers':>13} {'Overlapping':>12} {'%':>7} {'Overlaps':>9}")
    print("  " + "-" * 60)

    total_tl = 0
    total_overlap_tl = 0
    total_overlaps = 0
    for r in all_same_layer:
        total_tl += r["total_target_layers"]
        total_overlap_tl += r["overlapping_target_layers"]
        total_overlaps += r["total_overlaps"]
        print(
            f"  {r['name']:<14} {r['total_target_layers']:>13} "
            f"{r['overlapping_target_layers']:>12} {r['overlap_pct']:>6.1f}% "
            f"{r['total_overlaps']:>9}"
        )

    overlap_pct = round(total_overlap_tl / total_tl * 100, 1) if total_tl else 0
    print("  " + "-" * 60)
    print(f"  {'TOTAL':<14} {total_tl:>13} {total_overlap_tl:>12} {overlap_pct:>6.1f}% {total_overlaps:>9}")
    print()
    if overlap_pct > 10:
        print(f"  >> VERDICT: Same-layer self-overlap is COMMON ({overlap_pct}%).")
        print("     Rules TARGET_SELF_OVERLAP and WITHIN_COORDINATION_OVERLAP")
        print("     are NOT supported by real-world practice. REMOVE as errors.")
    elif overlap_pct > 3:
        print(f"  >> VERDICT: Same-layer self-overlap is MODERATE ({overlap_pct}%).")
        print("     Keep as WARNING only.")
    else:
        print(f"  >> VERDICT: Same-layer self-overlap is RARE ({overlap_pct}%).")
        print("     Rule is well-grounded. Keep as ERROR.")

    # Show examples
    for r in all_same_layer:
        if r.get("examples"):
            print(f"\n  Examples from {r['name']}:")
            for ex in r["examples"][:3]:
                print(f"    {ex}")

    # --- Multi-block (ownership analogy) ---
    print()
    print()
    print("TEST: TARGET_IN_MULTIPLE_COORDINATION_PLANS_IN_LANE")
    print("  Rule: Same target must appear in only one coordination plan per lane")
    print("  Proxy: same target has multiple non-contiguous effect blocks on same layer")
    print("-" * 100)
    print(f"  {'Profile':<14} {'Target+Layers':>13} {'Multi-Block':>12} {'%':>7}")
    print("  " + "-" * 45)

    total_tl2 = 0
    total_mb = 0
    for r in all_multi_group:
        total_tl2 += r["total_target_layers"]
        total_mb += r["multi_block_target_layers"]
        print(
            f"  {r['name']:<14} {r['total_target_layers']:>13} "
            f"{r['multi_block_target_layers']:>12} {r['multi_block_pct']:>6.1f}%"
        )

    mb_pct = round(total_mb / total_tl2 * 100, 1) if total_tl2 else 0
    print("  " + "-" * 45)
    print(f"  {'TOTAL':<14} {total_tl2:>13} {total_mb:>12} {mb_pct:>6.1f}%")
    print()
    if mb_pct > 30:
        print(f"  >> VERDICT: Multi-block same-layer targeting is COMMON ({mb_pct}%).")
        print("     Rule TARGET_IN_MULTIPLE_COORDINATION_PLANS_IN_LANE")
        print("     is NOT supported by real-world practice. REMOVE.")
    elif mb_pct > 10:
        print(f"  >> VERDICT: Multi-block same-layer targeting is MODERATE ({mb_pct}%).")
        print("     Downgrade to WARNING.")
    else:
        print(f"  >> VERDICT: Multi-block same-layer targeting is RARE ({mb_pct}%).")
        print("     Rule is well-grounded. Keep.")

    # --- Diversity ---
    print()
    print()
    print("TEST: DIVERSITY RULES (INSUFFICIENT_UNIQUE_TEMPLATES, TEMPLATE_OVERUSED,")
    print("      CONSECUTIVE_REUSE_VIOLATION, TOP_HEAVY_DISTRIBUTION)")
    print("-" * 100)
    print(f"  {'Profile':<14} {'Effects':>8} {'Unique':>7} {'MaxUse':>7} {'Max%':>6} "
          f"{'Top2%':>6} {'MaxConsec':>10}")
    print("  " + "-" * 65)

    for r in all_diversity:
        if not r.get("total_effects"):
            continue
        print(
            f"  {r['name']:<14} {r['total_effects']:>8} {r['unique_effects']:>7} "
            f"{r['max_uses_single']:>7} {r['max_uses_pct']:>5.1f}% "
            f"{r['top2_share']:>5.1f}% {r['max_consecutive_same']:>10}"
        )

    print()
    print("  Context: Our validator constraints are:")
    print("    BASE:   min 5 unique, max 3 uses, max 1 consecutive, top2 <= 50%")
    print("    RHYTHM: min 9 unique, max 2 uses, max 0 consecutive, top2 <= 35%")
    print("    ACCENT: min 8 unique, max 2 uses, max 0 consecutive, top2 <= 35%")
    print()

    # Aggregate diversity stats
    if all_diversity:
        avg_unique = sum(r.get("unique_effects", 0) for r in all_diversity if r.get("total_effects")) / len(
            [r for r in all_diversity if r.get("total_effects")]
        )
        avg_max = sum(r.get("max_uses_single", 0) for r in all_diversity if r.get("total_effects")) / len(
            [r for r in all_diversity if r.get("total_effects")]
        )
        avg_top2 = sum(r.get("top2_share", 0) for r in all_diversity if r.get("total_effects")) / len(
            [r for r in all_diversity if r.get("total_effects")]
        )
        avg_consec = sum(r.get("max_consecutive_same", 0) for r in all_diversity if r.get("total_effects")) / len(
            [r for r in all_diversity if r.get("total_effects")]
        )
        print(f"  Averages: unique={avg_unique:.0f}, max_uses={avg_max:.0f}, "
              f"top2={avg_top2:.1f}%, max_consecutive={avg_consec:.1f}")

    # --- Cross-layer (recap) ---
    print()
    print()
    print("TEST: CROSS-LANE RULES (already proven — recap)")
    print("-" * 100)
    total_targets_cl = sum(r["total_targets"] for r in all_cross_layer)
    total_multi_cl = sum(r["multi_layer"] for r in all_cross_layer)
    cl_pct = round(total_multi_cl / total_targets_cl * 100, 1) if total_targets_cl else 0
    print(f"  {cl_pct}% of targets appear on multiple layers (already removed)")

    # =====================================================================
    # PART 3: Final verdict
    # =====================================================================
    print()
    print("=" * 100)
    print("PART 3: FINAL RULE VERDICTS")
    print("=" * 100)
    print()
    print(f"  {'Rule Code':<55s} {'Category':10s} {'Verdict':15s}")
    print("  " + "-" * 82)

    schema_rules = [r for r in rules if not r.needs_profile_check]
    check_rules = [r for r in rules if r.needs_profile_check]

    for r in schema_rules:
        print(f"  {r.rule_code:<55s} {r.category:10s} {'KEEP':15s}")

    # Assign verdicts based on analysis
    for r in check_rules:
        if r.category == "OVERLAP":
            if overlap_pct > 10:
                r.profile_support = "CONTRADICTED"
                r.evidence = f"{overlap_pct}% same-layer overlap rate"
                verdict = "REMOVE"
            elif overlap_pct > 3:
                r.profile_support = "WEAK"
                verdict = "WARN ONLY"
            else:
                r.profile_support = "SUPPORTED"
                verdict = "KEEP"
        elif r.category == "OWNERSHIP":
            if mb_pct > 30:
                r.profile_support = "CONTRADICTED"
                r.evidence = f"{mb_pct}% multi-block rate"
                verdict = "REMOVE"
            elif mb_pct > 10:
                r.profile_support = "WEAK"
                verdict = "WARN ONLY"
            else:
                r.profile_support = "SUPPORTED"
                verdict = "KEEP"
        elif r.category == "DIVERSITY":
            r.profile_support = "CHECK_ABOVE"
            verdict = "SEE STATS"
        else:
            verdict = "CHECK"

        print(f"  {r.rule_code:<55s} {r.category:10s} {verdict:15s}")

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()
