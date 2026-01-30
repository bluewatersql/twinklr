"""Domain manager base class for BlinkB0t.

This module provides the abstract base class that all domain-specific
managers must implement. Each domain (moving heads, RGB, lasers, etc.)
creates a manager that orchestrates domain-specific processing while
leveraging universal session services.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.session import BlinkB0tSession


class DomainManager(ABC):
    """Abstract base class for domain-specific managers.

    Each sequencing domain (moving heads, RGB strips, lasers, matrix panels, etc.)
    implements this class to provide domain-specific functionality while leveraging
    universal session services (audio analysis, sequence fingerprinting, configs).

    The manager pattern:
    - Session provides universal infrastructure (configs, audio, sequence analysis)
    - Manager provides domain-specific logic (planning, sequencing, effect generation)
    - Manager uses session.audio and session.sequence for shared services

    Subclasses must implement:
    - run_pipeline() - Execute the complete domain-specific pipeline
    """

    def __init__(self, session: BlinkB0tSession):
        """Initialize domain manager with session.

        Args:
            session: BlinkB0t session providing universal services
        """
        self.session = session

    @abstractmethod
    def run_pipeline(
        self,
        audio_path: str | Path,
        xsq_in: str | Path,
        xsq_out: str | Path,
    ) -> None:
        """Run the complete domain-specific pipeline.

        This method must be implemented by each domain to provide
        their specific pipeline logic (planning, sequencing, etc.).

        Typically involves:
        1. Analyze audio (via session.audio)
        2. Fingerprint sequence (via session.sequence)
        3. Generate domain-specific plan
        4. Apply plan to sequence

        Args:
            audio_path: Path to audio file
            xsq_in: Input xLights sequence path
            xsq_out: Output xLights sequence path

        Raises:
            NotImplementedError: If subclass doesn't implement this
        """
        pass
