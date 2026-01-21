"""Sequencer factory for routing jobs to domain-specific sequencers.

The factory pattern allows BlinkB0t to support multiple sequencing domains
(moving heads, RGB strips, lasers, matrix panels, etc.) with a unified interface.

Example usage:
    # Get sequencer for moving heads
    from blinkb0t.core.domains.sequencing import get_sequencer

    sequencer = get_sequencer('movingheads')
    sequencer.apply_plan(
        xsq_in='input.xsq',
        xsq_out='output.xsq',
        plan=plan_data,
        job_config=config,
        song_features=features
    )

    # Future: Get sequencer for RGB strips
    sequencer = get_sequencer('rgb')
    sequencer.apply_plan(...)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.base import BaseSequencer

logger = logging.getLogger(__name__)


class SequencerFactory:
    """Factory for creating domain-specific sequencers.

    This factory maintains a registry of sequencers and provides instances
    on demand. Sequencers are registered at module import time using the
    auto-registration pattern.
    """

    def __init__(self) -> None:
        """Initialize the factory with an empty registry."""
        self._sequencers: dict[str, type[BaseSequencer]] = {}

    def register(self, domain: str, sequencer_class: type[BaseSequencer]) -> None:
        """Register a sequencer for a domain.

        Args:
            domain: Domain name (e.g., 'movingheads', 'rgb', 'laser')
            sequencer_class: Sequencer class (must inherit from BaseSequencer)

        Raises:
            ValueError: If domain is already registered
        """
        if domain in self._sequencers:
            logger.warning(f"Sequencer for domain '{domain}' already registered, overwriting")
        self._sequencers[domain] = sequencer_class
        logger.debug(f"Registered sequencer for domain: {domain}")

    def get_sequencer(self, domain: str, *, job_config: Any, fixtures: Any) -> BaseSequencer:
        """Get sequencer instance for domain.

        Args:
            domain: Domain name (e.g., 'movingheads', 'rgb', 'laser')
            job_config: Job configuration (domain-specific)
            fixtures: Fixture group configuration (domain-specific)

        Returns:
            Sequencer instance for the specified domain

        Raises:
            ValueError: If no sequencer registered for domain
        """
        if domain not in self._sequencers:
            available = ", ".join(self.list_domains())
            raise ValueError(
                f"No sequencer registered for domain: '{domain}'. "
                f"Available domains: {available or 'none'}"
            )
        sequencer_class = self._sequencers[domain]
        logger.debug(f"Creating sequencer instance for domain: {domain}")
        return sequencer_class(job_config=job_config, fixtures=fixtures)

    def list_domains(self) -> list[str]:
        """List all registered domains.

        Returns:
            List of registered domain names
        """
        return list(self._sequencers.keys())

    def has_domain(self, domain: str) -> bool:
        """Check if domain is registered.

        Args:
            domain: Domain name to check

        Returns:
            True if domain is registered, False otherwise
        """
        return domain in self._sequencers


# Global factory instance (singleton pattern)
_factory = SequencerFactory()


def register_sequencer(domain: str, sequencer_class: type[BaseSequencer]) -> None:
    """Register a sequencer (convenience function).

    This is the primary API for registering sequencers. Called automatically
    by domain modules during import.

    Args:
        domain: Domain name (e.g., 'movingheads', 'rgb', 'laser')
        sequencer_class: Sequencer class (must inherit from BaseSequencer)

    Example:
        from blinkb0t.core.domains.sequencing.factory import register_sequencer
        from .sequencer import MovingHeadSequencer

        register_sequencer('movingheads', MovingHeadSequencer)
    """
    _factory.register(domain, sequencer_class)


def get_sequencer(domain: str, *, job_config: Any, fixtures: Any) -> BaseSequencer:
    """Get sequencer for domain (convenience function).

    This is the primary API for getting sequencer instances.

    Args:
        domain: Domain name (e.g., 'movingheads', 'rgb', 'laser')
        job_config: Job configuration (domain-specific)
        fixtures: Fixture group configuration (domain-specific)

    Returns:
        Sequencer instance for the specified domain

    Raises:
        ValueError: If no sequencer registered for domain

    Example:
        sequencer = get_sequencer('movingheads', job_config=config, fixtures=fixtures)
        sequencer.apply_plan(xsq_in='in.xsq', xsq_out='out.xsq', ...)
    """
    return _factory.get_sequencer(domain, job_config=job_config, fixtures=fixtures)


def list_domains() -> list[str]:
    """List all registered domains (convenience function).

    Returns:
        List of registered domain names
    """
    return _factory.list_domains()


def has_domain(domain: str) -> bool:
    """Check if domain is registered (convenience function).

    Args:
        domain: Domain name to check

    Returns:
        True if domain is registered, False otherwise
    """
    return _factory.has_domain(domain)
