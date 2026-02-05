"""Shared test fixtures for MacroPlanner tests."""

from twinklr.core.sequencer.planning.models import MotifSpec, PalettePlan, PaletteRef
from twinklr.core.sequencer.vocabulary import EnergyTarget


def make_palette_plan(
    primary_id: str = "core.christmas_traditional",
    alternate_ids: list[str] | None = None,
) -> PalettePlan:
    """Create a valid PalettePlan for testing.

    Args:
        primary_id: Primary palette ID (default: core.christmas_traditional)
        alternate_ids: Optional list of alternate palette IDs

    Returns:
        Valid PalettePlan instance
    """
    alternates = []
    if alternate_ids:
        for alt_id in alternate_ids:
            alternates.append(
                PaletteRef(
                    palette_id=alt_id,
                    role="ACCENT",
                    intensity=1.0,
                )
            )

    return PalettePlan(
        primary=PaletteRef(
            palette_id=primary_id,
            role="PRIMARY",
            intensity=1.0,
        ),
        alternates=alternates,
    )


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
