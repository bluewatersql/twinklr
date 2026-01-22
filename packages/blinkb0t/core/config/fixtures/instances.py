"""Fixture instance configuration and pose management.

Defines individual fixture instances, their configurations, and pose representations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from blinkb0t.core.config.fixtures.capabilities import FixtureCapabilities, MovementSpeed
from blinkb0t.core.config.fixtures.dmx import ChannelInversions, DmxMapping
from blinkb0t.core.config.fixtures.physical import MovementLimits, Orientation, PanTiltRange
from blinkb0t.core.config.poses import STANDARD_POSES, PoseLibrary


class Pose(BaseModel):
    """Physical orientation of a fixture in degrees.

    Represents pan/tilt angles in a coordinate system where:
    - pan_deg: 0° = forward, positive = stage right, negative = stage left
    - tilt_deg: 0° = horizon, positive = up, negative = down
    """

    model_config = ConfigDict(frozen=False)

    pan_deg: float = Field(..., description="Pan angle in degrees")
    tilt_deg: float = Field(..., description="Tilt angle in degrees")

    @field_validator("pan_deg")
    @classmethod
    def normalize_pan(cls, v: float) -> float:
        """Normalize pan to [-180, 180) range."""
        # Normalize to [0, 360) first
        v = v % 360.0
        # Convert to [-180, 180)
        if v >= 180.0:
            v -= 360.0
        return v


class FixturePosition(BaseModel):
    """Physical mounting position and aim offset of a fixture.

    Handles the fact that fixtures mounted at different positions
    need different DMX values to aim at the same target.
    """

    model_config = ConfigDict(frozen=False)

    position_index: int = Field(
        default=1, ge=1, le=10, description="Position number on this mount (1st, 2nd, etc.)"
    )

    # Default aim offset from "forward" (0, 0)
    pan_offset_deg: float = Field(
        default=0.0,
        description="Pan offset in degrees (positive = stage right, negative = stage left)",
    )
    tilt_offset_deg: float = Field(
        default=0.0, description="Tilt offset in degrees (positive = up, negative = down)"
    )

    def apply_offset(self, pose: Pose) -> Pose:
        """Apply mounting offset to a target pose.

        Use this when you want a fixture to aim at a specific target,
        and need to calculate the actual pose accounting for its mounting position.

        Args:
            pose: Target pose (where you want the fixture to aim)

        Returns:
            Actual pose accounting for mounting offset
        """
        return Pose(
            pan_deg=pose.pan_deg + self.pan_offset_deg,
            tilt_deg=pose.tilt_deg + self.tilt_offset_deg,
        )

    def remove_offset(self, pose: Pose) -> Pose:
        """Remove mounting offset to get relative pose.

        Use this when you have a fixture's actual pose and want to
        know where it's aiming relative to "forward".

        Args:
            pose: Actual fixture pose

        Returns:
            Relative pose (where the fixture is actually aiming)
        """
        return Pose(
            pan_deg=pose.pan_deg - self.pan_offset_deg,
            tilt_deg=pose.tilt_deg - self.tilt_offset_deg,
        )


class FixtureConfig(BaseModel):
    """Complete configuration for a moving head fixture.

    This is the main configuration object containing all information
    needed to control and sequence a fixture.
    """

    model_config = ConfigDict(frozen=False)

    # Identification
    fixture_id: str = Field(..., description="Unique fixture identifier (e.g., 'MH1', 'MH2')")

    # DMX configuration
    dmx_universe: int = Field(default=1, ge=1, le=64, description="DMX universe number")
    dmx_start_address: int = Field(default=1, ge=1, le=512, description="Starting DMX address")
    channel_count: int = Field(default=16, ge=1, le=128, description="Number of DMX channels used")

    dmx_mapping: DmxMapping = Field(..., description="DMX channel assignments")
    inversions: ChannelInversions = Field(
        default_factory=ChannelInversions, description="Channel inversion flags"
    )

    # Physical capabilities
    pan_tilt_range: PanTiltRange = Field(
        default_factory=PanTiltRange, description="Physical movement range"
    )
    orientation: Orientation = Field(
        default_factory=Orientation, description="Calibration and orientation data"
    )
    limits: MovementLimits = Field(
        default_factory=MovementLimits, description="Safety movement limits"
    )

    capabilities: FixtureCapabilities = Field(
        default_factory=FixtureCapabilities, description="Feature capabilities"
    )
    movement_speed: MovementSpeed = Field(
        default_factory=MovementSpeed, description="Movement speed specifications"
    )

    # Position (optional - for fixtures with physical offsets)
    position: FixturePosition | None = Field(
        default=None, description="Physical mounting position and offsets"
    )

    def get_standard_pose(self, pose_id: str) -> Pose:
        """Get a standard pose by ID.

        Args:
            pose_id: Pose ID from PoseLibrary enum (e.g., "FORWARD", "SOFT_HOME")

        Returns:
            Pose object for the standard position (config Pose, not domain Pose)

        Note:
            This returns a config.fixtures.Pose object.
        """

        # Convert string to PoseLibrary enum
        try:
            pose_enum = PoseLibrary(pose_id.lower())
        except ValueError:
            raise ValueError(f"Unknown pose ID: {pose_id}") from None

        # Get domain pose
        domain_pose = STANDARD_POSES[pose_enum]

        # Convert to config Pose
        return Pose(pan_deg=domain_pose.pan_deg, tilt_deg=domain_pose.tilt_deg)

    def dmx_to_degrees(self, pan_dmx: int, tilt_dmx: int) -> Pose:
        """Convert DMX values to physical degrees.

        Args:
            pan_dmx: Pan DMX value (0-255)
            tilt_dmx: Tilt DMX value (0-255)

        Returns:
            Pose in physical degrees
        """
        # Pan conversion
        pan_offset = pan_dmx - self.orientation.pan_front_dmx
        pan_deg = (pan_offset / 255.0) * self.pan_tilt_range.pan_range_deg

        # Apply inversion
        if self.inversions.pan:
            pan_deg = -pan_deg

        # Tilt conversion
        tilt_offset = tilt_dmx - self.orientation.tilt_zero_dmx
        tilt_deg = (tilt_offset / 255.0) * self.pan_tilt_range.tilt_range_deg

        # Apply inversion
        if self.inversions.tilt:
            tilt_deg = -tilt_deg

        return Pose(pan_deg=pan_deg, tilt_deg=tilt_deg)

    def degrees_to_dmx(self, pose: Pose) -> tuple[int, int]:
        """Convert physical degrees to DMX values.

        Applies inversions and limits automatically.

        Args:
            pose: Physical pose in degrees

        Returns:
            Tuple of (pan_dmx, tilt_dmx) values
        """
        # Apply inversions
        pan_deg = -pose.pan_deg if self.inversions.pan else pose.pan_deg
        tilt_deg = -pose.tilt_deg if self.inversions.tilt else pose.tilt_deg

        # Convert to DMX
        pan_dmx = int(
            self.orientation.pan_front_dmx + (pan_deg / self.pan_tilt_range.pan_range_deg) * 255.0
        )
        tilt_dmx = int(
            self.orientation.tilt_zero_dmx + (tilt_deg / self.pan_tilt_range.tilt_range_deg) * 255.0
        )

        # Apply limits
        pan_dmx = max(self.limits.pan_min, min(self.limits.pan_max, pan_dmx))
        tilt_dmx = max(self.limits.tilt_min, min(self.limits.tilt_max, tilt_dmx))

        return (pan_dmx, tilt_dmx)

    def is_pose_safe(self, pose: Pose) -> bool:
        """Check if a pose is within safety limits.

        Args:
            pose: Pose to check

        Returns:
            True if pose is safe, False otherwise
        """
        pan_dmx, tilt_dmx = self.degrees_to_dmx(pose)

        # Check DMX limits
        if not (self.limits.pan_min <= pan_dmx <= self.limits.pan_max):
            return False
        if not (self.limits.tilt_min <= tilt_dmx <= self.limits.tilt_max):
            return False

        # Check backward pointing if avoided
        if self.limits.avoid_backward and abs(pose.pan_deg) > 90:
            return False

        return True

    def clamp_pan(self, value: int) -> int:
        """Clamp pan DMX value to movement limits.

        Args:
            value: Pan DMX value to clamp

        Returns:
            Clamped pan value within limits
        """
        return max(self.limits.pan_min, min(self.limits.pan_max, value))

    def clamp_tilt(self, value: int) -> int:
        """Clamp tilt DMX value to movement limits.

        Args:
            value: Tilt DMX value to clamp

        Returns:
            Clamped tilt value within limits
        """
        return max(self.limits.tilt_min, min(self.limits.tilt_max, value))

    def is_pan_in_bounds(self, value: int) -> bool:
        """Check if pan DMX value is within movement limits.

        Args:
            value: Pan DMX value to check

        Returns:
            True if within limits, False otherwise
        """
        return self.limits.pan_min <= value <= self.limits.pan_max

    def is_tilt_in_bounds(self, value: int) -> bool:
        """Check if tilt DMX value is within movement limits.

        Args:
            value: Tilt DMX value to check

        Returns:
            True if within limits, False otherwise
        """
        return self.limits.tilt_min <= value <= self.limits.tilt_max

    def deg_to_pan_dmx(self, deg: float) -> int:
        """Convert pan degrees to DMX value with automatic clamping.

        Applies inversions and clamps to movement limits automatically.

        Args:
            deg: Pan angle in degrees (0 = forward, positive = right, negative = left)

        Returns:
            DMX value (0-255) clamped to movement limits
        """
        # Apply inversion
        adjusted_deg = -deg if self.inversions.pan else deg

        # Convert to DMX
        pan_dmx = int(
            self.orientation.pan_front_dmx
            + (adjusted_deg / self.pan_tilt_range.pan_range_deg) * 255.0
        )

        # Clamp to limits
        return self.clamp_pan(pan_dmx)

    def deg_to_tilt_dmx(self, deg: float) -> int:
        """Convert tilt degrees to DMX value with automatic clamping.

        Applies inversions and clamps to movement limits automatically.

        Args:
            deg: Tilt angle in degrees (0 = horizon, positive = up, negative = down)

        Returns:
            DMX value (0-255) clamped to movement limits
        """
        # Apply inversion
        adjusted_deg = -deg if self.inversions.tilt else deg

        # Convert to DMX
        tilt_dmx = int(
            self.orientation.tilt_zero_dmx
            + (adjusted_deg / self.pan_tilt_range.tilt_range_deg) * 255.0
        )

        # Clamp to limits
        return self.clamp_tilt(tilt_dmx)

    def pan_deg_to_dmx_delta(self, deg: float) -> int:
        """Convert pan degrees to DMX delta (offset) without clamping.

        Use this for relative movements or when you need the raw delta value.
        For absolute positioning, use deg_to_pan_dmx() instead.

        Args:
            deg: Pan angle delta in degrees

        Returns:
            DMX delta value (can be negative, not clamped)
        """
        return int(round((deg / self.pan_tilt_range.pan_range_deg) * 255.0))

    def tilt_deg_to_dmx_delta(self, deg: float) -> int:
        """Convert tilt degrees to DMX delta (offset) without clamping.

        Use this for relative movements or when you need the raw delta value.
        For absolute positioning, use deg_to_tilt_dmx() instead.

        Args:
            deg: Tilt angle delta in degrees

        Returns:
            DMX delta value (can be negative, not clamped)
        """
        return int(round((deg / self.pan_tilt_range.tilt_range_deg) * 255.0))


class FixtureInstance(BaseModel):
    """A single fixture instance in the rig.

    Combines fixture configuration with xLights model mapping.
    """

    model_config = ConfigDict(frozen=False)

    fixture_id: str = Field(..., description="Unique fixture identifier")
    config: FixtureConfig = Field(..., description="Fixture configuration")
    xlights_model_name: str = Field(..., description="xLights model name (e.g., 'Dmx MH1')")

    @model_validator(mode="after")
    def sync_fixture_id(self) -> FixtureInstance:
        """Ensure fixture_id matches config."""
        if self.config.fixture_id != self.fixture_id:
            self.config.fixture_id = self.fixture_id
        return self
