"""Easing curve generators backed by easing-functions."""

from __future__ import annotations

from typing import Any, Protocol, TypeGuard, cast

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
    QuadEaseIn,
    QuadEaseInOut,
    QuadEaseOut,
    SineEaseIn,
    SineEaseInOut,
    SineEaseOut,
)

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


class _CallableEasing(Protocol):
    def __call__(self, t: float) -> float: ...


class _EaseMethodEasing(Protocol):
    def ease(self, t: float) -> float: ...


def _has_ease(e: Any) -> TypeGuard[_EaseMethodEasing]:
    return hasattr(e, "ease")


EasingFn = _CallableEasing  # ✅ avoid Callable alias entirely


_EASING_DEFAULTS: dict[str, float] = {
    "start": 0.0,
    "end": 1.0,
    "duration": 1.0,
}


def _make_easing(easing_cls: type[Any], **kwargs: Any) -> EasingFn:
    obj = easing_cls(**{**_EASING_DEFAULTS, **kwargs})

    if _has_ease(obj):
        return lambda t: obj.ease(t)

    if not callable(obj):
        raise TypeError(f"{type(obj).__name__} is not callable and has no .ease(t)")
    return cast(EasingFn, obj)


def _evaluate_easing(easing: EasingFn, t: float) -> float:
    if _has_ease(easing):
        return easing.ease(t)
    return easing(t)


def _sample_easing(n_samples: int, easing: EasingFn) -> list[CurvePoint]:
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=_evaluate_easing(easing, t)) for t in t_grid]


def generate_ease_in_sine(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a sine ease-in curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseIn))


def generate_ease_out_sine(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a sine ease-out curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseOut))


def generate_ease_in_out_sine(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a sine ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(SineEaseInOut))


def generate_ease_in_quad(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a quadratic ease-in curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseIn))


def generate_ease_out_quad(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a quadratic ease-out curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseOut))


def generate_ease_in_out_quad(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a quadratic ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(QuadEaseInOut))


def generate_ease_in_cubic(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a cubic ease-in curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseIn))


def generate_ease_out_cubic(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a cubic ease-out curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseOut))


def generate_ease_in_out_cubic(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a cubic ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(CubicEaseInOut))


def generate_ease_in_back(n_samples: int, overshoot: float = 1.70158, **kwargs) -> list[CurvePoint]:
    """Generate a back ease-in curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseIn, overshoot=overshoot))


def generate_ease_out_back(
    n_samples: int, overshoot: float = 1.70158, **kwargs
) -> list[CurvePoint]:
    """Generate a back ease-out curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseOut, overshoot=overshoot))


def generate_ease_in_out_back(
    n_samples: int,
    overshoot: float = 1.70158,
) -> list[CurvePoint]:
    """Generate a back ease-in-out curve."""
    return _sample_easing(n_samples, _make_easing(BackEaseInOut, overshoot=overshoot))


def generate_bounce_out(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a bounce-out curve."""
    return _sample_easing(n_samples, _make_easing(BounceEaseOut))


def generate_bounce_in(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate a bounce-in curve."""
    return _sample_easing(n_samples, _make_easing(BounceEaseIn))


def generate_elastic_out(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate an elastic-out curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseOut))


def generate_elastic_in(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate an elastic-in curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseIn))


def generate_elastic_in_out(n_samples: int, **kwargs) -> list[CurvePoint]:
    """Generate an elastic-in-out curve."""
    return _sample_easing(n_samples, _make_easing(ElasticEaseInOut))
