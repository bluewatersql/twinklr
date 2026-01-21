"""Tests for Phase 0 Component 5: JobConfig enhancements."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig, PlannerFeatures
from blinkb0t.core.domains.sequencing.models.poses import Pose, PoseConfig, PoseID


class TestJobConfigEnhancements:
    """Test Phase 0 Component 5 enhancements to JobConfig."""

    def test_schema_version_3_0(self):
        """Test schema version bumped to 3.0."""
        config = JobConfig(fixture_config_path="test.json")
        assert config.schema_version == "3.0"

    def test_default_pose_config(self):
        """Test default pose configuration."""
        config = JobConfig(fixture_config_path="test.json")

        assert isinstance(config.pose_config, PoseConfig)
        assert len(config.pose_config.custom_poses) == 0
        assert len(config.pose_config.pose_overrides) == 0

    def test_default_planner_features(self):
        """Test default planner features (Phase 3: all enabled)."""
        config = JobConfig(fixture_config_path="test.json")

        assert isinstance(config.planner_features, PlannerFeatures)
        assert config.planner_features.enable_shutter is True
        assert config.planner_features.enable_gobo is True
        assert config.planner_features.enable_color is True  # enabled by default

    def test_custom_poses(self):
        """Test custom pose configuration."""
        custom_pose = Pose(
            pose_id="CUSTOM_SPOT",
            name="Custom Spotlight",
            description="Venue-specific spotlight position",
            pan_deg=45.0,
            tilt_deg=30.0,
        )

        config = JobConfig(
            fixture_config_path="test.json",
            pose_config=PoseConfig(custom_poses={"CUSTOM_SPOT": custom_pose}),
        )

        assert "CUSTOM_SPOT" in config.pose_config.custom_poses
        assert config.pose_config.custom_poses["CUSTOM_SPOT"].pan_deg == 45.0
        assert config.pose_config.custom_poses["CUSTOM_SPOT"].tilt_deg == 30.0
        assert config.pose_config.custom_poses["CUSTOM_SPOT"].name == "Custom Spotlight"

    def test_pose_override(self):
        """Test overriding standard pose."""
        override_pose = Pose(
            pose_id="FORWARD",
            name="Forward (Adjusted)",
            description="Adjusted for venue rig orientation",
            pan_deg=5.0,
            tilt_deg=2.0,
        )

        config = JobConfig(
            fixture_config_path="test.json",
            pose_config=PoseConfig(pose_overrides={PoseID.FORWARD: override_pose}),
        )

        assert PoseID.FORWARD in config.pose_config.pose_overrides
        assert config.pose_config.pose_overrides[PoseID.FORWARD].pan_deg == 5.0
        assert config.pose_config.pose_overrides[PoseID.FORWARD].tilt_deg == 2.0

    def test_multiple_custom_poses(self):
        """Test multiple custom poses."""
        pose1 = Pose(
            pose_id="VENUE_SPOT",
            name="Venue Spotlight",
            description="Main spotlight position",
            pan_deg=-12.0,
            tilt_deg=25.0,
        )
        pose2 = Pose(
            pose_id="DJ_BOOTH",
            name="DJ Booth",
            description="Aimed at DJ booth",
            pan_deg=135.0,
            tilt_deg=15.0,
        )

        config = JobConfig(
            fixture_config_path="test.json",
            pose_config=PoseConfig(custom_poses={"VENUE_SPOT": pose1, "DJ_BOOTH": pose2}),
        )

        assert len(config.pose_config.custom_poses) == 2
        assert "VENUE_SPOT" in config.pose_config.custom_poses
        assert "DJ_BOOTH" in config.pose_config.custom_poses

    def test_planner_features_all_disabled(self):
        """Test disabling all planner features."""
        config = JobConfig(
            fixture_config_path="test.json",
            planner_features=PlannerFeatures(
                enable_shutter=False, enable_gobo=False, enable_color=False
            ),
        )

        assert config.planner_features.enable_shutter is False
        assert config.planner_features.enable_gobo is False
        assert config.planner_features.enable_color is False

    def test_planner_features_custom(self):
        """Test custom planner features configuration."""
        config = JobConfig(
            fixture_config_path="test.json",
            planner_features=PlannerFeatures(enable_shutter=True, enable_gobo=False),
        )

        assert config.planner_features.enable_shutter is True
        assert config.planner_features.enable_gobo is False
        assert config.planner_features.enable_color is True  # enabled by default

    def test_agent_config_still_works(self):
        """Test that existing agent configuration still works."""
        config = JobConfig(
            fixture_config_path="test.json",
            agent=AgentOrchestrationConfig(
                max_iterations=5, token_budget=100000, enforce_token_budget=False
            ),
        )

        assert config.agent.max_iterations == 5
        assert config.agent.token_budget == 100000
        assert config.agent.enforce_token_budget is False

    def test_full_configuration(self):
        """Test full configuration with all new sections."""
        custom_pose = Pose(
            pose_id="CUSTOM", name="Custom", description="Test", pan_deg=45.0, tilt_deg=30.0
        )

        config = JobConfig(
            fixture_config_path="test.json",
            project_name="test_show",
            debug=True,
            agent=AgentOrchestrationConfig(max_iterations=3, token_budget=50000),
            pose_config=PoseConfig(custom_poses={"CUSTOM": custom_pose}),
            planner_features=PlannerFeatures(enable_shutter=True, enable_gobo=True),
        )

        # Check all sections present
        assert config.project_name == "test_show"
        assert config.debug is True
        assert config.agent.max_iterations == 3
        assert "CUSTOM" in config.pose_config.custom_poses
        assert config.planner_features.enable_shutter is True

    def test_backwards_compatibility_old_config(self):
        """Test backwards compatibility with schema 2.0 configs."""
        # Simulate old schema 2.0 config (no new fields)
        old_config_dict = {
            "schema_version": "2.0",
            "fixture_config_path": "test.json",
            "debug": True,
        }

        # Should load with defaults for new fields (Pydantic will handle this)
        config = JobConfig.model_validate(old_config_dict)

        # New fields use defaults
        assert isinstance(config.pose_config, PoseConfig)
        assert isinstance(config.planner_features, PlannerFeatures)
        assert len(config.pose_config.custom_poses) == 0
        assert config.planner_features.enable_shutter is True


class TestPlannerFeatures:
    """Test PlannerFeatures model."""

    def test_default_values(self):
        """Test default feature flags (Phase 3: all enabled)."""
        features = PlannerFeatures()

        assert features.enable_shutter is True
        assert features.enable_gobo is True
        assert features.enable_color is True  # enabled by default

    def test_custom_values(self):
        """Test custom feature flags."""
        features = PlannerFeatures(enable_shutter=False, enable_gobo=True, enable_color=False)

        assert features.enable_shutter is False
        assert features.enable_gobo is True
        assert features.enable_color is False

    def test_all_enabled(self):
        """Test all features enabled."""
        features = PlannerFeatures(enable_shutter=True, enable_gobo=True, enable_color=True)

        assert features.enable_shutter is True
        assert features.enable_gobo is True
        assert features.enable_color is True

    def test_all_disabled(self):
        """Test all features disabled."""
        features = PlannerFeatures(enable_shutter=False, enable_gobo=False, enable_color=False)

        assert features.enable_shutter is False
        assert features.enable_gobo is False
        assert features.enable_color is False


class TestPoseConfigValidation:
    """Test pose configuration validation."""

    def test_invalid_pan_angle_positive(self):
        """Test validation catches invalid pan angle (too positive)."""
        with pytest.raises(ValidationError) as exc_info:
            Pose(
                pose_id="INVALID",
                name="Invalid",
                description="Test",
                pan_deg=200.0,  # Out of range [-180, 180]
                tilt_deg=0.0,
            )

        errors = exc_info.value.errors()
        assert any("pan_deg" in str(e["loc"]) for e in errors)

    def test_invalid_pan_angle_negative(self):
        """Test validation catches invalid pan angle (too negative)."""
        with pytest.raises(ValidationError) as exc_info:
            Pose(
                pose_id="INVALID",
                name="Invalid",
                description="Test",
                pan_deg=-200.0,  # Out of range [-180, 180]
                tilt_deg=0.0,
            )

        errors = exc_info.value.errors()
        assert any("pan_deg" in str(e["loc"]) for e in errors)

    def test_invalid_tilt_angle_positive(self):
        """Test validation catches invalid tilt angle (too positive)."""
        with pytest.raises(ValidationError) as exc_info:
            Pose(
                pose_id="INVALID",
                name="Invalid",
                description="Test",
                pan_deg=0.0,
                tilt_deg=100.0,  # Out of range [-90, 90]
            )

        errors = exc_info.value.errors()
        assert any("tilt_deg" in str(e["loc"]) for e in errors)

    def test_invalid_tilt_angle_negative(self):
        """Test validation catches invalid tilt angle (too negative)."""
        with pytest.raises(ValidationError) as exc_info:
            Pose(
                pose_id="INVALID",
                name="Invalid",
                description="Test",
                pan_deg=0.0,
                tilt_deg=-100.0,  # Out of range [-90, 90]
            )

        errors = exc_info.value.errors()
        assert any("tilt_deg" in str(e["loc"]) for e in errors)

    def test_valid_pan_angle_boundaries(self):
        """Test valid pan angles at boundaries."""
        # Should not raise
        pose_min = Pose(
            pose_id="MIN_PAN", name="Min Pan", description="Test", pan_deg=-180.0, tilt_deg=0.0
        )
        pose_max = Pose(
            pose_id="MAX_PAN", name="Max Pan", description="Test", pan_deg=180.0, tilt_deg=0.0
        )

        assert pose_min.pan_deg == -180.0
        assert pose_max.pan_deg == 180.0

    def test_valid_tilt_angle_boundaries(self):
        """Test valid tilt angles at boundaries."""
        # Should not raise
        pose_min = Pose(
            pose_id="MIN_TILT", name="Min Tilt", description="Test", pan_deg=0.0, tilt_deg=-90.0
        )
        pose_max = Pose(
            pose_id="MAX_TILT", name="Max Tilt", description="Test", pan_deg=0.0, tilt_deg=90.0
        )

        assert pose_min.tilt_deg == -90.0
        assert pose_max.tilt_deg == 90.0


class TestJobConfigIntegration:
    """Integration tests for JobConfig with all enhancements."""

    def test_minimal_config_loads(self):
        """Test minimal configuration loads with all defaults."""
        config = JobConfig(fixture_config_path="test.json")

        # Check all sections present with defaults
        assert config.schema_version == "3.0"
        assert isinstance(config.agent, AgentOrchestrationConfig)
        assert isinstance(config.pose_config, PoseConfig)
        assert isinstance(config.planner_features, PlannerFeatures)

    def test_config_serialization(self):
        """Test configuration can be serialized and deserialized."""
        original = JobConfig(
            fixture_config_path="test.json",
            project_name="test",
            pose_config=PoseConfig(
                custom_poses={
                    "CUSTOM": Pose(
                        pose_id="CUSTOM",
                        name="Custom",
                        description="Test",
                        pan_deg=45.0,
                        tilt_deg=30.0,
                    )
                }
            ),
        )

        # Serialize
        data = original.model_dump()

        # Deserialize
        restored = JobConfig.model_validate(data)

        # Check fields match
        assert restored.project_name == original.project_name
        assert "CUSTOM" in restored.pose_config.custom_poses
        assert restored.pose_config.custom_poses["CUSTOM"].pan_deg == 45.0

    def test_config_with_extra_fields_ignored(self):
        """Test configuration ignores extra fields (forward compatibility)."""
        config_dict = {
            "schema_version": "3.0",
            "fixture_config_path": "test.json",
            "unknown_field": "should_be_ignored",
            "another_unknown": 123,
        }

        # Should not raise due to extra="ignore"
        config = JobConfig.model_validate(config_dict)
        assert config.fixture_config_path == "test.json"
