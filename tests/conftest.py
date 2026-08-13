"""Shared pytest fixtures for twinklr tests.

Modern conftest adapted from .dev/tests/conftest.py with updates for new architecture.
"""

from __future__ import annotations

from pathlib import Path

import nltk.data
import pytest

from twinklr.core.config.fixtures.instances import FixtureInstance
from twinklr.core.config.poses import PanPose, TiltPose
from twinklr.core.sequencer.models.enum import TemplateRole
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

# ============================================================================
# Vendored NLTK resources — offline test data
# ============================================================================
# g2p_en (used by twinklr.core.audio.phonemes.g2p_service) needs NLTK's
# averaged_perceptron_tagger_eng POS tagger. Rather than requiring a live
# `nltk.download()` during test collection/execution (network-hostile), the
# extracted resource is vendored under tests/vendor/nltk_data/ and prepended
# to NLTK's search path here, before any test imports g2p_en. This makes
# tests/unit/audio/phonemes/test_g2p_service.py and test_bundle.py pass with
# no network access at test-run time. Production code (audio/phonemes/*) is
# untouched — this only affects where NLTK looks for data during pytest.
_VENDORED_NLTK_DATA = Path(__file__).resolve().parent / "vendor" / "nltk_data"
if _VENDORED_NLTK_DATA.is_dir() and str(_VENDORED_NLTK_DATA) not in nltk.data.path:
    nltk.data.path.insert(0, str(_VENDORED_NLTK_DATA))

# ============================================================================
# requires_template_data marker — fixture-presence skip
# ============================================================================
# A handful of tests (and the production code paths they exercise) still
# hardcode the legacy, gitignored `data/templates/index.json` path rather
# than the tracked `catalog/templates/` seed set (see
# `catalog/templates/README.md` and `build/specs/phase-0-foundation/
# P0-T2-structural-test-repair.md`). Repointing those production call sites
# is P1K-T3's job, not this one. Until that lands, tests marked
# `requires_template_data` skip cleanly instead of failing when the legacy
# path is absent — same pattern as
# `tests/integration/profiling/test_profiler_integration.py`'s
# `pytest.skip()` on absent vendor fixtures.

_LEGACY_TEMPLATES_INDEX = Path(__file__).resolve().parent.parent / "data" / "templates" / "index.json"


def _legacy_template_data_available() -> bool:
    return _LEGACY_TEMPLATES_INDEX.exists()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip `requires_template_data`-marked tests when the legacy data is absent."""
    if _legacy_template_data_available():
        return
    skip_reason = pytest.mark.skip(
        reason=(
            "data/templates/index.json not present; this test depends on a production "
            "code path not yet repointed to catalog/templates/ (see P1K-T3). Run the "
            "recipe_builder promotion pipeline to populate data/templates/ locally, or "
            "wait for P1K-T3's repoint."
        )
    )
    for item in items:
        if "requires_template_data" in item.keywords:
            item.add_marker(skip_reason)


# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture
def project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def fixtures_dir() -> Path:
    """Get test fixtures directory."""
    return Path(__file__).parent / "fixtures"


# ============================================================================
# Timing Fixtures
# ============================================================================


@pytest.fixture
def simple_song_features() -> dict:
    """Create simple song features for testing (120 BPM, 4 bars)."""
    return {
        "tempo_bpm": 120.0,
        "duration_s": 8.0,  # 4 bars at 120 BPM
        "beats_s": [i * 0.5 for i in range(16)],  # 16 beats (4 bars - 4 beats)
        "bars_s": [i * 2.0 for i in range(4)],  # 4 bars
        "assumptions": {"beats_per_bar": 4},
    }


@pytest.fixture
def beat_grid(simple_song_features: dict) -> BeatGrid:
    """Create a BeatGrid from simple song features."""
    return BeatGrid.from_song_features(simple_song_features)


# ============================================================================
# Fixture Config Fixtures
# ============================================================================


@pytest.fixture
def mock_fixture_instance() -> FixtureInstance:
    """Create a mock FixtureInstance for testing."""
    from twinklr.core.config.fixtures.base import FixtureConfig
    from twinklr.core.config.fixtures.enums import ChannelName, FixtureType

    config = FixtureConfig(
        fixture_type=FixtureType.MOVING_HEAD,
        model_name="Test Moving Head",
        dmx_mapping={
            ChannelName.PAN: 1,
            ChannelName.TILT: 2,
            ChannelName.DIMMER: 3,
        },
        inversions={
            ChannelName.PAN: False,
            ChannelName.TILT: False,
        },
        pan_range_deg=540.0,
        tilt_range_deg=270.0,
    )

    return FixtureInstance(
        fixture_id="test_fixture_1",
        start_channel=1,
        config=config,
        role=TemplateRole.INNER_LEFT,
        pan_pose=PanPose.CENTER,
        tilt_pose=TiltPose.HORIZON,
    )


@pytest.fixture
def mock_fixture_group(mock_fixture_instance: FixtureInstance) -> list[FixtureInstance]:
    """Create a list of mock FixtureInstance objects for testing."""
    # Create 4 fixtures
    fixtures = []
    roles = [
        TemplateRole.OUTER_LEFT,
        TemplateRole.INNER_LEFT,
        TemplateRole.INNER_RIGHT,
        TemplateRole.OUTER_RIGHT,
    ]
    pan_poses = [PanPose.WIDE_LEFT, PanPose.MID_LEFT, PanPose.MID_RIGHT, PanPose.WIDE_RIGHT]

    for i, (role, pan_pose) in enumerate(zip(roles, pan_poses, strict=False)):
        fixture = FixtureInstance(
            fixture_id=f"test_fixture_{i + 1}",
            start_channel=(i * 10) + 1,
            config=mock_fixture_instance.config,
            role=role,
            pan_pose=pan_pose,
            tilt_pose=TiltPose.HORIZON,
        )
        fixtures.append(fixture)

    return fixtures


# ============================================================================
# Template Fixtures
# ============================================================================


@pytest.fixture
def mock_template_doc():
    """Create a mock TemplateDoc for testing.

    Note: Imports moved inside fixture to avoid circular dependencies.
    """
    from twinklr.core.sequencer.moving_heads.templates import (
        get_template,
        load_builtin_templates,
    )

    load_builtin_templates()
    return get_template("bounce_fan_pulse")


# ============================================================================
# Test Data Loaders
# ============================================================================


@pytest.fixture
def load_fixture_json(fixtures_dir: Path):
    """Factory fixture to load JSON test fixtures."""
    import json

    def _load(filename: str) -> dict:
        fixture_path = fixtures_dir / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")
        with fixture_path.open("r") as f:
            return json.load(f)

    return _load
