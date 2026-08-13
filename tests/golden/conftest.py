"""Fixtures for the golden render suite.

The `--regen-goldens` flag itself is registered in `tests/conftest.py` so it is
available for whole-suite invocations as well.
"""

from __future__ import annotations

import pytest

from tests.golden.harness import RIGS, RenderResult, RigSpec, regen_requested, render_rig

# Renders are pure and take a few hundred milliseconds each; cache per rig so the
# handful of golden tests sharing a rig render it once.
_RENDER_CACHE: dict[str, RenderResult] = {}


@pytest.fixture(scope="session")
def regen_goldens(pytestconfig: pytest.Config) -> bool:
    """True when the run should rewrite goldens instead of comparing against them."""
    return regen_requested(pytestconfig)


@pytest.fixture
def render_cached():
    """Render a rig once per session and hand back the cached result."""

    def _render(rig: RigSpec) -> RenderResult:
        if rig.rig_id not in _RENDER_CACHE:
            _RENDER_CACHE[rig.rig_id] = render_rig(rig)
        return _RENDER_CACHE[rig.rig_id]

    return _render


@pytest.fixture(params=sorted(RIGS), ids=sorted(RIGS))
def rig(request: pytest.FixtureRequest) -> RigSpec:
    """Parametrized over every tracked golden rig."""
    return RIGS[request.param]
