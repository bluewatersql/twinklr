"""Channel specification system for DMX channel overlay architecture.

This module provides the foundation for channel overlay system,
allowing channels (shutter, color, gobo) to be specified independently of
movement templates.

Key Components:
- ChannelDefaults: Job-level default channel states
- ChannelSpecification: Section-level channel overrides
- ResolvedChannels: Final resolved channel values
- ChannelResolver: Resolution logic (defaults + overrides)
- BasicChannelValidator: Validation of channel combinations
"""

from blinkb0t.core.config.models import ChannelDefaults
from blinkb0t.core.domains.sequencing.channels.resolver import ChannelResolver
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.channels.validation import (
    BasicChannelValidator,
    ChannelValidator,
)
from blinkb0t.core.domains.sequencing.models.channels import (
    ChannelEffect,
    ChannelSpecification,
    DmxEffect,
    ResolvedChannels,
    SequencedEffect,
)

__all__ = [
    "ChannelDefaults",
    "ChannelEffect",
    "ChannelSpecification",
    "ChannelState",
    "DmxEffect",
    "ResolvedChannels",
    "SequencedEffect",
    "ChannelResolver",
    "BasicChannelValidator",
    "ChannelValidator",
]
