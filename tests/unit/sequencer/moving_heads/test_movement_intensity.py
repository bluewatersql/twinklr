"""Intensity behavior of the default movement handler and the movement library.

These pin the four coupled defects repaired in P1P-T3:

- **P4-F1** — `generate` overwrote its `intensity` argument with
  `params.get("intensity", Intensity.SMOOTH)`. `params` is the step's movement
  params dict, which never carries that key, so every movement in every show
  rendered at SMOOTH whatever the plan asked for.
- **P4-F1a** — only 2 of 29 patterns declared all five intensities, so simply
  honouring the argument raised `KeyError` on 27 of them.
- **P4-M6** — `center_curve` rescaled each sampled window to full range, which
  made physical excursion a function of frequency and inverted the SLOW/SMOOTH
  intent (low intensities are paired with low frequencies).
- **P4-M5** — the t=1.0 anchor carried the curve's *start* value, so most
  segments ended with a full-excursion snap inside the final 1/n.
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


def generate(pattern: MovementPattern, intensity: Intensity, *, cycles: float = 2.0):
    """Call the handler the way `step_compiler` does: intensity as the argument only."""
    return DefaultMovementHandler().generate(
        params={"movement_pattern": pattern, "geometry": GeometryType.FAN},
        n_samples=64,
        cycles=cycles,
        intensity=intensity,
    )


def curves(result) -> list[list[float]]:
    return [[p.v for p in c] for c in (result.pan_curve, result.tilt_curve) if c]


def total_variation(values: list[float]) -> float:
    """Curve energy: the distance the head actually travels over the segment."""
    return sum(abs(values[i + 1] - values[i]) for i in range(len(values) - 1))


def excursion(values: list[float]) -> float:
    return max(values) - min(values)


class TestArgumentIntensityIsAuthoritative:
    """P4-F1: the caller's `intensity` argument reaches pattern resolution."""

    def test_generate_uses_argument_intensity_not_params_key(self) -> None:
        """A conflicting `params["intensity"]` cannot displace the argument.

        The handler used to read intensity out of `params`, which production never
        populates. Passing a contradictory key here proves the lookup is gone: the
        result must track the argument and ignore the key entirely.
        """
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        clean = DefaultMovementHandler().generate(
            params={"movement_pattern": pattern, "geometry": GeometryType.FAN},
            n_samples=64,
            cycles=2.0,
            intensity=Intensity.INTENSE,
        )
        with_conflicting_key = DefaultMovementHandler().generate(
            params={
                "movement_pattern": pattern,
                "geometry": GeometryType.FAN,
                "intensity": Intensity.SLOW,
            },
            n_samples=64,
            cycles=2.0,
            intensity=Intensity.INTENSE,
        )

        assert [p.v for p in with_conflicting_key.pan_curve] == [p.v for p in clean.pan_curve]

    def test_intensity_argument_changes_the_curve(self) -> None:
        """The regression guard: SLOW and INTENSE must not render identically."""
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]
        slow = [p.v for p in generate(pattern, Intensity.SLOW).pan_curve]
        intense = [p.v for p in generate(pattern, Intensity.INTENSE).pan_curve]
        assert slow != intense


class TestCategoricalParamsCoverage:
    """P4-F1a: the library resolves for every pattern at every intensity."""

    def test_every_declared_table_covers_all_five_intensities(self) -> None:
        """No pattern may rely on the guard's fallback to stay renderable."""
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
        """29 patterns x 5 intensities = 145 calls, zero exceptions, zero fallbacks."""
        calls = 0
        for pattern_id in PATTERN_IDS:
            pattern = MovementLibrary.PATTERNS[pattern_id]
            table = pattern.categorical_params or DEFAULT_MOVEMENT_PARAMS
            for intensity in INTENSITY_LADDER:
                assert intensity in table, f"{pattern.id} would fall back at {intensity.value}"
                result = generate(pattern, intensity)
                assert result.pan_curve or result.pan_static_dmx is not None
                calls += 1
        assert calls == 145

    def test_unknown_intensity_degrades_instead_of_raising(self) -> None:
        """P4-F1a guard: an intensity missing from a table cannot KeyError."""
        pattern = MovementLibrary.PATTERNS[MovementType.CIRCLE]
        stripped = pattern.model_copy(
            update={
                "categorical_params": {
                    Intensity.SMOOTH: pattern.categorical_params[Intensity.SMOOTH]
                }
            }
        )
        assert generate(stripped, Intensity.INTENSE).pan_curve


@pytest.mark.parametrize("pattern_id", PATTERN_IDS, ids=lambda p: p.value)
class TestPerPatternIntensityBehavior:
    """The properties every pattern's authored ladder has to satisfy."""

    def test_intensity_monotonic_curve_energy(self, pattern_id: MovementType) -> None:
        """Higher intensity means more travel: SLOW <= ... <= INTENSE."""
        pattern = MovementLibrary.PATTERNS[pattern_id]
        energies = [
            sum(total_variation(values) for values in curves(generate(pattern, intensity)))
            for intensity in INTENSITY_LADDER
        ]

        for step, (lower, upper) in enumerate(itertools.pairwise(INTENSITY_LADDER)):
            low, high = energies[step], energies[step + 1]
            assert low <= high + 1e-9, f"{pattern.id}: {lower.value} > {upper.value} ({energies})"

        if pattern_id not in STATIONARY_PATTERNS:
            assert energies[0] < energies[-1], f"{pattern.id}: SLOW and INTENSE tie ({energies})"

    def test_slow_excursion_less_than_intense_excursion(self, pattern_id: MovementType) -> None:
        """P4-M6: frequency no longer inverts physical excursion.

        Sanity ordering check; the discriminating pre-fix failures live in tests/unit/curves/functions/test_movement.py (the spec metric passed on unfixed code), because
        `center_curve` stretched SLOW's partial oscillation back out to full range
        and gave the gentlest intensity the widest swing.
        """
        if pattern_id in STATIONARY_PATTERNS:
            pytest.skip("both axes hold position under the default geometry")

        pattern = MovementLibrary.PATTERNS[pattern_id]
        slow = max(excursion(v) for v in curves(generate(pattern, Intensity.SLOW)))
        intense = max(excursion(v) for v in curves(generate(pattern, Intensity.INTENSE)))
        assert slow < intense, f"{pattern.id}: SLOW swings {slow:.3f} vs INTENSE {intense:.3f}"

    def test_no_terminal_snapback(self, pattern_id: MovementType) -> None:
        """P4-M5: the last step is no larger than the largest step before it."""
        pattern = MovementLibrary.PATTERNS[pattern_id]
        for intensity in INTENSITY_LADDER:
            for values in curves(generate(pattern, intensity)):
                if len(values) < 3:
                    continue
                deltas = [abs(values[i + 1] - values[i]) for i in range(len(values) - 1)]
                assert deltas[-1] <= max(deltas[:-1]) + 1e-9, (
                    f"{pattern.id} at {intensity.value}: final step {deltas[-1]:.4f} "
                    f"exceeds the largest step elsewhere {max(deltas[:-1]):.4f}"
                )
