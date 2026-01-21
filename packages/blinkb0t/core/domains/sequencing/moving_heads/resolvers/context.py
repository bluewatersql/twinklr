"""Movement resolver interface and context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
    from blinkb0t.core.config.models import JobConfig
    from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect
    from blinkb0t.core.domains.sequencing.models.xsq import XSequence
    from blinkb0t.core.domains.sequencing.moving_heads.context import SequencerContext


class MovementResolver(ABC):
    """Interface for resolving movement instructions to sequenced effects.

    Handlers implement this interface to convert plan instructions into
    SequencedEffect objects for the channel integration pipeline.
    """

    @abstractmethod
    def resolve(
        self,
        instruction: dict[str, Any],
        context: ResolverContext,
        targets: list[str],
    ) -> list[SequencedEffect]:
        """Resolve instruction to sequenced effects.

        Args:
            instruction: Full instruction dict (movement, dimmer, geometry, etc.)
            context: Resolver context with all needed dependencies
            targets: List of target fixture names

        Returns:
            List of SequencedEffect objects (usually 1, but multi-phase patterns may return multiple)
        """
        pass


@dataclass
class ResolverContext:
    """Extended context for movement resolvers.

    Extends SequencerContext with additional information needed for
    complete effect resolution (xsq, fixtures, instruction, section, etc.).
    """

    sequencer_context: SequencerContext
    xsq: XSequence
    fixtures: FixtureGroup
    instruction: dict[str, Any]
    section: dict[str, Any]
    job_config: JobConfig

    def __init__(
        self,
        *,
        sequencer_context: SequencerContext,
        xsq: XSequence,
        fixtures: FixtureGroup,
        instruction: dict[str, Any],
        section: dict[str, Any],
        job_config: JobConfig,
    ) -> None:
        """Initialize resolver context.

        Args:
            sequencer_context: Base sequencer context
            xsq: XSequence instance
            fixtures: Fixture group for this instruction
            instruction: Instruction dictionary
            section: Section dictionary
            job_config: Job configuration
        """
        self.sequencer_context = sequencer_context
        self.xsq = xsq
        self.fixtures = fixtures
        self.instruction = instruction
        self.section = section
        self.job_config = job_config

    @property
    def first_fixture(self) -> FixtureInstance:
        """Get first fixture from fixture group (convenience)."""
        expanded = self.fixtures.expand_fixtures()
        if not expanded:
            raise ValueError("Fixture group is empty")
        return expanded[0]

    @property
    def start_ms(self) -> int:
        """Get instruction start time in milliseconds.

        Checks instruction-level timing first, falls back to section timing.
        """
        # Check for flat start_ms first (new format)
        if "start_ms" in self.instruction:
            return int(self.instruction["start_ms"])
        # Check for nested time_ms (old format)
        inst_time = self.instruction.get("time_ms")
        if inst_time:
            return int(inst_time.get("start", 0))
        # Fall back to section timing (flat format)
        if "start_ms" in self.section:
            return int(self.section["start_ms"])
        # Fall back to section timing (nested format)
        section_time = self.section.get("time_ms", {})
        return int(section_time.get("start", 0))

    @property
    def end_ms(self) -> int:
        """Get instruction end time in milliseconds.

        Checks instruction-level timing first, falls back to section timing.
        """
        # Check for flat end_ms first (new format)
        if "end_ms" in self.instruction:
            return int(self.instruction["end_ms"])
        # Check for nested time_ms (old format)
        inst_time = self.instruction.get("time_ms")
        if inst_time:
            return int(inst_time.get("end", 0))
        # Fall back to section timing (flat format)
        if "end_ms" in self.section:
            return int(self.section["end_ms"])
        # Fall back to section timing (nested format)
        section_time = self.section.get("time_ms", {})
        return int(section_time.get("end", 0))

    @property
    def duration_ms(self) -> int:
        """Get section duration in milliseconds."""
        return self.end_ms - self.start_ms

    # Delegate to SequencerContext for backward compatibility
    @property
    def fixture(self) -> FixtureInstance:
        """Get fixture from sequencer context."""
        return self.sequencer_context.fixture

    @property
    def boundaries(self) -> Any:
        """Get boundaries from sequencer context."""
        return self.sequencer_context.boundaries

    @property
    def beats_s(self) -> list[float]:
        """Get beats from sequencer context."""
        return self.sequencer_context.beats_s

    @property
    def song_features(self) -> dict[str, Any]:
        """Get song features from sequencer context."""
        return self.sequencer_context.song_features
