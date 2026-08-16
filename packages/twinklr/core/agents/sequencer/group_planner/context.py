"""Context models for GroupPlanner inputs.

Provides structured context for section-level coordination planning.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.feature_engineering.models.vocabulary import VocabularyExtensions
from twinklr.core.sequencer.planning import (
    FocalAssignment,
    MacroPlan,
    MacroSection,
    MotifThread,
    PaletteRef,
    PaletteStop,
)
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import LaneKind


class MacroSectionPlanningInput(BaseModel):
    """Lossless typed macro projection consumed by one group-planner section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    macro_section: MacroSection
    palette_stop: PaletteStop
    resolved_palette: PaletteRef
    motif_threads: list[MotifThread]
    focal_assignment: FocalAssignment

    def reader_projection(self) -> dict[str, Any]:
        """Return the section contract through canonical named readers."""
        return {
            "macro_section": MacroPlan.section_reader_projection(self.macro_section),
            "palette_stop": MacroPlan.palette_stop_reader_projection(self.palette_stop),
            "resolved_palette": MacroPlan.palette_reader_projection(self.resolved_palette),
            "motif_threads": [
                MacroPlan.motif_thread_reader_projection(item) for item in self.motif_threads
            ],
            "focal_assignment": MacroPlan.focal_assignment_reader_projection(self.focal_assignment),
        }


def project_macro_section(plan: MacroPlan, section: MacroSection) -> MacroSectionPlanningInput:
    """Project the full macro contract without converting its intent to strings."""
    section_id = section.section.section_id
    palette_stop = next(
        stop for stop in plan.palette_arc if stop.stop_id == section.palette_role.stop_id
    )
    motif_threads = [
        thread for thread in plan.motif_continuity if thread.motif_id in section.motif_ids
    ]
    focal_assignment = next(item for item in plan.focal_arc if item.section_id == section_id)
    return MacroSectionPlanningInput(
        macro_section=section,
        palette_stop=palette_stop,
        resolved_palette=plan.palette_for_section(section_id),
        motif_threads=motif_threads,
        focal_assignment=focal_assignment,
    )


class SectionPlanningContext(BaseModel):
    """Context for planning a single section.

    Contains all information needed by GroupPlanner to generate
    a SectionCoordinationPlan for one section.

    This is the input to the GroupPlanner orchestrator's run() method.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    macro_input: MacroSectionPlanningInput | None = Field(
        default=None,
        description="Typed macro contract projection for this section",
    )

    # Section identity (from MacroPlan)
    section_id: str = Field(description="Section identifier (e.g., 'verse_1')")
    section_name: str = Field(description="Section type name (e.g., 'verse')")

    # Timing (from MacroPlan section)
    start_ms: int = Field(ge=0, description="Section start in milliseconds")
    end_ms: int = Field(ge=0, description="Section end in milliseconds")

    # Intent (from MacroPlan)
    energy_target: str = Field(description="Energy target (LOW, MED, HIGH, BUILD, etc.)")
    motion_density: str = Field(description="Motion density (SPARSE, MED, BUSY)")
    choreography_style: str = Field(description="Choreography style (IMAGERY, ABSTRACT, HYBRID)")
    lead_targets: list[str] = Field(
        description="Concrete group IDs resolved from LEAD macro focal roles"
    )
    lead_targets_typed: list[dict[str, Any]] = Field(
        default_factory=list,
        description="LEAD macro focal targets in typed form (group/zone/split)",
    )
    support_targets: list[str] = Field(
        default_factory=list,
        description="Concrete group IDs resolved from SUPPORT macro focal roles",
    )
    support_targets_typed: list[dict[str, Any]] = Field(
        default_factory=list,
        description="SUPPORT macro focal targets in typed form (group/zone/split)",
    )
    notes: str | None = Field(default=None, description="Section-specific notes from MacroPlan")

    # Shared context references
    choreo_graph: ChoreographyGraph = Field(description="Choreography graph configuration")
    template_catalog: TemplateCatalog = Field(description="Available templates")
    timing_context: TimingContext = Field(description="Timing resolution context")

    # Theme from MacroSection (required for section coordination)
    theme: ThemeRef | None = Field(
        default=None,
        description="Theme reference from MacroPlan for this section",
    )

    # Motifs from MacroSection (required for template selection)
    motif_ids: list[str] = Field(
        default_factory=list,
        description="Motif IDs from MacroPlan for this section",
    )

    # Resolved palette from the typed macro precedence rule.
    palette: dict[str, Any] | None = Field(
        default=None,
        description="Resolved PaletteRef from MacroPlan for this section",
    )

    # Lyric/narrative context (optional, from lyrics analysis)
    lyric_context: dict[str, Any] | None = Field(
        default=None,
        description="Section-scoped lyric context (story beats, key phrases, characters)",
    )

    # Recipe catalog (optional, from FE pipeline Phase 2)
    recipe_catalog: RecipeCatalog | None = Field(
        default=None,
        description="Recipe catalog with FE-promoted and builtin recipes.",
    )

    @field_serializer("recipe_catalog")
    def serialize_recipe_catalog(
        self, catalog: RecipeCatalog | None
    ) -> list[dict[str, object]] | None:
        """Keep prompt/cache model dumps stable across processes."""
        return catalog.to_canonical_data() if catalog is not None else None

    # Feature Engineering enrichment (optional, from FE pipeline Phase 1)
    # Only sequencer-relevant fields are exposed here.  DMX model-level
    # metrics (layering_style, transition_style) are out of scope.
    color_arc: dict[str, Any] | None = Field(
        default=None,
        description="Section color assignment from Color Arc Engine (palette, shift timing, contrast).",
    )
    propensity_hints: dict[str, Any] | None = Field(
        default=None,
        description="Effect-model affinities from Propensity Miner.",
    )
    style_constraints: dict[str, Any] | None = Field(
        default=None,
        description="Timing style constraints (beat alignment, density).",
    )
    vocabulary_extensions: VocabularyExtensions | None = Field(
        default=None,
        description="Corpus-derived compound motion/energy terms from FE.",
    )
    color_narrative_row: dict[str, Any] | None = Field(
        default=None,
        description="Section color narrative row from FE (dominant class, contrast, hue movement).",
    )
    arc_keyframe: dict[str, Any] | None = Field(
        default=None,
        description="Arc keyframe nearest to this section's position in the song-level color arc.",
    )

    @property
    def duration_ms(self) -> int:
        """Section duration in milliseconds."""
        return self.end_ms - self.start_ms

    def get_target_groups(self, roles: list[str]) -> list[str]:
        """Expand target identifiers to concrete group_ids.

        Args:
            roles: List of target identifiers

        Returns:
            List of group_ids matching those roles
        """
        group_ids: list[str] = []
        groups_by_role = self.choreo_graph.groups_by_role
        for role in roles:
            if role in groups_by_role:
                group_ids.extend(groups_by_role[role])
        return group_ids

    def templates_for_lane(self, lane: LaneKind) -> list[TemplateInfo]:
        """Get templates compatible with a lane.

        Args:
            lane: Lane kind (BASE, RHYTHM, ACCENT)

        Returns:
            List of compatible template catalog entries
        """
        return self.template_catalog.list_by_lane(lane)

    def recipes_for_lane(self, lane: LaneKind) -> list[EffectRecipe]:
        """Get recipes compatible with a lane.

        Args:
            lane: Lane kind (BASE, RHYTHM, ACCENT)

        Returns:
            List of compatible recipes, or empty list if no recipe catalog.
        """
        if self.recipe_catalog is None:
            return []
        return self.recipe_catalog.list_by_lane(lane)
