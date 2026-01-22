"""Easing curve generators backed by easing-functions."""

from __future__ import annotations

import inspect
from typing import Protocol

from easing_functions import (
    BackEaseIn,
    BackEaseInOut,
    BackEaseOut,
    BounceEaseIn,
    BounceEaseOut,
    CubicEaseIn,
    CubicEaseInOut,
    CubicEaseOut,
    ElasticEaseIn,
    ElasticEaseInOut,
    ElasticEaseOut,
    ExpoEaseIn,
    ExpoEaseInOut,
    ExpoEaseOut,
    QuadEaseIn,
    QuadEaseInOut,
    QuadEaseOut,
    SineEaseIn,
    SineEaseInOut,
    SineEaseOut,
)

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


class _EasingCallable(Protocol):
    def __call__(self, t: float) -> float: ...

    def ease(self, t: float) -> float: ...


_EASING_DEFAULTS = {
    "start": 0.0,
    "end": 1.0,
    "duration": 1.0,
}


def _make_easing(
    easing_cls: type[_EasingCallable],
    *,
    overshoot: float | None = None,
) -> _EasingCallable:
    parameters = inspect.signature(easing_cls).parameters
    kwargs = dict(_EASING_DEFAULTS)

    if overshoot is not None:
        if "overshoot" in parameters:
            kwargs["overshoot"] = overshoot
        elif "s" in parameters:
            kwargs["s"] = overshoot

    return easing_cls(**kwargs)


def _evaluate_easing(easing: _EasingCallable, t: float) -> float:
    if hasattr(easing, "ease"):
        return easing.ease(t)
    return easing(t)


def _sample_easing(n_samples: int, easing: _EasingCallable) -> list[CurvePoint]:
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=_evaluate_easing(easing, t)) for t in t_grid]


def generate_ease_in_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-in curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseIn))


def generate_ease_out_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-out curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseOut))


def generate_ease_in_out_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseInOut))


def generate_ease_in_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-in curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseIn))


def generate_ease_out_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-out curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseOut))


def generate_ease_in_out_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseInOut))


def generate_ease_in_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-in curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseIn))


def generate_ease_out_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-out curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseOut))


def generate_ease_in_out_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseInOut))


def generate_ease_in_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-in curve."""
    return _sample_easing(n_samples, _make_easing(ExpoEaseIn))


def generate_ease_out_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-out curve."""
    return _sample_easing(n_samples, _make_easing(ExpoEaseOut))


def generate_ease_in_out_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(ExpoEaseInOut))


def generate_ease_in_back(n_samples: int, overshoot: float = 1.70158) -> list[CurvePoint]:
    """Generate a back ease-in curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseIn, overshoot=overshoot))


def generate_ease_out_back(n_samples: int, overshoot: float = 1.70158) -> list[CurvePoint]:
    """Generate a back ease-out curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseOut, overshoot=overshoot))


def generate_ease_in_out_back(
    n_samples: int,
    overshoot: float = 1.70158,
) -> list[CurvePoint]:
    """Generate a back ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseInOut, overshoot=overshoot))


def generate_bounce_out(n_samples: int) -> list[CurvePoint]:
    """Generate a bounce-out curve."""
    return _sample_easing(n_samples, _make_easing(BounceEaseOut))


def generate_bounce_in(n_samples: int) -> list[CurvePoint]:
    """Generate a bounce-in curve."""
    return _sample_easing(n_samples, _make_easing(BounceEaseIn))


def generate_elastic_out(n_samples: int) -> list[CurvePoint]:
    """Generate an elastic-out curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseOut))


def generate_elastic_in(n_samples: int) -> list[CurvePoint]:
    """Generate an elastic-in curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseIn))


def generate_elastic_in_out(n_samples: int) -> list[CurvePoint]:
    """Generate an elastic-in-out curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseInOut))
