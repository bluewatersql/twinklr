"""Context models for GroupPlanner inputs.

Provides structured context for section-level coordination planning.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import LaneKind


class SectionPlanningContext(BaseModel):
    """Context for planning a single section.

    Contains all information needed by GroupPlanner to generate
    a SectionCoordinationPlan for one section.

    This is the input to the GroupPlanner orchestrator's run() method.
    """

    model_config = ConfigDict(extra="forbid")

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
    primary_focus_targets: list[str] = Field(description="Primary focus role targets")
    secondary_targets: list[str] = Field(default_factory=list, description="Secondary role targets")
    notes: str | None = Field(default=None, description="Section-specific notes from MacroPlan")

    # Shared context references
    choreo_graph: ChoreographyGraph = Field(description="Choreography graph configuration")
    template_catalog: TemplateCatalog = Field(description="Available templates")
    timing_context: TimingContext = Field(description="Timing resolution context")

    # Optional layer intent from MacroPlan (if provided)
    layer_intents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Layer intents from MacroPlan layering_plan (optional)",
    )

    # Theme from MacroSectionPlan (required for section coordination)
    theme: ThemeRef | None = Field(
        default=None,
        description="Theme reference from MacroPlan for this section",
    )

    # Motifs from MacroSectionPlan (required for template selection)
    motif_ids: list[str] = Field(
        default_factory=list,
        description="Motif IDs from MacroPlan for this section",
    )

    # Palette override from MacroSectionPlan (optional)
    palette: dict[str, Any] | None = Field(
        default=None,
        description="Palette override from MacroPlan for this section",
    )

    # Lyric/narrative context (optional, from lyrics analysis)
    lyric_context: dict[str, Any] | None = Field(
        default=None,
        description="Section-scoped lyric context (story beats, key phrases, characters)",
    )

    @property
    def duration_ms(self) -> int:
        """Section duration in milliseconds."""
        return self.end_ms - self.start_ms

    def get_target_groups(self, roles: list[str]) -> list[str]:
        """Expand role names to concrete group_ids.

        Args:
            roles: List of role names (e.g., ["HERO", "ARCHES"])

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


class GroupPlanningContext(BaseModel):
    """Aggregate context for GroupPlanner orchestration.

    Holds shared resources and provides factory method for
    creating per-section SectionPlanningContext instances.
    """

    model_config = ConfigDict(extra="forbid")

    choreo_graph: ChoreographyGraph = Field(description="Choreography graph configuration")
    template_catalog: TemplateCatalog = Field(description="Available templates")
    timing_context: TimingContext = Field(description="Timing resolution context")

    # Optional global strategy from MacroPlan
    global_story: dict[str, Any] | None = Field(
        default=None,
        description="Global story from MacroPlan (theme, motifs, etc.)",
    )
    layering_plan: dict[str, Any] | None = Field(
        default=None,
        description="Layering plan from MacroPlan",
    )

    def build_section_contexts(
        self,
        section_plans: list[dict[str, Any]],
    ) -> list[SectionPlanningContext]:
        """Build SectionPlanningContext for each section in MacroPlan.

        Args:
            section_plans: List of section_plan dicts from MacroPlan

        Returns:
            List of SectionPlanningContext, one per section
        """
        contexts: list[SectionPlanningContext] = []

        # Extract layer intents if layering_plan provided
        layer_intents: list[dict[str, Any]] = []
        if self.layering_plan and "layers" in self.layering_plan:
            layer_intents = self.layering_plan["layers"]

        for section_plan in section_plans:
            section_info = section_plan.get("section", {})

            # Extract theme reference if provided
            theme_data = section_plan.get("theme")
            theme: ThemeRef | None = None
            if theme_data:
                if isinstance(theme_data, ThemeRef):
                    theme = theme_data
                elif isinstance(theme_data, dict):
                    theme = ThemeRef.model_validate(theme_data)

            ctx = SectionPlanningContext(
                section_id=section_info.get("section_id", "unknown"),
                section_name=section_info.get("name", "unknown"),
                start_ms=section_info.get("start_ms", 0),
                end_ms=section_info.get("end_ms", 0),
                energy_target=section_plan.get("energy_target", "MED"),
                motion_density=section_plan.get("motion_density", "MED"),
                choreography_style=section_plan.get("choreography_style", "HYBRID"),
                primary_focus_targets=section_plan.get("primary_focus_targets", []),
                secondary_targets=section_plan.get("secondary_targets", []),
                notes=section_plan.get("notes"),
                choreo_graph=self.choreo_graph,
                template_catalog=self.template_catalog,
                timing_context=self.timing_context,
                layer_intents=layer_intents,
                theme=theme,
                motif_ids=section_plan.get("motif_ids", []),
                palette=section_plan.get("palette"),
            )
            contexts.append(ctx)

        return contexts
