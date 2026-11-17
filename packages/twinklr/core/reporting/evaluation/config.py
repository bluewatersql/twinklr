"""Configuration model for evaluation reports."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvalConfig(BaseModel):
    """Evaluation report configuration.

    Controls thresholds, plotting, output format and plan validation.

    Example:
        >>> config = EvalConfig(plot_all_roles=True)
        >>> config.enable_heuristic_validation
        True
    """

    # Thresholds
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
    model_config = {"frozen": True}
