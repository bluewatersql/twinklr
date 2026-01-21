"""Base class for all domain-specific sequencers.

This module defines the common interface that all sequencing domains must implement.
Each domain (moving heads, RGB, lasers, etc.) has its own sequencer inheriting from BaseSequencer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSequencer(ABC):
    """Base class for all domain-specific sequencers.

    Each sequencing domain (moving heads, RGB strips, lasers, etc.) must
    inherit from this class and implement the apply_plan method.

    The sequencer is responsible for:
    - Loading and modifying xLights sequence files (.xsq)
    - Interpreting domain-specific plans
    - Generating DMX/effect data
    - Handling timing, gaps, and transitions

    Configuration is provided at construction time and cached for the session.

    Example:
        # Create sequencer with configuration
        sequencer = MovingHeadSequencer(
            job_config=job_config,
            fixtures=fixtures
        )

        # Apply plan to sequence
        sequencer.apply_plan(
            xsq_in='input.xsq',
            xsq_out='output.xsq',
            plan=plan_data,
            song_features=features
        )
    """

    def __init__(self, *, job_config: Any, fixtures: Any):
        """Initialize sequencer with configuration.

        Args:
            job_config: Job configuration (domain-specific)
            fixtures: Fixture group configuration (domain-specific)
        """
        self.job_config = job_config
        self.fixtures = fixtures

    @abstractmethod
    def apply_plan(
        self,
        *,
        xsq_in: str,
        xsq_out: str,
        plan: dict[str, Any],
        song_features: dict[str, Any],
    ) -> None:
        """Apply a plan to a sequence file.

        Args:
            xsq_in: Input xLights sequence file path (.xsq)
            xsq_out: Output xLights sequence file path (.xsq)
            plan: Choreography plan to apply (domain-specific format)
            song_features: Audio analysis features (tempo, beats, energy, etc.)

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        pass
