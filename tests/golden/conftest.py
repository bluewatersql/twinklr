"""Fixtures for the golden render suite.

The `--regen-goldens` flag itself is registered in `tests/conftest.py` so it is
available for whole-suite invocations as well.
"""

from __future__ import annotations

import os

import pytest

from tests.golden.harness import RIGS, RenderResult, RigSpec, regen_requested, render_rig
from tests.golden.xlights_client import DEFAULT_BASE_URL, probe_reachable

# Renders are pure and take a few hundred milliseconds each; cache per rig so the
# handful of golden tests sharing a rig render it once.
_RENDER_CACHE: dict[str, RenderResult] = {}


# ============================================================================
# requires_xlights marker — LOCAL-ONLY, skips when the automation API is unreachable
# ============================================================================
# Mirrors tests/conftest.py's `requires_template_data` skip pattern: the check runs
# once at collection time (cheap — a single short-timeout probe), and every test
# carrying the marker is skipped with the same explicit reason rather than failing
# or hanging. This is what keeps P1P-T12's suite out of CI without a separate
# test-selection flag: the marker alone is the skip mechanism.

# The suite also needs an explicit opt-in. Its tests create a new sequence in whatever
# xLights instance answers, so running them just because the owner happens to have
# xLights open (for example during `make validate`) interrupts their session and, when
# that instance is busy, fails the gate.
XLIGHTS_ACCEPTANCE_ENV = "TWINKLR_XLIGHTS_ACCEPTANCE"
_XLIGHTS_REACHABLE = os.environ.get(XLIGHTS_ACCEPTANCE_ENV) == "1" and probe_reachable(
    DEFAULT_BASE_URL
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip `requires_xlights`-marked tests when no automation API answers."""
    if _XLIGHTS_REACHABLE:
        return
    skip_reason = pytest.mark.skip(
        reason=(
            f"LOCAL-ONLY test (P1P-T12). Set {XLIGHTS_ACCEPTANCE_ENV}=1 and start xLights "
            f"with its HTTP automation API answering at {DEFAULT_BASE_URL} to exercise "
            "this suite. Never runs in CI."
        )
    )
    for item in items:
        if "requires_xlights" in item.keywords:
            item.add_marker(skip_reason)


@pytest.fixture(scope="session")
def xlights_reachable() -> bool:
    """Whether the automation API answered at collection time."""
    return _XLIGHTS_REACHABLE


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
