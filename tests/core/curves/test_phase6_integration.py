"""Phase 6 integration tests for curve pipeline."""

from blinkb0t.core.curves.composition import apply_envelope
from blinkb0t.core.curves.dmx_conversion import movement_curve_to_dmx
from blinkb0t.core.curves.generators import generate_movement_sine, generate_linear
from blinkb0t.core.curves.phase import apply_phase_shift_samples
from blinkb0t.core.curves.simplification import simplify_rdp


def test_movement_pipeline_to_dmx() -> None:
    movement = generate_movement_sine(n_samples=32, cycles=1.0)
    shifted = apply_phase_shift_samples(movement, offset_norm=0.25, n_samples=32)
    envelope = generate_linear(n_samples=32, ascending=True)
    composed = apply_envelope(shifted, envelope, n_samples=32)
    simplified = simplify_rdp(composed, epsilon=0.02)

    dmx_points = movement_curve_to_dmx(
        simplified,
        base_dmx=128.0,
        amplitude_dmx=50.0,
        clamp_min=0.0,
        clamp_max=255.0,
    )

    assert dmx_points
    for p in dmx_points:
        assert 0.0 <= p.v <= 255.0
        assert 0.0 <= p.t <= 1.0
