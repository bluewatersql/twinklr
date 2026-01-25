"""Generate curve visualization plots.

This module creates matplotlib plots of curves for visual inspection.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_curve(
    samples: list[float],
    *,
    title: str,
    output_path: Path,
    space: str = "dmx",  # Changed default to DMX
    bar_range: tuple[float, float],
    curve_type: str | None = None,
    section_bar_range: tuple[float, float] | None = None,
) -> None:
    """Generate curve plot PNG.

    Creates a simple line plot of the curve with minimal styling
    for clarity.

    Args:
        samples: Curve sample values
        title: Plot title
        output_path: Path to save PNG
        space: "norm" (0-1) or "dmx" (0-255)
        bar_range: (start_bar, end_bar) for x-axis
        curve_type: Optional curve type/name to display
        section_bar_range: Optional (t0, t1) section boundaries to mark

    Example:
        >>> plot_curve(
        ...     samples=[0.0, 0.5, 1.0, 0.5, 0.0],
        ...     title="Verse 1 • OUTER_LEFT • PAN",
        ...     output_path=Path("plot.png"),
        ...     space="dmx",
        ...     bar_range=(1.0, 21.0),
        ...     curve_type="movement_sine",
        ...     section_bar_range=(1.0, 21.0),
        ... )
    """
    if not samples:
        logger.warning(f"No samples to plot for {title}")
        return

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 3), dpi=100)

    # X-axis: bars
    start_bar, end_bar = bar_range
    x = np.linspace(start_bar, end_bar, len(samples))

    # Y-axis: Always use DMX space (0-255)
    y = np.array(samples) * 255
    ax.set_ylim(0, 255)
    ax.set_ylabel("DMX Value", fontsize=10)

    # Plot main curve
    ax.plot(x, y, linewidth=1.5, color="#2E86AB", label="Curve")

    # Add section boundary markers if provided
    if section_bar_range:
        t0, t1 = section_bar_range
        ax.axvline(
            t0, color="#E63946", linestyle="--", linewidth=1, alpha=0.7, label="Section Start"
        )
        ax.axvline(t1, color="#E63946", linestyle="--", linewidth=1, alpha=0.7, label="Section End")

    # Add curve type to title if provided
    display_title = title
    if curve_type:
        display_title = f"{title}\n[{curve_type}]"

    ax.set_xlabel("Bars", fontsize=10)
    ax.set_title(display_title, fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.3, linewidth=0.5)

    # Add legend if we have markers
    if section_bar_range:
        ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

    # Tight layout
    fig.tight_layout()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    logger.debug(f"Saved plot: {output_path.name}")
