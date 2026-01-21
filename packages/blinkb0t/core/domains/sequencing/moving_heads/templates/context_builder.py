"""Builder for creating ResolverContext (separates context construction logic)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
from blinkb0t.core.domains.sequencing.models.xsq import XSequence

if TYPE_CHECKING:
    from blinkb0t.core.config.models import JobConfig

from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import ResolverContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.boundary_enforcer import (
    BoundaryEnforcer,
)


class ResolverContextBuilder:
    """Builds ResolverContext for handler invocation.

    Centralizes complex context construction logic, following Single Responsibility.
    """

    def __init__(
        self,
        sequencer_context: SequencerContext,
        xsq: XSequence,
        job_config: JobConfig,
    ):
        """Initialize builder with shared dependencies.

        Args:
            sequencer_context: Shared sequencer context
            xsq: XSequence object
            job_config: Job configuration
        """
        self.sequencer_context = sequencer_context
        self.xsq = xsq
        self.job_config = job_config

    def build_context(
        self,
        fixture: FixtureInstance,
        instruction: dict[str, Any],
        section: dict[str, Any],
        fixtures: FixtureGroup,
    ) -> ResolverContext:
        """Build ResolverContext for handler invocation.

        Args:
            fixture: Target fixture
            instruction: Handler instruction
            section: Section metadata
            fixtures: Fixture group

        Returns:
            Complete ResolverContext
        """
        # Update sequencer context fixture if needed
        if self.sequencer_context.fixture != fixture:
            # Create new boundary enforcer for this fixture
            boundaries = BoundaryEnforcer(fixture)
            # Update context (immutable, so create new)
            sequencer_context = SequencerContext(
                fixture=fixture,
                boundaries=boundaries,
                dmx_curve_mapper=self.sequencer_context.dmx_curve_mapper,
                beats_s=self.sequencer_context.beats_s,
                song_features=self.sequencer_context.song_features,
            )
        else:
            sequencer_context = self.sequencer_context

        return ResolverContext(
            sequencer_context=sequencer_context,
            xsq=self.xsq,
            fixtures=fixtures,
            instruction=instruction,
            section=section,
            job_config=self.job_config,
        )
