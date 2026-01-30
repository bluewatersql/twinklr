"""Configuration model for evaluation reports."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvalConfig(BaseModel):
    """Evaluation report configuration.

    Controls sampling, thresholds, plotting, and output format.

    Example:
        >>> config = EvalConfig(samples_per_bar=128, plot_all_roles=True)
        >>> config.clamp_warning_threshold
        0.05
    """

    # Sampling
    samples_per_bar: int = Field(
        default=96,
        ge=1,
        description="Number of samples per bar for curve analysis",
    )

    # Thresholds
    clamp_warning_threshold: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Clamp percentage threshold for warnings (0.05 = 5%)",
    )
    clamp_error_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Clamp percentage threshold for errors (0.20 = 20%)",
    )
    loop_delta_threshold: float = Field(
        default=0.05,
        ge=0.0,
        description="Loop continuity threshold (normalized)",
    )
    gap_warning_bars: float = Field(
        default=0.5,
        ge=0.0,
        description="Gap size threshold for warnings (bars)",
    )
    max_concurrent_layers: int = Field(
        default=3,
        ge=1,
        description="Maximum expected concurrent layers",
    )

    # Plotting
    roles_to_plot: list[str] | None = Field(
        default=None,
        description="Specific roles to plot (None = auto-select)",
    )
    plot_all_roles: bool = Field(
        default=False,
        description="Plot all roles (overrides roles_to_plot)",
    )
    include_dmx_plots: bool = Field(
        default=False,
        description="Include DMX space plots in addition to normalized",
    )

    # Output
    output_format: list[str] = Field(
        default_factory=lambda: ["json", "md"],
        description="Output formats: json, md, html",
    )

    # Phase 2: Validation toggles
    enable_heuristic_validation: bool = Field(
        default=True,
        description="Enable heuristic plan validation",
    )
    enable_physics_checks: bool = Field(
        default=True,
        description="Enable physical constraint checking",
    )
    enable_compliance_checks: bool = Field(
        default=True,
        description="Enable template compliance verification",
    )
    enable_continuity_checks: bool = Field(
        default=True,
        description="Enable cross-section continuity analysis",
    )

    # Phase 2: Physics limits
    max_pan_speed_deg_per_sec: float = Field(
        default=540.0,
        ge=0.0,
        description="Maximum pan speed (degrees/second)",
    )
    max_tilt_speed_deg_per_sec: float = Field(
        default=270.0,
        ge=0.0,
        description="Maximum tilt speed (degrees/second)",
    )
    max_acceleration_deg_per_sec2: float = Field(
        default=1000.0,
        ge=0.0,
        description="Maximum acceleration (degrees/second²)",
    )
    min_settle_time_ms: float = Field(
        default=50.0,
        ge=0.0,
        description="Minimum time to settle at position (milliseconds)",
    )

    # Phase 2: Continuity thresholds
    position_discontinuity_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Position change threshold for discontinuity warnings (normalized)",
    )
    velocity_discontinuity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description="Velocity change threshold for harsh transitions (normalized/sec)",
    )
    dimmer_snap_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Dimmer change threshold for snap warnings (normalized)",
    )

    model_config = {"frozen": True}
