"""Shared test fixtures for MacroPlanner tests."""

from twinklr.core.sequencer.planning.models import MotifSpec
from twinklr.core.sequencer.vocabulary import EnergyTarget


def make_motif_spec(
    motif_id: str,
    description: str | None = None,
    energy: list[EnergyTarget] | None = None,
) -> MotifSpec:
    """Create a valid MotifSpec for testing.

    Args:
        motif_id: Motif identifier (e.g. 'snowflakes')
        description: Optional description (auto-generated if None, min 10 chars)
        energy: Optional energy levels (defaults to [MED])

    Returns:
        Valid MotifSpec instance
    """
    if description is None:
        # Auto-generate description meeting minimum length (10 chars)
        motif_name = motif_id.replace("_", " ").title()
        description = f"{motif_name} visual motif for testing purposes"

    if energy is None:
        energy = [EnergyTarget.MED]

    return MotifSpec(
        motif_id=motif_id,
        tags=[f"motif.{motif_id}"],
        description=description,
        preferred_energy=energy,
        usage_notes=f"Test usage notes for {motif_id} motif in choreography",
    )
