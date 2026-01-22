import math

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


def generate_musical_accent(
    n_samples: int,
    cycles: float = 1.0,
    attack_frac: float = 0.1,
    decay_rate: float = 3.0,
) -> list[CurvePoint]:
    """Musical accent: sharp attack, smooth decay.

    Optimized for percussive elements like drum hits, stabs, and stingers.
    Creates an instant rise followed by natural decay.

    Envelope (per cycle):
        - Attack (0-attack_frac): Linear sharp rise to peak
        - Decay (attack_frac-1.0): Exponential smooth decay

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete accents in the output.
        attack_frac: Fraction of each cycle spent in attack (0.0 to 1.0).
        decay_rate: Exponential decay rate (higher = faster decay).

    Returns:
        List of CurvePoints forming a musical accent envelope.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")
    if cycles <= 0:
        raise ValueError(f"cycles must be > 0, got {cycles}")

    attack_frac = max(0.0, min(1.0, attack_frac))
    decay_rate = max(0.0, decay_rate)

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    # Avoid division by zero when attack_frac is 0 or 1
    denom_attack = attack_frac if attack_frac > 0.0 else 1.0
    denom_decay = (1.0 - attack_frac) if attack_frac < 1.0 else 1.0

    for t in t_grid:
        cycle_pos = (t * cycles) % 1.0

        if cycle_pos < attack_frac:
            v = cycle_pos / denom_attack
        else:
            decay_t = (cycle_pos - attack_frac) / denom_decay
            v = math.exp(-decay_rate * decay_t)

        v = max(0.0, min(1.0, v))
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_musical_swell(
    n_samples: int,
    cycles: float = 1.0,
    rise_frac: float = 0.9,
    rise_rate: float = 3.0,
) -> list[CurvePoint]:
    """Musical swell: smooth rise, sharp cutoff.

    Optimized for build-ups and crescendos leading into drops or climaxes.
    Creates a gradual musical build followed by instant release.

    Envelope (per cycle):
        - Rise (0-rise_frac): Exponential smooth rise to peak
        - Release (rise_frac-1.0): Linear sharp drop to zero

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete swells in the output.
        rise_frac: Fraction of each cycle spent rising (0.0 to 1.0).
        rise_rate: Exponential rise rate (higher = faster rise).

    Returns:
        List of CurvePoints forming a musical swell envelope.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")
    if cycles <= 0:
        raise ValueError(f"cycles must be > 0, got {cycles}")

    rise_frac = max(0.0, min(1.0, rise_frac))
    rise_rate = max(0.0, rise_rate)

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    denom_rise = rise_frac if rise_frac > 0.0 else 1.0
    denom_release = (1.0 - rise_frac) if rise_frac < 1.0 else 1.0

    for t in t_grid:
        cycle_pos = (t * cycles) % 1.0

        if cycle_pos < rise_frac:
            rise_t = cycle_pos / denom_rise
            v = 1.0 - math.exp(-rise_rate * rise_t)
        else:
            release_t = (cycle_pos - rise_frac) / denom_release
            v = 1.0 - release_t

        v = max(0.0, min(1.0, v))
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_beat_pulse(
    n_samples: int,
    cycles: float = 1.0,
    beat_subdivision: int = 4,
    phase: float = 0.0,
) -> list[CurvePoint]:
    """Beat-aligned pulse: rhythmic oscillation.

    Creates smooth pulsing aligned to musical beat subdivisions.
    Uses sine wave for natural, non-jarring rhythmic effects.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete cycles in the output.
        beat_subdivision: Number of pulses per cycle.
            - 1: Whole note (slow pulse)
            - 2: Half notes
            - 4: Quarter notes (default, most common)
            - 8: Eighth notes (double-time feel)
            - 16: Sixteenth notes (rapid pulsing)
        phase: Phase offset in cycles (e.g., 0.25 shifts by 90 degrees).

    Returns:
        List of CurvePoints forming a beat-aligned pulse wave.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")
    if cycles <= 0:
        raise ValueError(f"cycles must be > 0, got {cycles}")
    if beat_subdivision <= 0:
        raise ValueError(f"beat_subdivision must be > 0, got {beat_subdivision}")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    total = float(beat_subdivision) * cycles

    for t in t_grid:
        wave = math.sin(2.0 * math.pi * (total * t + phase))
        v = 0.5 * (1.0 + wave)
        v = max(0.0, min(1.0, v))
        points.append(CurvePoint(t=t, v=v))

    return points
