"""Sequencing domain - audio analysis, planning, and sequence generation.

This module provides the unified interface for all sequencing domains (moving heads,
RGB strips, lasers, etc.). It includes:

- Shared utilities: audio analysis, xLights format handling, versioning
- Sequencer factory: routes jobs to domain-specific sequencers
- Domain modules: movingheads (with auto-registration)

Example:
    from blinkb0t.core.domains.sequencing import get_sequencer

    # Create sequencer with configuration
    sequencer = get_sequencer('movingheads')

    # Or directly instantiate (use explicit import path):
    from blinkb0t.core.domains.sequencing.moving_heads import MovingHeadSequencer
    sequencer = MovingHeadSequencer(job_config=config, fixtures=fixtures)

    # Apply plan
    sequencer.apply_plan(
        xsq_in='in.xsq',
        xsq_out='out.xsq',
        plan=plan,
        song_features=features
    )
"""

# Import factory functions only - no domain modules at package level
# Domain modules are imported explicitly when needed to avoid circular dependencies
from blinkb0t.core.domains.sequencing.factory import (
    get_sequencer,
    has_domain,
    list_domains,
    register_sequencer,
)

__all__ = [
    # Factory API (primary interface)
    "get_sequencer",
    "register_sequencer",
    "list_domains",
    "has_domain",
]
