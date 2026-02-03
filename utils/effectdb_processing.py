#!/usr/bin/env python3
"""
Analyze xLights Effect Events JSON
Processes base_effect_events.json to extract effect types, parameters, and statistics
"""

from collections import Counter, defaultdict
import contextlib
import json
from pathlib import Path
import statistics
from typing import Any


def parse_effectdb_settings(settings_str: str) -> dict[str, str]:
    """Parse effectdb_settings string into parameter dictionary"""
    if not settings_str:
        return {}

    params = {}
    # Split on commas, but be careful of escaped commas (&comma;)
    parts = settings_str.split(",")

    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            params[key.strip()] = value.strip()

    return params


def infer_type(value: str) -> str:
    """Infer the data type of a parameter value"""
    if not value or value == "":
        return "empty"

    # Try int
    try:
        int(value)
        return "int"
    except ValueError:
        pass

    # Try float
    try:
        float(value)
        return "float"
    except ValueError:
        pass

    # Check bool
    if value.lower() in ("true", "false", "0", "1"):
        return "bool"

    return "string"


def is_high_cardinality_param(param_name: str, values: list[str], num_instances: int) -> bool:
    """
    Determine if a parameter should be excluded due to high cardinality
    Excludes: text, font, file, palette, and params with unique value per instance
    """
    param_lower = param_name.lower()

    # Exclude known high-cardinality parameter types
    exclude_keywords = [
        "text",
        "font",
        "file",
        "palette",
        "path",
        "definition",
        "timing",
        "track",
        "data",
        "label",
        "description",
    ]

    if any(keyword in param_lower for keyword in exclude_keywords):
        return True

    # If cardinality > 50% of instances, it's likely high cardinality
    unique_values = len(set(values))
    return bool(unique_values > num_instances * 0.5 and unique_values > 20)


def filter_parameter(param_name: str) -> bool:
    """Filter out parameters that are not relevant to the analysis"""
    return param_name == "BufferStyle" or param_name.find("DMX") >= 0 or param_name.startswith("MH")


def analyze_effects(json_file: Path) -> dict[str, Any]:
    """Main analysis function"""

    with json_file.open("r") as f:
        data = json.load(f)

    events = data.get("events", [])

    # Initialize collectors
    effect_types = set()
    effect_params = defaultdict(
        lambda: {"buffer_styles": set(), "other_params": defaultdict(list), "durations_ms": []}
    )

    # Process each event
    for event in events:
        effect_type = event.get("effect_type", "Unknown")
        effect_types.add(effect_type)

        start_ms = event.get("start_ms", 0)
        end_ms = event.get("end_ms", 0)
        duration_ms = end_ms - start_ms

        effectdb_settings = event.get("effectdb_settings", "")
        params = parse_effectdb_settings(effectdb_settings)

        # Extract BufferStyle
        buffer_style = params.get("BufferStyle", "default")
        effect_params[effect_type]["buffer_styles"].add(buffer_style)
        effect_params[effect_type]["durations_ms"].append(duration_ms)

        # Process other parameters (excluding BufferStyle)
        for param_name, param_value in params.items():
            if not filter_parameter(param_name):
                effect_params[effect_type]["other_params"][param_name].append(param_value)

    # Build results
    results = {
        "summary": {
            "total_events": len(events),
            "distinct_effect_types": len(effect_types),
            "effect_types": sorted(effect_types),
        },
        "effect_details": {},
    }

    # Process each effect type
    for effect_type in sorted(effect_types):
        details = effect_params[effect_type]

        durations = details["durations_ms"]
        if durations:
            duration_stats = {
                "min_ms": min(durations),
                "max_ms": max(durations),
                "avg_ms": statistics.mean(durations),
                "median_ms": statistics.median(durations),
                "count": len(durations),
            }
        else:
            duration_stats = {"min_ms": 0, "max_ms": 0, "avg_ms": 0, "median_ms": 0, "count": 0}

        # Build parameter dictionary for this effect type
        parameter_dict = {}
        for param_name in sorted(details["other_params"].keys()):
            values = details["other_params"][param_name]

            # Skip high cardinality parameters
            if is_high_cardinality_param(param_name, values, len(durations)):
                continue

            # Determine primary type
            type_counts = Counter()
            for v in values:
                param_type = infer_type(v)
                type_counts[param_type] += 1

            primary_type = type_counts.most_common(1)[0][0]

            param_profile = {"type": primary_type, "count": len(values)}

            # Add value profile based on type
            if primary_type in ("int", "float"):
                numeric_values = []
                for v in values:
                    with contextlib.suppress(ValueError, TypeError):
                        numeric_values.append(float(v))

                if numeric_values:
                    param_profile["value_profile"] = {
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": statistics.mean(numeric_values),
                        "median": statistics.median(numeric_values),
                    }
            elif primary_type in ("string", "bool"):
                # Get distinct values for categorical
                distinct_values = list(set(values))
                # Only include if reasonable number of distinct values
                if len(distinct_values) <= 50:
                    param_profile["value_profile"] = {
                        "distinct_values": sorted(distinct_values),
                        "distinct_count": len(distinct_values),
                    }

            parameter_dict[param_name] = param_profile

        results["effect_details"][effect_type] = {
            "buffer_styles": sorted(details["buffer_styles"]),
            "parameter_names": sorted(details["other_params"].keys()),
            "duration_stats": duration_stats,
            "instance_count": len(durations),
            "parameters": parameter_dict,
        }

    return results


def print_results(results: dict[str, Any]):
    """Pretty print the analysis results"""

    print("=" * 80)
    print("XLIGHTS EFFECT EVENTS ANALYSIS")
    print("=" * 80)

    # Summary
    summary = results["summary"]
    print("\nSUMMARY:")
    print(f"  Total Events: {summary['total_events']:,}")
    print(f"  Distinct Effect Types: {summary['distinct_effect_types']}")

    # Effect Types
    print("\nEFFECT TYPES:")
    for i, effect_type in enumerate(summary["effect_types"], 1):
        print(f"  {i:2d}. {effect_type}")

    # Effect Details
    print(f"\n{'=' * 80}")
    print("EFFECT TYPE DETAILS")
    print("=" * 80)

    for effect_type, details in sorted(results["effect_details"].items()):
        print(f"\n{effect_type}:")
        print(f"  Instances: {details['instance_count']}")
        print(f"  Buffer Styles: {', '.join(details['buffer_styles'])}")

        duration = details["duration_stats"]
        print("  Duration (ms):")
        print(f"    Min: {duration['min_ms']:,.0f}")
        print(f"    Max: {duration['max_ms']:,.0f}")
        print(f"    Avg: {duration['avg_ms']:,.0f}")
        print(f"    Median: {duration['median_ms']:,.0f}")

        if details["parameter_names"]:
            print(f"  Parameters ({len(details['parameter_names'])}):")
            for param in details["parameter_names"]:
                print(f"    - {param}")

        # Print parameter profiles
        if details.get("parameters"):
            print(f"\n  Parameter Profiles ({len(details['parameters'])}):")
            for param_name, param_info in sorted(details["parameters"].items()):
                print(f"\n    {param_name}:")
                print(f"      Type: {param_info['type']}")
                print(f"      Count: {param_info['count']}")

                if "value_profile" in param_info:
                    profile = param_info["value_profile"]
                    if param_info["type"] in ("int", "float"):
                        print("      Value Range:")
                        print(f"        Min: {profile['min']}")
                        print(f"        Max: {profile['max']}")
                        print(f"        Avg: {profile['avg']:.2f}")
                        print(f"        Median: {profile['median']:.2f}")
                    elif "distinct_values" in profile:
                        print(f"      Distinct Values ({profile['distinct_count']}):")
                        for val in profile["distinct_values"][:5]:  # Show first 5
                            print(f"        - {val}")
                        if profile["distinct_count"] > 5:
                            print(f"        ... and {profile['distinct_count'] - 5} more")


def save_results(results: dict[str, Any], output_file: Path):
    """Save results to JSON file"""
    with output_file.open("w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    input_file = repo_root / Path("data/test/base_effect_events.json")
    output_file = repo_root / Path("data/test/effect_analysis_results.json")

    print(f"Processing: {input_file}")
    print(f"File size: {input_file.stat().st_size / 1024 / 1024:.2f} MB")

    results = analyze_effects(input_file)

    print_results(results)
    save_results(results, output_file)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
