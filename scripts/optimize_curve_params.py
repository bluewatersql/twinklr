#!/usr/bin/env python3
"""Optimize curve parameters by intensity level.

Evaluates amplitude and frequency combinations for each curve type to find
optimal settings that align with intensity target behaviors:

- SLOW: 1/2 speed (0.5x frequency)
- SMOOTH: Baseline (1.0x frequency, reference point)
- FAST: 1 1/4 speed (1.25x frequency)
- DRAMATIC: 1 1/2 speed (1.5x frequency)
- INTENSE: Max effect (2.0x frequency, max amplitude)

Generates a markdown report with recommended parameters per curve type.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.curves.adapters import build_default_adapter_registry
from twinklr.core.curves.library import CurveLibrary, build_default_registry
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementCategoricalParams

if TYPE_CHECKING:
    from twinklr.core.curves.models import CurvePoint
    from twinklr.core.curves.semantics import CurveKind


@dataclass
class CurveMetrics:
    """Metrics for evaluating curve quality."""

    energy: float  # Average rate of change (speed)
    range: float  # Value range (max - min)
    mean: float  # Average value
    variance: float  # Variance from mean
    peak_velocity: float  # Maximum rate of change
    smoothness: float  # Inverse of jerkiness


@dataclass
class IntensityTarget:
    """Target behavior for an intensity level."""

    name: str
    frequency_multiplier: float  # Relative to SMOOTH
    amplitude_min: float  # Minimum acceptable amplitude
    amplitude_max: float  # Maximum acceptable amplitude
    energy_target: float  # Target energy level


# Define intensity targets based on user requirements
INTENSITY_TARGETS = {
    Intensity.SLOW: IntensityTarget(
        name="SLOW",
        frequency_multiplier=0.5,  # 1/2 speed
        amplitude_min=0.2,
        amplitude_max=0.4,
        energy_target=0.3,
    ),
    Intensity.SMOOTH: IntensityTarget(
        name="SMOOTH",
        frequency_multiplier=1.0,  # Baseline
        amplitude_min=0.4,
        amplitude_max=0.6,
        energy_target=0.5,
    ),
    Intensity.FAST: IntensityTarget(
        name="FAST",
        frequency_multiplier=1.25,  # 1 1/4 speed
        amplitude_min=0.6,
        amplitude_max=0.8,
        energy_target=0.7,
    ),
    Intensity.DRAMATIC: IntensityTarget(
        name="DRAMATIC",
        frequency_multiplier=1.5,  # 1 1/2 speed
        amplitude_min=0.7,
        amplitude_max=0.9,
        energy_target=0.85,
    ),
    Intensity.INTENSE: IntensityTarget(
        name="INTENSE",
        frequency_multiplier=2.0,  # Max 100% effect
        amplitude_min=0.9,
        amplitude_max=1.0,
        energy_target=1.0,
    ),
}


def calculate_metrics(points: list[CurvePoint]) -> CurveMetrics:
    """Calculate curve quality metrics.

    Args:
        points: Curve samples to analyze

    Returns:
        CurveMetrics with computed statistics
    """
    if len(points) < 2:
        return CurveMetrics(
            energy=0.0,
            range=0.0,
            mean=0.5,
            variance=0.0,
            peak_velocity=0.0,
            smoothness=1.0,
        )

    values = [p.v for p in points]
    times = [p.t for p in points]

    # Basic stats
    v_min = min(values)
    v_max = max(values)
    v_range = v_max - v_min
    v_mean = sum(values) / len(values)

    # Variance
    variance = sum((v - v_mean) ** 2 for v in values) / len(values)

    # Velocity (rate of change)
    velocities = []
    for i in range(1, len(points)):
        dt = times[i] - times[i - 1]
        dv = abs(values[i] - values[i - 1])
        if dt > 0:
            velocities.append(dv / dt)
        else:
            velocities.append(0.0)

    avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0
    peak_velocity = max(velocities) if velocities else 0.0

    # Normalize energy to [0, 1] based on theoretical max velocity
    # Max velocity for a sine wave is 2*pi*frequency*amplitude / sample_count
    # For general curves, normalize by range and sample density
    sample_density = len(points)
    theoretical_max = v_range * sample_density if v_range > 0 else 1.0
    normalized_energy = avg_velocity / theoretical_max if theoretical_max > 0 else 0.0
    normalized_energy = min(1.0, normalized_energy)  # Clamp to [0, 1]

    # Smoothness (inverse of jerk - acceleration changes)
    accelerations = []
    for i in range(1, len(velocities)):
        da = abs(velocities[i] - velocities[i - 1])
        accelerations.append(da)

    jerkiness = sum(accelerations) / len(accelerations) if accelerations else 0.0
    smoothness = 1.0 / (1.0 + jerkiness * 10)  # Scale jerkiness for better distribution

    return CurveMetrics(
        energy=normalized_energy,
        range=v_range,
        mean=v_mean,
        variance=variance,
        peak_velocity=peak_velocity,
        smoothness=smoothness,
    )


def score_params(
    metrics: CurveMetrics,
    target: IntensityTarget,
    amplitude: float,
) -> float:
    """Score parameter combination against target.

    Args:
        metrics: Computed curve metrics
        target: Target intensity behavior
        amplitude: Amplitude used

    Returns:
        Score [0, 1] where 1 is perfect match
    """
    # Energy alignment (most important)
    energy_error = abs(metrics.energy - target.energy_target)
    energy_score = max(0.0, 1.0 - energy_error / target.energy_target)

    # Amplitude in target range
    amp_in_range = target.amplitude_min <= amplitude <= target.amplitude_max
    amp_score = 1.0 if amp_in_range else 0.5

    # Range utilization (should use available amplitude)
    range_target = amplitude * 0.8  # Expect ~80% of amplitude to be used
    range_error = abs(metrics.range - range_target)
    range_score = max(0.0, 1.0 - range_error / amplitude)

    # Smoothness (prefer smooth curves)
    smoothness_score = metrics.smoothness

    # Weighted combination
    score = (
        energy_score * 0.5  # Energy most important
        + amp_score * 0.2  # Amplitude range
        + range_score * 0.2  # Range utilization
        + smoothness_score * 0.1  # Smoothness
    )

    return score


@dataclass
class ParamResult:
    """Result of testing a parameter combination."""

    amplitude: float
    frequency: float
    metrics: CurveMetrics
    score: float


def test_curve_params(
    curve_id: CurveLibrary,
    intensity: Intensity,
    n_samples: int = 128,
    debug: bool = False,
) -> ParamResult:
    """Test parameter combinations for a curve at an intensity level.

    Uses Phase 3 adapter system to translate categorical params to curve-specific params.

    Args:
        curve_id: Curve to test
        intensity: Intensity level to optimize for
        n_samples: Number of samples for evaluation
        debug: Enable debug output

    Returns:
        Best parameter combination and metrics
    """
    registry = build_default_registry()
    adapter_registry = build_default_adapter_registry()
    target = INTENSITY_TARGETS[intensity]

    # Define test grid - expand search space
    amplitude_step = (target.amplitude_max - target.amplitude_min) / 4
    amplitude_values = [
        target.amplitude_min,
        target.amplitude_min + amplitude_step,
        (target.amplitude_min + target.amplitude_max) / 2,
        target.amplitude_max - amplitude_step,
        target.amplitude_max,
    ]

    # Test frequencies around the target - wider range
    frequency_values = [
        target.frequency_multiplier * 0.7,
        target.frequency_multiplier * 0.85,
        target.frequency_multiplier,
        target.frequency_multiplier * 1.15,
        target.frequency_multiplier * 1.3,
    ]

    best_result: ParamResult | None = None
    best_score = -1.0

    # Get curve definition to check default params
    definition = registry.get(curve_id.value)
    if not definition:
        if debug:
            print(f"    WARNING: Curve {curve_id.value} not found in registry")
        return _fallback_result(target)

    for amplitude in amplitude_values:
        for frequency in frequency_values:
            # Generate curve with test parameters using adapter system
            try:
                # Create categorical params object
                categorical = MovementCategoricalParams(
                    amplitude=amplitude,
                    frequency=frequency,
                    center_offset=0.5,  # Neutral center
                )

                # Resolve curve using adapter system (Phase 3)
                # This automatically handles pulse → high/low, bezier scaling, etc.
                points = registry.resolve(
                    definition=definition,
                    n_samples=n_samples,
                    categorical_params=categorical,
                    adapter_registry=adapter_registry,
                )

                if not points or len(points) < 2:
                    if debug:
                        print(f"    WARNING: No points generated for {curve_id.value}")
                    continue

                metrics = calculate_metrics(points)
                score = score_params(metrics, target, amplitude)

                if score > best_score:
                    best_score = score
                    best_result = ParamResult(
                        amplitude=amplitude,
                        frequency=frequency,
                        metrics=metrics,
                        score=score,
                    )

            except TypeError as e:
                # Curve doesn't support these parameters - skip silently
                if debug:
                    print(f"    DEBUG: {curve_id.value} doesn't support params: {e}")
                continue
            except Exception as e:
                # Other error - log and skip
                if debug:
                    print(f"    ERROR: {curve_id.value} failed: {e}")
                continue

    # Fallback if no results
    if best_result is None:
        if debug:
            print(f"    WARNING: No valid parameter combinations found for {curve_id.value}")
        return _fallback_result(target)

    return best_result


def _fallback_result(target: IntensityTarget) -> ParamResult:
    """Create fallback result when testing fails.

    Args:
        target: Intensity target

    Returns:
        ParamResult with default values and zero score
    """
    return ParamResult(
        amplitude=target.amplitude_max,
        frequency=target.frequency_multiplier,
        metrics=CurveMetrics(
            energy=0.0,
            range=0.0,
            mean=0.5,
            variance=0.0,
            peak_velocity=0.0,
            smoothness=0.0,
        ),
        score=0.0,
    )


def get_testable_curves() -> list[tuple[CurveLibrary, CurveKind]]:
    """Get list of curves that support amplitude/frequency parameters.

    With Phase 3 adapter system, more curves are now testable as adapters
    handle translation of categorical params to curve-specific params.

    Returns:
        List of (curve_id, curve_kind) tuples
    """
    registry = build_default_registry()

    testable_curves = []

    # Movement curves - primary focus (Phase 3: all use adapters)
    movement_curves = [
        CurveLibrary.MOVEMENT_SINE,
        CurveLibrary.MOVEMENT_TRIANGLE,
        CurveLibrary.MOVEMENT_COSINE,
        CurveLibrary.MOVEMENT_PULSE,  # Adapter: amplitude → high/low
        CurveLibrary.MOVEMENT_LISSAJOUS,  # Adapter: frequency → a/b ratio (NEW)
        CurveLibrary.MOVEMENT_PERLIN_NOISE,  # Adapter: amplitude/frequency scaling (NEW)
    ]

    # Wave curves (used in dimmers and movements)
    wave_curves = [
        CurveLibrary.SINE,
        CurveLibrary.PULSE,  # Adapter: amplitude → high/low
        CurveLibrary.COSINE,
        CurveLibrary.TRIANGLE,
    ]

    # Parametric curves (Phase 5: now testable with adapters)
    parametric_curves = [
        CurveLibrary.BEZIER,  # Adapter: amplitude → control point scaling (NEW)
        CurveLibrary.LISSAJOUS,  # Adapter: frequency → a/b ratio (NEW)
    ]

    # Dynamic curves - skip bounce/elastic as they have fixed behavior
    # These don't accept intensity params and use fixed algorithms
    dynamic_curves: list[CurveLibrary] = []

    all_curves = movement_curves + wave_curves + parametric_curves + dynamic_curves

    for curve_id in all_curves:
        definition = registry.get(curve_id.value)
        if definition:
            testable_curves.append((curve_id, definition.kind))

    return testable_curves


def generate_report(results: dict[CurveLibrary, dict[Intensity, ParamResult]], output_path: Path):
    """Generate markdown report with optimization results.

    Args:
        results: Nested dict of curve -> intensity -> result
        output_path: Path to write report
    """
    lines = []

    lines.append("# Curve Parameter Optimization Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(
        "This report presents optimized amplitude and frequency parameters for each curve type"
    )
    lines.append("across intensity levels. Parameters are tuned to achieve target behaviors:")
    lines.append("")
    lines.append("| Intensity | Speed | Amplitude Range | Target Energy |")
    lines.append("|-----------|-------|-----------------|---------------|")

    for intensity in [
        Intensity.SLOW,
        Intensity.SMOOTH,
        Intensity.FAST,
        Intensity.DRAMATIC,
        Intensity.INTENSE,
    ]:
        target = INTENSITY_TARGETS[intensity]
        lines.append(
            f"| **{target.name}** | {target.frequency_multiplier}x | "
            f"{target.amplitude_min:.2f}-{target.amplitude_max:.2f} | "
            f"{target.energy_target:.2f} |"
        )

    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("For each curve and intensity level:")
    lines.append("1. Test grid of amplitude/frequency combinations")
    lines.append("2. Calculate metrics: energy, range, smoothness, peak velocity")
    lines.append("3. Score against intensity target (0-1, higher is better)")
    lines.append("4. Select best-scoring parameters")
    lines.append("")
    lines.append("**Score Weights:**")
    lines.append("- Energy alignment: 50%")
    lines.append("- Amplitude range: 20%")
    lines.append("- Range utilization: 20%")
    lines.append("- Smoothness: 10%")
    lines.append("")

    lines.append("## Results by Curve Type")
    lines.append("")

    # Group curves by category (Phase 5: added parametric and noise curves)
    movement_curves = [
        CurveLibrary.MOVEMENT_SINE,
        CurveLibrary.MOVEMENT_TRIANGLE,
        CurveLibrary.MOVEMENT_PULSE,
        CurveLibrary.MOVEMENT_COSINE,
        CurveLibrary.MOVEMENT_LISSAJOUS,  # NEW: Parametric
        CurveLibrary.MOVEMENT_PERLIN_NOISE,  # NEW: Noise
    ]

    wave_curves = [
        CurveLibrary.SINE,
        CurveLibrary.TRIANGLE,
        CurveLibrary.PULSE,
        CurveLibrary.COSINE,
    ]

    parametric_curves = [
        CurveLibrary.BEZIER,  # NEW: Parametric
        CurveLibrary.LISSAJOUS,  # NEW: Parametric
    ]

    dynamic_curves = [
        CurveLibrary.BOUNCE_IN,
        CurveLibrary.BOUNCE_OUT,
        CurveLibrary.ELASTIC_IN,
        CurveLibrary.ELASTIC_OUT,
    ]

    categories = [
        ("Movement Curves", movement_curves),
        ("Wave Curves", wave_curves),
        ("Parametric Curves", parametric_curves),  # NEW: Phase 5
        ("Dynamic Curves", dynamic_curves),
    ]

    for category_name, curve_list in categories:
        lines.append(f"### {category_name}")
        lines.append("")

        for curve_id in curve_list:
            if curve_id not in results:
                continue

            lines.append(f"#### {curve_id.value.upper()}")
            lines.append("")
            lines.append("| Intensity | Amplitude | Frequency | Energy | Range | Score |")
            lines.append("|-----------|-----------|-----------|--------|-------|-------|")

            curve_results = results[curve_id]
            for intensity in [
                Intensity.SLOW,
                Intensity.SMOOTH,
                Intensity.FAST,
                Intensity.DRAMATIC,
                Intensity.INTENSE,
            ]:
                if intensity not in curve_results:
                    continue

                result = curve_results[intensity]
                lines.append(
                    f"| **{intensity.value}** | "
                    f"{result.amplitude:.3f} | "
                    f"{result.frequency:.3f} | "
                    f"{result.metrics.energy:.3f} | "
                    f"{result.metrics.range:.3f} | "
                    f"{result.score:.3f} |"
                )

            lines.append("")

    lines.append("## Recommended Implementation")
    lines.append("")
    lines.append("### Update Movement Library")
    lines.append("")
    lines.append("Replace `DEFAULT_MOVEMENT_PARAMS` in `movement.py` with curve-specific params:")
    lines.append("")
    lines.append("```python")
    lines.append("# Curve-specific intensity parameters")
    lines.append("CURVE_INTENSITY_PARAMS = {")

    for curve_id in movement_curves:
        if curve_id not in results:
            continue

        lines.append(f"    CurveLibrary.{curve_id.name}: {{")

        curve_results = results[curve_id]
        for intensity in [
            Intensity.SLOW,
            Intensity.SMOOTH,
            Intensity.FAST,
            Intensity.DRAMATIC,
            Intensity.INTENSE,
        ]:
            if intensity not in curve_results:
                continue

            result = curve_results[intensity]
            lines.append(
                f"        Intensity.{intensity.name}: MovementCategoricalParams("
                f"amplitude={result.amplitude:.3f}, "
                f"frequency={result.frequency:.3f}, "
                f"center_offset=0.5),"
            )

        lines.append("    },")

    lines.append("}")
    lines.append("```")
    lines.append("")

    lines.append("### Key Insights")
    lines.append("")

    # Analyze variance across curves
    intensity_levels = [
        Intensity.SLOW,
        Intensity.SMOOTH,
        Intensity.FAST,
        Intensity.DRAMATIC,
        Intensity.INTENSE,
    ]

    for intensity in intensity_levels:
        target = INTENSITY_TARGETS[intensity]
        amplitudes = []
        frequencies = []

        for curve_id in results:
            if intensity in results[curve_id]:
                result = results[curve_id][intensity]
                amplitudes.append(result.amplitude)
                frequencies.append(result.frequency)

        if amplitudes and frequencies:
            avg_amp = sum(amplitudes) / len(amplitudes)
            avg_freq = sum(frequencies) / len(frequencies)
            amp_variance = sum((a - avg_amp) ** 2 for a in amplitudes) / len(amplitudes)
            freq_variance = sum((f - avg_freq) ** 2 for f in frequencies) / len(frequencies)

            lines.append(f"**{target.name}:**")
            lines.append(f"- Average amplitude: {avg_amp:.3f} (σ²={amp_variance:.4f})")
            lines.append(f"- Average frequency: {avg_freq:.3f} (σ²={freq_variance:.4f})")

            if amp_variance > 0.01:
                lines.append("  - ⚠️ High amplitude variance - curves need different settings")
            if freq_variance > 0.01:
                lines.append("  - ⚠️ High frequency variance - curves need different settings")

            lines.append("")

    lines.append("### Migration Path")
    lines.append("")
    lines.append(
        "1. **Phase 1**: Add `CURVE_INTENSITY_PARAMS` alongside existing `DEFAULT_MOVEMENT_PARAMS`"
    )
    lines.append("2. **Phase 2**: Update movement handlers to check curve-specific params first")
    lines.append("3. **Phase 3**: Migrate all templates to use curve-specific params")
    lines.append("4. **Phase 4**: Remove global defaults, require explicit curve params")
    lines.append("")

    lines.append("## Validation")
    lines.append("")
    lines.append("To validate these parameters:")
    lines.append("1. Run evaluation on test sequence with each intensity level")
    lines.append("2. Compare energy/range metrics against targets")
    lines.append("3. Visual inspection of rendered curves")
    lines.append("4. Iterate on outliers (score < 0.7)")
    lines.append("")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))

    print(f"Report written to: {output_path}")


def main():
    """Run curve parameter optimization."""
    parser = argparse.ArgumentParser(description="Optimize curve parameters by intensity level")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("changes/vnext/optimization/curve_optimization.md"),
        help="Output markdown report path",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=128,
        help="Number of samples for evaluation",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )

    args = parser.parse_args()

    print("Starting curve parameter optimization...")
    print(f"Samples per curve: {args.samples}")
    print()

    # Get testable curves
    curves = get_testable_curves()
    print(f"Testing {len(curves)} curves across 5 intensity levels...")
    print()

    # Test all combinations
    results: dict[CurveLibrary, dict[Intensity, ParamResult]] = {}

    for curve_id, _curve_kind in curves:
        print(f"Testing {curve_id.value}...")
        results[curve_id] = {}

        for intensity in [
            Intensity.SLOW,
            Intensity.SMOOTH,
            Intensity.FAST,
            Intensity.DRAMATIC,
            Intensity.INTENSE,
        ]:
            result = test_curve_params(
                curve_id, intensity, n_samples=args.samples, debug=args.debug
            )
            results[curve_id][intensity] = result

            print(
                f"  {intensity.value:10s}: amp={result.amplitude:.3f}, "
                f"freq={result.frequency:.3f}, score={result.score:.3f}"
            )

        print()

    # Generate report
    print("Generating report...")
    generate_report(results, args.output)
    print()
    print("✅ Optimization complete!")


if __name__ == "__main__":
    main()
