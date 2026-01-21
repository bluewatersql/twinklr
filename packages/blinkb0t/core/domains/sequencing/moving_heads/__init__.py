"""Moving head choreography system.

Provides template loading, sequencing, and management for moving head lighting.

Components:
- Manager: Orchestrates the complete pipeline
- Sequencer: Applies plans to XSQ files
- Templates: Template loading and processing
- Resolvers: Movement and target resolution
- Handlers: Effect handlers
"""

from .manager import MovingHeadManager
from .sequencer import MovingHeadSequencer

__all__ = [
    "MovingHeadManager",
    "MovingHeadSequencer",
]
