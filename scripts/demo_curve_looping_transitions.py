#!/usr/bin/env python3
"""
Curve Looping and Transition Demo

Tests concepts for curve blending and looping within sections:
- Looping: Single curve repeated 3 times
- No transitions: 3 different curves back-to-back
- Crossfade transitions: 3 different curves with smooth blending

Generates visualizations and xLights output files.
"""

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d

# =============================================================================
# Core Data Structures
# =============================================================================


@dataclass
class CurvePoint:
    """A single point on a curve."""

    time: float  # Time in seconds
    value: float  # DMX value (0-255)


# =============================================================================
# Curve Generation Functions
# =============================================================================


def ease_in_out_sine(t: np.ndarray) -> np.ndarray:
    """Smooth acceleration and deceleration."""
    result = -(np.cos(np.pi * t) - 1) / 2
    return np.asarray(result, dtype=np.float64)


def ease_in_quad(t: np.ndarray) -> np.ndarray:
    """Quadratic ease in - accelerating from zero."""
    result = t * t
    return np.asarray(result, dtype=np.float64)


def triangle_wave(t: np.ndarray) -> np.ndarray:
    """Linear up then down - loop friendly."""
    result = 1 - np.abs(2 * t - 1)
    return np.asarray(result, dtype=np.float64)


def generate_curve(
    curve_func: Callable[[np.ndarray], np.ndarray],
    duration: float,
    min_dmx: float,
    max_dmx: float,
    num_points: int = 100,
) -> list[CurvePoint]:
    """
    Generate a curve from a mathematical function.

    Args:
        curve_func: Function that takes normalized time [0,1] and returns [0,1]
        duration: Duration in seconds
        min_dmx: Minimum DMX value
        max_dmx: Maximum DMX value
        num_points: Number of points in the curve

    Returns:
        List of CurvePoint objects
    """
    t = np.linspace(0, 1, num_points)
    normalized_values = curve_func(t)

    # Scale to DMX range
    dmx_values = min_dmx + (normalized_values * (max_dmx - min_dmx))

    # Convert to absolute time
    absolute_times = t * duration

    return [
        CurvePoint(time=float(absolute_times[i]), value=float(dmx_values[i]))
        for i in range(num_points)
    ]


# =============================================================================
# Curve Manipulation Functions
# =============================================================================


def loop_curve(curve: list[CurvePoint], num_loops: int) -> list[CurvePoint]:
    """
    Repeat a curve multiple times.

    Args:
        curve: Base curve to loop
        num_loops: Number of times to repeat

    Returns:
        Looped curve with adjusted time values
    """
    if not curve:
        return []

    # Get single loop duration
    loop_duration = curve[-1].time

    looped = []
    for loop_idx in range(num_loops):
        offset = loop_idx * loop_duration
        for point in curve:
            looped.append(CurvePoint(time=point.time + offset, value=point.value))

    return looped


def concatenate_curves(curves: list[list[CurvePoint]]) -> list[CurvePoint]:
    """
    Concatenate multiple curves back-to-back without transitions.

    Args:
        curves: List of curves to concatenate

    Returns:
        Single curve with all input curves placed sequentially
    """
    if not curves:
        return []

    result = []
    time_offset = 0.0

    for curve in curves:
        if not curve:
            continue

        # Get duration of this curve
        curve_duration = curve[-1].time - curve[0].time

        # Add points with time offset
        for point in curve:
            result.append(
                CurvePoint(time=point.time - curve[0].time + time_offset, value=point.value)
            )

        # Update offset for next curve
        time_offset += curve_duration

    return result


def crossfade_curves(
    curve_a: list[CurvePoint],
    curve_b: list[CurvePoint],
    fade_start: float,
    fade_end: float,
) -> list[CurvePoint]:
    """
    Crossfade from curve A to curve B using linear interpolation.

    Args:
        curve_a: First curve
        curve_b: Second curve
        fade_start: Start of transition (normalized 0-1)
        fade_end: End of transition (normalized 0-1)

    Returns:
        Blended curve
    """
    # Resample both curves to same number of points
    num_points = max(len(curve_a), len(curve_b))

    # Extract times and values
    times_a = np.array([p.time for p in curve_a])
    values_a = np.array([p.value for p in curve_a])
    times_b = np.array([p.time for p in curve_b])
    values_b = np.array([p.value for p in curve_b])

    # Normalize times to [0, 1]
    t_norm = np.linspace(0, 1, num_points)

    # Interpolate both curves
    interp_a = interp1d(times_a / times_a[-1], values_a, kind="linear", fill_value="extrapolate")
    interp_b = interp1d(times_b / times_b[-1], values_b, kind="linear", fill_value="extrapolate")

    resampled_a = interp_a(t_norm)
    resampled_b = interp_b(t_norm)

    # Calculate total duration
    total_duration = max(times_a[-1], times_b[-1])

    result = []
    for i, t in enumerate(t_norm):
        # Calculate blend factor
        if t < fade_start:
            blend = 0.0  # 100% curve A
        elif t > fade_end:
            blend = 1.0  # 100% curve B
        else:
            # Linear blend in transition region
            blend = (t - fade_start) / (fade_end - fade_start)

        # Blend values
        blended_value = (1 - blend) * resampled_a[i] + blend * resampled_b[i]

        result.append(CurvePoint(time=t * total_duration, value=float(blended_value)))

    return result


def concatenate_with_crossfade(
    curves: list[list[CurvePoint]], transition_duration: float = 0.5
) -> list[CurvePoint]:
    """
    Concatenate curves with crossfade transitions between them.

    Places curves at fixed time boundaries (5s, 10s, 15s) and blends
    in the transition zones WITHOUT changing the total timeline duration.

    Args:
        curves: List of curves to concatenate
        transition_duration: Duration of crossfade in seconds

    Returns:
        Single curve with smooth transitions, same duration as concatenation
    """
    if not curves:
        return []

    if len(curves) == 1:
        return curves[0]

    # Calculate fixed boundaries based on original curve durations
    boundaries = [0.0]
    for curve in curves:
        curve_duration = curve[-1].time - curve[0].time
        boundaries.append(boundaries[-1] + curve_duration)

    result = []

    for curve_idx, curve in enumerate(curves):
        if not curve:
            continue

        curve_start_time = boundaries[curve_idx]
        curve_end_time = boundaries[curve_idx + 1]
        curve_duration = curve_end_time - curve_start_time

        # Determine blend regions for this curve
        blend_in_start = None
        blend_in_end = None
        blend_out_start = None
        blend_out_end = None

        if curve_idx > 0:  # Has previous curve, blend in
            blend_in_start = curve_start_time - transition_duration / 2
            blend_in_end = curve_start_time + transition_duration / 2

        if curve_idx < len(curves) - 1:  # Has next curve, blend out
            blend_out_start = curve_end_time - transition_duration / 2
            blend_out_end = curve_end_time + transition_duration / 2

        # Process all points in this curve
        for point in curve:
            normalized_time = point.time - curve[0].time
            absolute_time = curve_start_time + normalized_time

            # Skip points that are in the blend-in region (handled by previous curve's blend-out)
            if (
                blend_in_start is not None
                and blend_in_end is not None
                and absolute_time < blend_in_end
            ):
                continue

            # Skip points that are in the blend-out region (will be handled in transition)
            if blend_out_start is not None and absolute_time >= blend_out_start:
                continue

            # Add point as-is (in the solid middle region)
            result.append(CurvePoint(time=absolute_time, value=point.value))

        # Create blend-out transition to next curve
        if curve_idx < len(curves) - 1:
            next_curve = curves[curve_idx + 1]

            # Create uniform time samples in the transition region
            num_samples = 50
            if blend_out_start is not None and blend_out_end is not None:
                blend_times = np.linspace(blend_out_start, blend_out_end, num_samples)
            else:
                continue  # Skip if blend times are not set

            # Interpolate current curve
            curr_times = np.array([p.time - curve[0].time + curve_start_time for p in curve])
            curr_values = np.array([p.value for p in curve])
            curr_interp = interp1d(
                curr_times,
                curr_values,
                kind="linear",
                bounds_error=False,
                fill_value=(curr_values[0], curr_values[-1]),
            )

            # Interpolate next curve
            next_times = np.array(
                [p.time - next_curve[0].time + curve_end_time for p in next_curve]
            )
            next_values = np.array([p.value for p in next_curve])
            next_interp = interp1d(
                next_times,
                next_values,
                kind="linear",
                bounds_error=False,
                fill_value=(next_values[0], next_values[-1]),
            )

            # Add blended points
            for t in blend_times:
                # Calculate blend factor (0 = current curve, 1 = next curve)
                raw_blend = (t - blend_out_start) / transition_duration
                # Use smoothstep for smoother transition
                blend_factor = raw_blend * raw_blend * (3.0 - 2.0 * raw_blend)

                # Blend the values
                curr_val = curr_interp(t)
                next_val = next_interp(t)
                blended_value = (1 - blend_factor) * curr_val + blend_factor * next_val

                result.append(CurvePoint(time=float(t), value=float(blended_value)))

    return result


# =============================================================================
# Visualization Functions
# =============================================================================


def plot_curve_comparison(
    curves_dict: dict[str, list[CurvePoint]],
    title: str,
    output_path: Path,
    transition_duration: float = 0.5,
):
    """
    Plot multiple curves for comparison.

    Args:
        curves_dict: Dictionary mapping labels to curves
        title: Plot title
        output_path: Where to save the plot
        transition_duration: Duration of transitions (for marking on plot)
    """
    _fig, axes = plt.subplots(len(curves_dict), 1, figsize=(14, 4 * len(curves_dict)))

    if len(curves_dict) == 1:
        axes = [axes]

    colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"]

    for idx, (label, curve) in enumerate(curves_dict.items()):
        ax = axes[idx]

        times = [p.time for p in curve]
        values = [p.value for p in curve]

        ax.plot(times, values, color=colors[idx % len(colors)], linewidth=2, label=label)
        ax.fill_between(times, 40, values, alpha=0.2, color=colors[idx % len(colors)])

        # Mark transition zones for crossfade scenario
        if "Crossfade" in label:
            # Estimate transition zones (around 5s and 10s marks)
            for boundary in [4.75, 9.5]:  # Approximate boundaries
                ax.axvspan(
                    boundary - transition_duration / 2,
                    boundary + transition_duration / 2,
                    alpha=0.15,
                    color="green",
                    label="Transition Zone" if boundary == 4.75 else "",
                )

        # Mark curve boundaries for non-transition scenario
        elif "Without" in label:
            for boundary in [5.0, 10.0]:
                ax.axvline(
                    boundary,
                    color="orange",
                    linestyle=":",
                    linewidth=2,
                    alpha=0.6,
                    label="Hard Boundary" if boundary == 5.0 else "",
                )

        # Mark loop boundaries
        elif "Looped" in label:
            for boundary in [5.0, 10.0]:
                ax.axvline(
                    boundary,
                    color="green",
                    linestyle=":",
                    linewidth=1,
                    alpha=0.4,
                    label="Loop Boundary" if boundary == 5.0 else "",
                )

        # DMX boundaries
        ax.axhline(40, color="red", linestyle="--", alpha=0.3, linewidth=1, label="Min (40)")
        ax.axhline(200, color="red", linestyle="--", alpha=0.3, linewidth=1, label="Max (200)")
        ax.axhline(0, color="gray", linestyle=":", alpha=0.2, linewidth=1)
        ax.axhline(255, color="gray", linestyle=":", alpha=0.2, linewidth=1)

        ax.set_xlabel("Time (seconds)", fontsize=11)
        ax.set_ylabel("DMX Value", fontsize=11)
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3, linestyle=":")
        ax.set_ylim(-10, 265)
        ax.set_xlim(0, 15)
        ax.legend(loc="upper right", fontsize=9)

    plt.suptitle(title, fontsize=14, fontweight="bold", y=0.995)
    plt.tight_layout(rect=(0, 0, 1, 0.99))
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"✓ Saved plot: {output_path}")
    plt.close()


# =============================================================================
# xLights Output Generation
# =============================================================================


def generate_xlights_effectdb(output_path: Path):
    """
    Generate xLights effectdb XML file.

    This defines the effect types that can be used.
    """
    root = ET.Element("effectdb")
    root.set("version", "1")

    # Define pan/tilt curve effect
    effect = ET.SubElement(root, "effect")
    effect.set("name", "Curve")
    effect.set("description", "Value curve over time")

    # Add parameters
    for param_name, param_type, default in [
        ("curve_type", "choice", "sine"),
        ("duration", "float", "5.0"),
        ("min_value", "int", "40"),
        ("max_value", "int", "200"),
    ]:
        param = ET.SubElement(effect, "parameter")
        param.set("name", param_name)
        param.set("type", param_type)
        param.set("default", default)

    # Write XML
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"✓ Generated effectdb: {output_path}")


def curve_to_xlights_effects(
    curve: list[CurvePoint], channel_name: str, start_time_ms: int = 0
) -> str:
    """
    Convert curve to xLights effect XML string.

    Args:
        curve: Curve to convert
        channel_name: Name of the channel (e.g., 'Pan', 'Tilt')
        start_time_ms: Start time in milliseconds

    Returns:
        XML string for the effect
    """
    if not curve:
        return ""

    duration_ms = int(curve[-1].time * 1000)

    # Build value curve string (time:value pairs, semicolon separated)
    curve_data = ";".join([f"{int(p.time * 1000)}:{int(p.value)}" for p in curve])

    effect = ET.Element("effect")
    effect.set("name", "Curve")
    effect.set("channel", channel_name)
    effect.set("startTime", str(start_time_ms))
    effect.set("endTime", str(start_time_ms + duration_ms))
    effect.set("duration", str(duration_ms))
    effect.set("curve", curve_data)

    return ET.tostring(effect, encoding="unicode")


def generate_xlights_effects(curves_dict: dict[str, list[CurvePoint]], output_path: Path):
    """
    Generate xLights effects XML file.

    Args:
        curves_dict: Dictionary mapping scenario names to curves
        output_path: Where to save the file
    """
    root = ET.Element("effects")
    root.set("version", "1")

    for scenario_name, curve in curves_dict.items():
        # Add effect group
        group = ET.SubElement(root, "effectGroup")
        group.set("name", scenario_name)

        # Add effect for this curve (simulating pan channel)
        effect = ET.SubElement(group, "effect")
        effect.set("name", "Pan Curve")
        effect.set("type", "Curve")
        effect.set("channel", "Pan")
        effect.set("startTime", "0")
        effect.set("endTime", str(int(curve[-1].time * 1000)))

        # Add curve data as value changes
        curve_data = ET.SubElement(effect, "curveData")
        for point in curve:
            pt = ET.SubElement(curve_data, "point")
            pt.set("time", str(int(point.time * 1000)))
            pt.set("value", str(int(point.value)))

    # Write XML
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"✓ Generated effects: {output_path}")


# =============================================================================
# Summary Statistics
# =============================================================================


def print_curve_summary(label: str, curve: list[CurvePoint]):
    """Print summary statistics for a curve."""
    if not curve:
        print(f"\n{label}: EMPTY")
        return

    times = [p.time for p in curve]
    values = [p.value for p in curve]

    print(f"\n{label}:")
    print(f"  Duration: {times[-1] - times[0]:.3f}s")
    print(f"  Points: {len(curve)}")
    print(f"  Value Range: [{min(values):.1f}, {max(values):.1f}]")
    print(f"  Mean Value: {np.mean(values):.1f}")
    print("  First 3 points:")
    for i in range(min(3, len(curve))):
        print(f"    t={curve[i].time:.3f}s, v={curve[i].value:.1f}")
    print("  Last 3 points:")
    for i in range(max(0, len(curve) - 3), len(curve)):
        print(f"    t={curve[i].time:.3f}s, v={curve[i].value:.1f}")


# =============================================================================
# Main Demo
# =============================================================================


def main():
    """Run the curve looping and transition demo."""
    print("=" * 80)
    print("CURVE LOOPING AND TRANSITION DEMO")
    print("=" * 80)

    # Configuration
    CURVE_DURATION = 5.0  # seconds
    TOTAL_DURATION = 15.0  # seconds
    NUM_LOOPS = 3
    MIN_DMX = 40.0
    MAX_DMX = 200.0
    NUM_POINTS = 100
    TRANSITION_DURATION = 1.0  # seconds (increased to show effect better)

    # Output directory
    output_dir = Path(__file__).parent / "output" / "curve_demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nConfiguration:")
    print(f"  Curve duration: {CURVE_DURATION}s")
    print(f"  Total duration: {TOTAL_DURATION}s")
    print(f"  Number of loops: {NUM_LOOPS}")
    print(f"  DMX range: [{MIN_DMX}, {MAX_DMX}]")
    print(f"  Transition duration: {TRANSITION_DURATION}s")
    print(f"  Output directory: {output_dir}")

    # -------------------------------------------------------------------------
    # Generate Base Curves
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GENERATING BASE CURVES")
    print("=" * 80)

    # Curve 1: Triangle (loop-friendly - starts and ends at same value)
    curve_triangle = generate_curve(triangle_wave, CURVE_DURATION, MIN_DMX, MAX_DMX, NUM_POINTS)
    print("✓ Generated Triangle curve (loop-friendly)")

    # Curve 2: Ease in/out sine (smooth acceleration/deceleration)
    curve_sine = generate_curve(ease_in_out_sine, CURVE_DURATION, MIN_DMX, MAX_DMX, NUM_POINTS)
    print("✓ Generated Ease In/Out Sine curve")

    # Curve 3: Ease in quadratic (accelerating)
    curve_quad = generate_curve(ease_in_quad, CURVE_DURATION, MIN_DMX, MAX_DMX, NUM_POINTS)
    print("✓ Generated Ease In Quadratic curve")

    # -------------------------------------------------------------------------
    # Test 1: Looping
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: LOOPING (Triangle curve repeated 3 times)")
    print("=" * 80)

    looped_curve = loop_curve(curve_triangle, NUM_LOOPS)
    print_curve_summary("Looped Triangle", looped_curve)

    # -------------------------------------------------------------------------
    # Test 2: Concatenation without Transitions
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: CONCATENATION WITHOUT TRANSITIONS")
    print("=" * 80)

    concat_no_transition = concatenate_curves([curve_triangle, curve_sine, curve_quad])
    print_curve_summary("Concatenated (no transitions)", concat_no_transition)

    # -------------------------------------------------------------------------
    # Test 3: Concatenation with Crossfade Transitions
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: CONCATENATION WITH CROSSFADE TRANSITIONS")
    print("=" * 80)

    concat_with_transition = concatenate_with_crossfade(
        [curve_triangle, curve_sine, curve_quad], transition_duration=TRANSITION_DURATION
    )
    print_curve_summary("Concatenated (with transitions)", concat_with_transition)

    # -------------------------------------------------------------------------
    # Visualization
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATIONS")
    print("=" * 80)

    # Plot all three scenarios
    scenarios = {
        "1. Looped Triangle (Loop-Friendly)": looped_curve,
        "2. Three Curves Without Transitions": concat_no_transition,
        "3. Three Curves With Crossfade Transitions": concat_with_transition,
    }

    plot_curve_comparison(
        scenarios,
        "Curve Looping and Transition Handling Demo",
        output_dir / "curve_comparison.png",
        transition_duration=TRANSITION_DURATION,
    )

    # -------------------------------------------------------------------------
    # Generate xLights Output
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("GENERATING xLIGHTS OUTPUT")
    print("=" * 80)

    generate_xlights_effectdb(output_dir / "effectdb.xml")
    generate_xlights_effects(scenarios, output_dir / "effects.xml")

    # -------------------------------------------------------------------------
    # Export JSON Data
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("EXPORTING JSON DATA")
    print("=" * 80)

    json_data = {}
    for label, curve in scenarios.items():
        json_data[label] = {
            "duration": curve[-1].time,
            "num_points": len(curve),
            "points": [{"time": p.time, "value": p.value} for p in curve],
        }

    json_path = output_dir / "curves.json"
    with json_path.open("w") as f:
        json.dump(json_data, f, indent=2)
    print(f"✓ Exported JSON data: {json_path}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print(f"\nOutputs saved to: {output_dir}")
    print("\nFiles generated:")
    print("  - curve_comparison.png (visualization)")
    print("  - effectdb.xml (xLights effect definitions)")
    print("  - effects.xml (xLights effects)")
    print("  - curves.json (raw curve data)")

    print("\nKey Findings:")
    print("  ✓ Triangle wave is loop-friendly (seamless repetition)")
    print("  ✓ Concatenation works but creates discontinuities")
    print("  ✓ Crossfade transitions smooth out discontinuities")
    print(f"  ✓ {TRANSITION_DURATION}s transition duration provides smooth blending")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
