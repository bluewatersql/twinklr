"""Lost movement behaviors: angular travel, travel/dwell and organic motion."""

from fractions import Fraction

from pydantic import ValidationError
import pytest

from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.sequencer.models.template import Movement
from twinklr.core.sequencer.moving_heads.compile.step import evaluate_path

AIM = PoseDegrees(pan_deg=0, tilt_deg=0)


def spec(**updates):
    return Movement.model_validate(
        {
            "shape": "polyline",
            "mode": "periodic",
            "period_beats": 4,
            "start_pan_deg": 0,
            "start_tilt_deg": 0,
            "pan_extent_deg": 40,
            "tilt_extent_deg": 20,
            "path_knots": [
                {"phase": 0, "x": -1, "y": -1},
                {"phase": 0.5, "x": 1, "y": 1},
                {"phase": 1, "x": -1, "y": -1},
            ],
            **updates,
        }
    )


def at(movement, phase):
    p = Fraction(phase)
    return evaluate_path(movement, AIM, p.numerator, p.denominator)


def test_angular_travel_has_constant_speed_and_reverses_without_sine_easing():
    movement = spec()
    values = [at(movement, Fraction(i, 8))[0] for i in range(9)]
    assert values == [-40, -20, 0, 20, 40, 20, 0, -20, -40]
    assert at(movement, Fraction(-1, 8)) == at(movement, Fraction(7, 8))
    assert at(movement, 1) == at(movement, 0)


def test_pose_switch_has_visible_travel_and_real_dwell():
    movement = spec(
        path_knots=[
            {"phase": p, "x": v, "y": v}
            for p, v in [(0, 1), (0.375, 1), (0.5, -1), (0.875, -1), (1, 1)]
        ]
    )
    assert at(movement, 0) == at(movement, 0.25) == (40, 20)
    assert at(movement, 0.4375) == (0, 0)
    assert at(movement, 0.5) == at(movement, 0.75) == (-40, -20)
    assert at(movement, 0.9375) == (0, 0)


def test_polyline_transform_and_finite_terminal_hold():
    movement = spec(
        mode="finite",
        path_knots=[{"phase": 0, "x": 0, "y": 0}, {"phase": 1, "x": 1, "y": 0}],
        transform={"rotation_deg": 90},
    )
    assert at(movement, -2) == (0, 0)
    assert at(movement, 0.5) == (0, 10)
    assert at(movement, 3) == (0, 20)
    reverse = movement.model_copy(
        update={"transform": movement.transform.model_copy(update={"reverse": True})}
    )
    assert at(reverse, -2) == (0, 20)
    assert at(reverse, 3) == (0, 0)


@pytest.mark.parametrize(
    "knots",
    [
        [{"phase": 0.1, "x": 0, "y": 0}, {"phase": 1, "x": 0, "y": 0}],
        [
            {"phase": 0, "x": 0, "y": 0},
            {"phase": 0.5, "x": 1, "y": 0},
            {"phase": 0.5, "x": 0, "y": 0},
            {"phase": 1, "x": 0, "y": 0},
        ],
        [{"phase": 0, "x": 0, "y": 0}, {"phase": 1, "x": 1, "y": 0}],
    ],
)
def test_reject_discontinuous_or_ambiguous_periodic_paths(knots):
    with pytest.raises(ValidationError):
        spec(path_knots=knots)


def test_path_knots_cannot_be_ignored_on_another_shape():
    with pytest.raises(ValidationError, match="only to polyline"):
        spec(shape="circle")


def test_organic_is_repeatable_irregular_and_has_independent_axes():
    movement = spec(shape="organic", path_knots=None)
    phases = [Fraction(i, 128) for i in range(129)]
    values = [at(movement, p) for p in phases]
    assert values == list(reversed([at(movement, p) for p in reversed(phases)]))
    assert all(at(movement, p + 3) == pytest.approx(v) for p, v in zip(phases, values, strict=True))
    assert values[0] == values[-1]
    assert max(v[0] for v in values) - min(v[0] for v in values) > 10
    assert max(v[1] for v in values) - min(v[1] for v in values) > 5
    assert any(abs(x / 40 - y / 20) > 0.1 for x, y in values)
    # Several unequal extrema distinguish meander from a single sine oscillation.
    turns = [
        values[i][0]
        for i in range(1, 128)
        if (values[i][0] - values[i - 1][0]) * (values[i + 1][0] - values[i][0]) < 0
    ]
    assert len(turns) > 4
    assert len({round(abs(v), 1) for v in turns}) > 3
    assert (
        abs(at(movement, Fraction(1, 100000))[0] - at(movement, Fraction(99999, 100000))[0]) < 0.1
    )


@pytest.mark.parametrize(
    "template_id",
    ["angular_pan", "angular_tilt", "bounce_fan", "fan_iris", "radial_fan", "zigzag_alternating"],
)
def test_symmetric_paths_do_not_offer_noop_reversal(template_id):
    from tests.support import moving_heads as m
    from twinklr.core.sequencer.moving_heads.modifiers import candidates
    from twinklr.core.sequencer.moving_heads.templates import get_template

    with m.family_catalog():
        offered = candidates(get_template(template_id).template)
    assert offered["direction=reverse"] is not None  # rejection reason


def test_asymmetric_travel_dwell_reversal_remains_available():
    from tests.support import moving_heads as m
    from twinklr.core.sequencer.moving_heads.modifiers import candidates
    from twinklr.core.sequencer.moving_heads.templates import get_template

    with m.family_catalog():
        offered = candidates(get_template("pose_pop_lock").template)
    assert offered["direction=reverse"] is None
