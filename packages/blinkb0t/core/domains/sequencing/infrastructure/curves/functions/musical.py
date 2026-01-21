"""Musical curve generation functions.

Curves optimized for beat-aligned timing and musical perception.
All functions take normalized time array [0, 1] and return normalized values [0, 1].

Musical curves are designed with specific attack/release characteristics:
- Sharp phases (5-10%): Perceived as "instant" by human perception
- Smooth phases (90-95%): Perceived as gradual musical change

Use Cases:
    - MUSICAL_ACCENT: Drum hits, stabs, stingers (sharp attack, smooth decay)
    - MUSICAL_SWELL: Builds, crescendos, swells into drops (smooth rise, sharp cutoff)
    - BEAT_PULSE: Rhythmic pulsing aligned to beat subdivisions
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def musical_accent(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Musical accent: sharp attack, smooth decay.

    Optimized for percussive elements like drum hits, stabs, and stingers.
    Creates an instant rise followed by natural decay.

    Envelope:
        - Attack (0-10%): Linear sharp rise to peak
        - Decay (10-100%): Exponential smooth decay

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Drum hits (kick, snare, hi-hat)
        - Stabs (horn stabs, synth stabs)
        - Stingers (short dramatic accents)
        - Percussive lighting effects

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> accent = musical_accent(t)  # Instant hit, smooth fade
        >>> # Perfect for flash on beat, fade during sustain
    """
    # Sharp attack phase (first 10%)
    attack_phase = t < 0.1
    attack = t / 0.1  # Linear rise from 0 to 1

    # Smooth decay phase (remaining 90%)
    # Exponential decay: e^(-3 * normalized_time)
    # Factor -3 gives natural musical decay (reaches ~5% by end)
    decay_t = (t - 0.1) / 0.9  # Normalize decay phase to [0, 1]
    decay = np.exp(-3 * decay_t)

    # Combine phases
    result = np.where(attack_phase, attack, decay)

    # Ensure DMX-safe bounds
    return np.clip(result, 0.0, 1.0)


def musical_swell(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Musical swell: smooth rise, sharp cutoff.

    Optimized for build-ups and crescendos leading into drops or climaxes.
    Creates a gradual musical build followed by instant release.

    Envelope:
        - Rise (0-90%): Exponential smooth rise to peak
        - Release (90-100%): Linear sharp drop to zero

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Build-ups to bass drops
        - Crescendos into climax moments
        - Pre-drop swells
        - Tension building effects

    Example:
        >>> t = np.linspace(0, 1, 800)  # 8 bars
        >>> swell = musical_swell(t)  # Gradual build, instant drop
        >>> # Perfect for 8-bar buildup into drop
    """
    # Smooth rise phase (first 90%)
    # Exponential rise: 1 - e^(-3 * normalized_time)
    # Inverse of decay for complementary shape
    rise_phase = t < 0.9
    rise_t = t / 0.9  # Normalize rise phase to [0, 1]
    rise = 1 - np.exp(-3 * rise_t)

    # Sharp release phase (last 10%)
    release_t = (t - 0.9) / 0.1  # Normalize release phase to [0, 1]
    release = 1 - release_t  # Linear drop from 1 to 0

    # Combine phases
    result = np.where(rise_phase, rise, release)

    # Ensure DMX-safe bounds
    return np.clip(result, 0.0, 1.0)


def beat_pulse(t: NDArray[np.float64], beat_subdivision: int = 4) -> NDArray[np.float64]:
    """Beat-aligned pulse: rhythmic oscillation.

    Creates smooth pulsing aligned to musical beat subdivisions.
    Uses sine wave for natural, non-jarring rhythmic effects.

    Args:
        t: Normalized time array [0, 1]
        beat_subdivision: Number of pulses per cycle
            - 1: Whole note (slow pulse)
            - 2: Half notes
            - 4: Quarter notes (default, most common)
            - 8: Eighth notes (double-time feel)
            - 16: Sixteenth notes (rapid pulsing)

    Returns:
        Normalized values [0, 1], oscillating around 0.5

    Use Cases:
        - Rhythmic pulsing on beat
        - Breathing/living effects
        - Tremolo/vibrato lighting
        - BPM-synced intensity modulation

    Formula:
        0.5 * (1 + sin(2π * subdivision * t))
        - Oscillates between 0 and 1
        - Centered at 0.5
        - Smooth transitions (no harsh cuts)

    Example:
        >>> t = np.linspace(0, 1, 400)  # 4 bars @ 100 pts/bar
        >>> pulse_4 = beat_pulse(t, beat_subdivision=4)  # Quarter notes
        >>> pulse_8 = beat_pulse(t, beat_subdivision=8)  # Eighth notes
        >>> # pulse_8 has twice the frequency of pulse_4
    """
    # Sine wave: oscillates between -1 and 1
    # sin(2π * subdivision * t) creates 'subdivision' cycles over [0, 1]
    wave = np.sin(2 * np.pi * beat_subdivision * t)

    # Scale and shift to [0, 1] range
    # 0.5 * (1 + wave) maps [-1, 1] → [0, 1]
    result = 0.5 * (1 + wave)

    # Already in [0, 1] range, but clip for safety
    clipped = np.clip(result, 0.0, 1.0)
    return np.asarray(clipped, dtype=np.float64)
