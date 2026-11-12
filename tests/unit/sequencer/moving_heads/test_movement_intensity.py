"""Intensity behavior of the default movement handler and the movement library.

P1P-T3 repaired P4-F1 (the handler's `intensity` argument made authoritative),
P4-M6 (`center_curve` translating instead of rescaling) and P4-M5 (the t=1.0
anchor continuing the motion). All three were reverted on 2026-11-12 at the
owner's request, to restore the look accepted in xLights before the clean-up:

- the handler reads intensity from `params.get("intensity", Intensity.SMOOTH)`,
  so the `intensity` argument does not change movement;
- the movement curves are rescaled to full range and closed on their start value.

P4-F1a (every pattern's table covers all five intensities) stays. These tests
pin the restored handler contract, and the authored ladder as reached through
the `params["intensity"]` key, the only route that selects a table entry.
"""

from __future__ import annotations

import itertools

import pytest

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.movement.default import (
    DefaultMovementHandler,
)
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import (
    DEFAULT_MOVEMENT_PARAMS,
    MovementLibrary,
    MovementPattern,
    MovementType,
)

# The ladder the categorical tables are authored against: rising movement energy.
INTENSITY_LADDER = [
    Intensity.SLOW,
    Intensity.SMOOTH,
    Intensity.DRAMATIC,
    Intensity.FAST,
    Intensity.INTENSE,
]

PATTERN_IDS = sorted(MovementLibrary.PATTERNS)

# `hold` and `accent_snap` drive both axes with MOVEMENT_HOLD, so they have no
# excursion to order under the default (non-chaos) geometry.
STATIONARY_PATTERNS = {MovementType.HOLD, MovementType.ACCENT_SNAP}


def generate(
    pattern: MovementPattern,
    intensity: Intensity,
    *,
    params_intensity: Intensity | None = None,
    cycles: float = 2.0,
):
    """Call the handler the way `step_compiler` does, optionally adding the key."""
    params: dict[str, object] = {"movement_pattern": pattern, "geometry": GeometryType.FAN}
    if params_intensity is not None:
        params["intensity"] = params_intensity
    return DefaultMovementHandler().generate(
        params=params,
        n_samples=64,
        cycles=cycles,
        intensity=intensity,
    )


def generate_at(pattern: MovementPattern, intensity: Intensity):
    """Select a table entry the way the restored handler does: via the params key."""
    return generate(pattern, Intensity.SMOOTH, params_intensity=intensity)


def curves(result) -> list[list[float]]:
    return [[p.v for p in c] for c in (result.pan_curve, result.tilt_curve) if c]


def total_variation(values: list[float]) -> float:
    """Curve energy: the distance the head actually travels over the segment."""
    return sum(abs(values[i + 1] - values[i]) for i in range(len(values) - 1))


def excursion(values: list[float]) -> float:
    return max(values) - min(values)


class TestParamsKeySelectsIntensity:
    """P4-F1 reverted: `params["intensity"]`, defaulting to SMOOTH, decides movement."""

    def test_params_key_beats_the_argument(self) -> None:
        """A `params["intensity"]` key decides the curve whatever the argument says."""
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        key_slow_arg_intense = generate(pattern, Intensity.INTENSE, params_intensity=Intensity.SLOW)
        key_slow_arg_slow = generate(pattern, Intensity.SLOW, params_intensity=Intensity.SLOW)
        key_intense = generate(pattern, Intensity.SLOW, params_intensity=Intensity.INTENSE)

        slow_values = [p.v for p in key_slow_arg_slow.pan_curve]
        assert [p.v for p in key_slow_arg_intense.pan_curve] == slow_values
        assert [p.v for p in key_intense.pan_curve] != slow_values

    def test_without_the_key_movement_renders_at_smooth(self) -> None:
        """Production never sets the key, so every step renders the SMOOTH entry."""
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        assert curves(generate(pattern, Intensity.INTENSE)) == curves(
            generate_at(pattern, Intensity.SMOOTH)
        )


class TestCategoricalParamsCoverage:
    """P4-F1a: the library resolves for every pattern at every intensity."""

    def test_every_declared_table_covers_all_five_intensities(self) -> None:
        """No pattern may rely on a fallback to stay renderable."""
        incomplete = {
            pattern.id: sorted(
                i.value for i in INTENSITY_LADDER if i not in pattern.categorical_params
            )
            for pattern in MovementLibrary.PATTERNS.values()
            if pattern.categorical_params
        }
        assert {k: v for k, v in incomplete.items() if v} == {}

    def test_pattern_census_is_unchanged(self) -> None:
        """29 patterns; the 2 without a table fall back to a complete default."""
        patterns = list(MovementLibrary.PATTERNS.values())
        assert len(patterns) == 29
        assert sum(1 for p in patterns if p.categorical_params) == 27
        assert set(DEFAULT_MOVEMENT_PARAMS) == set(INTENSITY_LADDER)

    def test_all_patterns_all_intensities_resolve(self) -> None:
        """29 patterns x 5 intensities = 145 calls, zero exceptions."""
        calls = 0
        for pattern_id in PATTERN_IDS:
            pattern = MovementLibrary.PATTERNS[pattern_id]
            table = pattern.categorical_params or DEFAULT_MOVEMENT_PARAMS
            for intensity in INTENSITY_LADDER:
                assert intensity in table, f"{pattern.id} has no {intensity.value} entry"
                result = generate_at(pattern, intensity)
                assert result.pan_curve or result.pan_static_dmx is not None
                calls += 1
        assert calls == 145


@pytest.mark.parametrize("pattern_id", PATTERN_IDS, ids=lambda p: p.value)
class TestPerPatternIntensityBehavior:
    """The restored handler contract, and the ladder every pattern's table authors."""

    def test_intensity_argument_does_not_change_the_movement(
        self, pattern_id: MovementType
    ) -> None:
        """P4-F1 reverted: every intensity argument renders the same curves."""
        pattern = MovementLibrary.PATTERNS[pattern_id]
        rendered = [curves(generate(pattern, intensity)) for intensity in INTENSITY_LADDER]

        assert all(result == rendered[0] for result in rendered[1:])

    def test_intensity_monotonic_curve_energy(self, pattern_id: MovementType) -> None:
        """Higher table entry means more travel: SLOW <= ... <= INTENSE."""
        pattern = MovementLibrary.PATTERNS[pattern_id]
        energies = [
            sum(total_variation(values) for values in curves(generate_at(pattern, intensity)))
            for intensity in INTENSITY_LADDER
        ]

        for step, (lower, upper) in enumerate(itertools.pairwise(INTENSITY_LADDER)):
            low, high = energies[step], energies[step + 1]
            assert low <= high + 1e-9, f"{pattern.id}: {lower.value} > {upper.value} ({energies})"

        if pattern_id not in STATIONARY_PATTERNS:
            assert energies[0] < energies[-1], f"{pattern.id}: SLOW and INTENSE tie ({energies})"

    def test_slow_excursion_less_than_intense_excursion(self, pattern_id: MovementType) -> None:
        """Sanity ordering of the authored tables' amplitudes."""
        if pattern_id in STATIONARY_PATTERNS:
            pytest.skip("both axes hold position under the default geometry")

        pattern = MovementLibrary.PATTERNS[pattern_id]
        slow = max(excursion(v) for v in curves(generate_at(pattern, Intensity.SLOW)))
        intense = max(excursion(v) for v in curves(generate_at(pattern, Intensity.INTENSE)))
        assert slow < intense, f"{pattern.id}: SLOW swings {slow:.3f} vs INTENSE {intense:.3f}"
