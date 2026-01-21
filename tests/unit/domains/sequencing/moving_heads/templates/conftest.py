"""Test fixtures for template tests."""

from blinkb0t.core.config.fixtures import (
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureInstance,
)


def create_test_fixture(fixture_id: str = "MH1") -> FixtureInstance:
    """Create a minimal test fixture."""
    dmx_mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=3,
        dimmer_channel=5,
    )
    config = FixtureConfig(
        fixture_id=fixture_id,
        name=f"Moving Head {fixture_id}",
        dmx_mapping=dmx_mapping,
        pan_range=(-270, 270),
        tilt_range=(-90, 90),
        pan_orient=1,
        tilt_orient=1,
    )
    return FixtureInstance(
        fixture_id=fixture_id,
        config=config,
        xlights_model_name=f"Dmx {fixture_id}",
    )


def create_test_fixture_group(fixture_ids: list[str] | None = None) -> FixtureGroup:
    """Create a test fixture group."""
    if fixture_ids is None:
        fixture_ids = ["MH1"]

    fixtures = [create_test_fixture(fid) for fid in fixture_ids]
    return FixtureGroup(
        group_id="test_group",
        xlights_group="Test Group",
        fixtures=fixtures,
    )
