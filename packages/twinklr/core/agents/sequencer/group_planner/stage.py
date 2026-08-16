"""GroupPlanner pipeline stage.

Wraps GroupPlannerOrchestrator for pipeline execution with FAN_OUT pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.group_planner.context import (
    SectionPlanningContext,
    project_macro_section,
)
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.pipeline.result import failure_result, success_result
from twinklr.core.sequencer.planning import GroupPlanSet, SectionCoordinationPlan
from twinklr.core.sequencer.planning.group_plan import NarrativeAssetDirective

if TYPE_CHECKING:
    from twinklr.core.agents.audio.lyrics.models import (
        KeyPhrase,
        LyricContextModel,
        StoryBeat,
    )
    from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
    from twinklr.core.audio.models.song_bundle import SongBundle
    from twinklr.core.feature_engineering.loader import FEArtifactBundle
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult
    from twinklr.core.sequencer.planning import MacroSection
    from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
    from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
    from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog

logger = logging.getLogger(__name__)


class GroupPlannerStage:
    """Pipeline stage for group planning (per-section).

    Designed for FAN_OUT execution pattern. Each invocation processes
    one MacroSection, builds its own SectionPlanningContext independently,
    and returns one SectionCoordinationPlan.

    Constructor args (configuration):
        - choreo_graph: ChoreographyGraph
        - template_catalog: TemplateCatalog

    State retrieved from PipelineContext (set by upstream stages):
        - audio_bundle: SongBundle (for building timing_context)
        - audio_profile: AudioProfileModel (optional, for enhanced context)
        - lyric_context: LyricContextModel (optional, for narrative context)
        - macro_plan: Full typed MacroPlan

    Usage with FAN_OUT:
        StageDefinition(
            id="groups",
            stage=GroupPlannerStage(
                choreo_graph=choreo_graph,
                template_catalog=template_catalog,
            ),
            pattern=ExecutionPattern.FAN_OUT,
            inputs=["sections"],  # List[MacroSection]
        )

    The pipeline executor will:
    1. Receive list of MacroSection from upstream
    2. Execute this stage once per section (in parallel)
    3. Each invocation builds its context independently (precisely scoped)
    4. Collect results into list of SectionCoordinationPlan

    Input: MacroSection (single section from MacroPlan)
    Output: SectionCoordinationPlan
    """

    def __init__(
        self,
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
        recipe_catalog: RecipeCatalog | None = None,
        fe_bundle: FEArtifactBundle | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        macro_choreo_graph: ChoreographyGraph | None = None,
    ) -> None:
        """Initialize group planner stage.

        Args:
            choreo_graph: Choreography graph configuration
            template_catalog: Available templates for coordination
            recipe_catalog: Unified recipe catalog (builtins + promoted)
            fe_bundle: Loaded FE artifacts for context enrichment
            max_iterations: Max refinement iterations per section (default: 3)
            min_pass_score: Min score for section approval (default: 7.0)
        """
        self.choreo_graph = choreo_graph
        self.template_catalog = template_catalog
        self.recipe_catalog = recipe_catalog
        self.fe_bundle = fe_bundle
        self.max_iterations = max_iterations
        self.min_pass_score = min_pass_score
        self.macro_choreo_graph = macro_choreo_graph or choreo_graph

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "group_planner"

    async def execute(
        self,
        input: MacroSection,
        context: PipelineContext,
    ) -> StageResult[SectionCoordinationPlan]:
        """Generate section coordination plan.

        Builds SectionPlanningContext from the MacroSection and
        shared context in PipelineContext.state, then runs the orchestrator.

        Args:
            input: MacroSection for one section
            context: Pipeline context with provider, config, and shared state

        Returns:
            StageResult containing SectionCoordinationPlan

        Side Effects:
            - Adds "group_planner_iterations_{section_id}" to context.metrics
            - Adds "group_planner_tokens_{section_id}" to context.metrics
        """
        from twinklr.core.agents.sequencer.group_planner.specs import (
            get_planner_spec,
            get_section_judge_spec,
        )
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.pipeline.execution import execute_step

        section_id = input.section.section_id

        try:
            logger.debug(f"Generating coordination plan for section: {section_id}")

            # Build section context (validates state presence)
            section_context = self._build_section_context(input, context)

            # Create orchestrator with pipeline context dependencies
            orchestrator = GroupPlannerOrchestrator(
                provider=context.provider,
                planner_spec=get_planner_spec(config=context.job_config.agent.plan_agent),
                section_judge_spec=get_section_judge_spec(
                    config=context.job_config.agent.judge_agent
                ),
                max_iterations=self.max_iterations,
                min_pass_score=self.min_pass_score,
                llm_logger=context.llm_logger,
            )
            pipeline_run_id = context.get_state("pipeline_run_id")

            return await execute_step(
                stage_name=f"{self.name}_{section_id}",
                context=context,
                compute=lambda: orchestrator.run(section_context, run_id=pipeline_run_id),
                result_extractor=lambda result: self._extract_plan_result(result, section_context),
                result_type=IterationResult,
                cache_key_fn=lambda: orchestrator.get_cache_key(section_context),
                cache_version="1",
                cache_domain=self.name,  # Group all sections under "group_planner"
            )

        except ValueError as e:
            logger.error(f"Invalid section context for {section_id}: {e}")
            return failure_result(f"Invalid section context: {e}", stage_name=self.name)
        except Exception as e:
            logger.exception(f"Section {section_id} planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    @staticmethod
    def _extract_plan_result(
        result: Any,
        section_context: SectionPlanningContext,
    ) -> SectionCoordinationPlan:
        """Normalize fresh or cached results and stamp authoritative macro fields."""
        if result.plan is None:
            raise ValueError("IterationResult.plan is None")
        plan = (
            SectionCoordinationPlan.model_validate(result.plan)
            if isinstance(result.plan, dict)
            else result.plan
        )
        GroupPlannerOrchestrator._stamp_macro_owned_fields(plan, section_context)
        return plan

    def _build_section_context(
        self, input: MacroSection, context: PipelineContext
    ) -> SectionPlanningContext:
        """Build section planning context from input and pipeline state.

        Args:
            input: MacroSection for this section
            context: Pipeline context with shared state

        Returns:
            SectionPlanningContext for orchestrator

        Raises:
            ValueError: If required state is missing
        """
        # Retrieve shared context from pipeline state
        audio_bundle = context.get_state("audio_bundle")
        macro_plan = context.get_state("macro_plan")
        lyric_context_model = context.get_state("lyric_context")

        if audio_bundle is None:
            raise ValueError("Missing 'audio_bundle' in context.state")

        # Build timing context from audio bundle with section bounds
        timing_context = self._build_timing_context(
            audio_bundle,
            section_id=input.section.section_id,
            section_start_ms=input.section.start_ms,
            section_end_ms=input.section.end_ms,
        )

        from twinklr.core.sequencer.planning import FocalRoleKind, MacroPlan

        if macro_plan is None:
            raise ValueError("Missing 'macro_plan' in context.state")
        normalized_macro = MacroPlan.model_validate(
            macro_plan.model_dump() if hasattr(macro_plan, "model_dump") else macro_plan,
            context={"choreo_graph": self.macro_choreo_graph},
        )
        macro_section = next(
            (
                section
                for section in normalized_macro.sections
                if section.section.section_id == input.section.section_id
            ),
            None,
        )
        if macro_section is None:
            raise ValueError(f"MacroPlan has no section '{input.section.section_id}'")
        macro_input = project_macro_section(normalized_macro, macro_section)

        # Build section-scoped lyric context
        section_lyric_context = self._build_section_lyric_context(
            lyric_context_model,
            section_id=input.section.section_id,
            start_ms=input.section.start_ms,
            end_ms=input.section.end_ms,
        )

        lead_focal_targets = [
            role.target for role in macro_section.focal_roles if role.role == FocalRoleKind.LEAD
        ]
        support_focal_targets = [
            role.target for role in macro_section.focal_roles if role.role == FocalRoleKind.SUPPORT
        ]
        resolved_lead_targets = self._resolve_focus_targets(lead_focal_targets)
        resolved_support_targets = self._resolve_focus_targets(support_focal_targets)
        typed_lead_targets = self._serialize_focus_targets(
            [target for target in lead_focal_targets if self._resolve_focus_targets([target])]
        )
        typed_support_targets = self._serialize_focus_targets(
            [target for target in support_focal_targets if self._resolve_focus_targets([target])]
        )
        # A macro LEAD may belong exclusively to the MH backend.  The display planner
        # still needs a concrete local focus; promote its highest available SUPPORT
        # while the full macro contract remains intact in ``macro_input``.
        if not resolved_lead_targets and resolved_support_targets:
            resolved_lead_targets = resolved_support_targets
            typed_lead_targets = typed_support_targets
            resolved_support_targets = []
            typed_support_targets = []

        fe_fields = self._extract_fe_fields(section_id=input.section.section_id)

        return SectionPlanningContext(
            macro_input=macro_input,
            section_id=macro_section.section.section_id,
            section_name=macro_section.section.name,
            start_ms=macro_section.section.start_ms,
            end_ms=macro_section.section.end_ms,
            energy_target=macro_section.energy_target.value,
            motion_density=macro_section.motion_density.value,
            choreography_style=macro_section.choreography_style.value,
            lead_targets=resolved_lead_targets,
            lead_targets_typed=typed_lead_targets,
            support_targets=resolved_support_targets,
            support_targets_typed=typed_support_targets,
            notes=macro_section.notes,
            choreo_graph=self.choreo_graph,
            template_catalog=self.template_catalog,
            timing_context=timing_context,
            theme=macro_section.theme,
            motif_ids=macro_section.motif_ids,
            palette=macro_input.resolved_palette.model_dump(mode="json"),
            lyric_context=section_lyric_context,
            recipe_catalog=self.recipe_catalog,
            **fe_fields,
        )

    def _extract_fe_fields(self, *, section_id: str) -> dict[str, Any]:
        """Extract FE context fields from the loaded artifact bundle.

        Args:
            section_id: Current section identifier for section-specific lookups.

        Returns:
            Dict of keyword arguments for SectionPlanningContext FE fields.
            All values default to None when fe_bundle is absent.
        """
        if self.fe_bundle is None:
            return {}

        result: dict[str, Any] = {}

        if self.fe_bundle.color_arc is not None:
            section_assignment = self._find_section_color_assignment(
                self.fe_bundle.color_arc, section_id
            )
            if section_assignment is not None:
                result["color_arc"] = section_assignment.model_dump(mode="json")

        if self.fe_bundle.propensity_index is not None:
            result["propensity_hints"] = self.fe_bundle.propensity_index.model_dump(mode="json")
        if self.fe_bundle.style_fingerprint is not None:
            fp = self.fe_bundle.style_fingerprint
            result["style_constraints"] = {
                "timing_style": fp.timing_style.model_dump(mode="json"),
            }
            if hasattr(fp, "transition_style") and fp.transition_style is not None:
                result["style_constraints"]["transition_style"] = fp.transition_style.model_dump(
                    mode="json"
                )
            if hasattr(fp, "layering_style") and fp.layering_style is not None:
                result["style_constraints"]["layering_style"] = fp.layering_style.model_dump(
                    mode="json"
                )
            if hasattr(fp, "recipe_preferences") and fp.recipe_preferences:
                result["style_constraints"]["recipe_preferences"] = dict(fp.recipe_preferences)
            if hasattr(fp, "color_tendencies") and fp.color_tendencies is not None:
                result["style_constraints"]["color_tendencies"] = fp.color_tendencies.model_dump(
                    mode="json"
                )
        if self.fe_bundle.vocabulary_extensions is not None:
            result["vocabulary_extensions"] = self.fe_bundle.vocabulary_extensions

        # Color narrative row for this section.
        if self.fe_bundle.color_narrative:
            for cnr in self.fe_bundle.color_narrative:
                if cnr.section_label == section_id or section_id.startswith(cnr.section_label):
                    result["color_narrative_row"] = cnr.model_dump(mode="json")
                    break

        # Arc keyframe nearest to this section's position in the song.
        if self.fe_bundle.color_arc is not None and self.fe_bundle.color_arc.arc_curve:
            arc_curve = self.fe_bundle.color_arc.arc_curve
            if self.fe_bundle.color_narrative:
                total_sections = len(self.fe_bundle.color_narrative)
                matching_idx = 0
                for idx, cnr in enumerate(self.fe_bundle.color_narrative):
                    if cnr.section_label == section_id or section_id.startswith(cnr.section_label):
                        matching_idx = idx
                        break
                position_pct = (
                    matching_idx / max(total_sections - 1, 1) if total_sections > 1 else 0.0
                )
            else:
                position_pct = 0.0
            nearest = min(arc_curve, key=lambda kf: abs(kf.position_pct - position_pct))
            result["arc_keyframe"] = nearest.model_dump(mode="json")

        return result

    @staticmethod
    def _find_section_color_assignment(
        color_arc: Any,
        section_id: str,
    ) -> Any | None:
        """Find the SectionColorAssignment matching section_id.

        Matches by section_label (exact, then prefix). Falls back to None
        if no match found.

        Args:
            color_arc: SongColorArc with section_assignments tuple.
            section_id: Section identifier to match.

        Returns:
            Matching SectionColorAssignment or None.
        """
        assignments = getattr(color_arc, "section_assignments", ())
        for assignment in assignments:
            if assignment.section_label == section_id:
                return assignment
        # Prefix match fallback (e.g., "chorus_1" matches "chorus")
        for assignment in assignments:
            if section_id.startswith(assignment.section_label):
                return assignment
        return None

    def _resolve_focus_targets(self, targets: list[Any]) -> list[str]:
        """Resolve macro typed targets to concrete group IDs for section planning.

        GroupPlanner operates on concrete groups for lane-level planning.
        Macro section focus can be group/zone/split, so expand zone/split to groups.
        """
        from twinklr.core.sequencer.vocabulary import TargetType

        resolved: list[str] = []
        for target in targets:
            ttype = getattr(target, "type", None)
            tid = getattr(target, "id", None)
            if ttype is None or not tid:
                continue

            if ttype == TargetType.GROUP:
                if self.choreo_graph.get_group(str(tid)) is not None:
                    resolved.append(str(tid))
            elif ttype == TargetType.ZONE:
                for tag, ids in self.choreo_graph.groups_by_tag.items():
                    if getattr(tag, "value", str(tag)) == tid:
                        resolved.extend(ids)
                        break
            elif ttype == TargetType.SPLIT:
                for split, ids in self.choreo_graph.groups_by_split.items():
                    if getattr(split, "value", str(split)) == tid:
                        resolved.extend(ids)
                        break

        # Deduplicate, preserve order
        seen: set[str] = set()
        result: list[str] = []
        for gid in resolved:
            if gid not in seen:
                seen.add(gid)
                result.append(gid)
        return result

    def _serialize_focus_targets(self, targets: list[Any]) -> list[dict[str, str]]:
        """Serialize typed macro focus targets for prompt/debug context."""
        serialized: list[dict[str, str]] = []
        for target in targets:
            if isinstance(target, dict):
                ttype = target.get("type")
                tid = target.get("id")
            else:
                ttype = getattr(target, "type", None)
                tid = getattr(target, "id", None)
                if ttype is not None and hasattr(ttype, "value"):
                    ttype = ttype.value
            if ttype and tid:
                serialized.append({"type": str(ttype), "id": str(tid)})
        return serialized

    def _build_timing_context(
        self,
        audio_bundle: SongBundle,
        *,
        section_id: str,
        section_start_ms: int,
        section_end_ms: int,
    ) -> TimingContext:
        """Build timing context from audio bundle with section bounds.

        Args:
            audio_bundle: SongBundle from audio analysis
            section_id: Current section identifier
            section_start_ms: Section start time in milliseconds
            section_end_ms: Section end time in milliseconds

        Returns:
            TimingContext with bar map and section bounds
        """
        from twinklr.core.agents.sequencer.group_planner.timing import (
            BarInfo,
            SectionBounds,
            TimingContext,
        )
        from twinklr.core.sequencer.templates.group.models import TimeRef, TimeRefKind

        timing_info = audio_bundle.timing
        tempo_bpm = audio_bundle.features.get("tempo_bpm", 120.0)
        beat_duration_ms = 60000.0 / tempo_bpm
        beats_per_bar_raw = audio_bundle.features.get("assumptions", {}).get("beats_per_bar")
        beats_per_bar: int
        if isinstance(beats_per_bar_raw, int) and beats_per_bar_raw > 0:
            beats_per_bar = beats_per_bar_raw
        else:
            logger.warning(
                "Derived timing meter missing for section '%s'; falling back to 4/4",
                section_id,
            )
            beats_per_bar = 4
        bar_duration_ms = beat_duration_ms * beats_per_bar

        # Build SECTION-RELATIVE bar_map
        # Bar 1 = section start, not song start
        # This matches LLM expectations (bar 1 is always section start)
        bar_map: dict[int, BarInfo] = {}
        current_ms = float(section_start_ms)  # Start from section start
        bar_num = 1
        while current_ms < section_end_ms:
            bar_map[bar_num] = BarInfo(
                bar=bar_num,
                start_ms=int(current_ms),
                duration_ms=int(bar_duration_ms),
            )
            current_ms += bar_duration_ms
            bar_num += 1

        # Build section bounds using MS TimeRefs (exact millisecond values)
        section_bounds = {
            section_id: SectionBounds(
                section_id=section_id,
                start=TimeRef(kind=TimeRefKind.MS, offset_ms=section_start_ms),
                end=TimeRef(kind=TimeRefKind.MS, offset_ms=section_end_ms),
            )
        }

        return TimingContext(
            song_duration_ms=int(timing_info.duration_ms),
            beats_per_bar=beats_per_bar,
            bar_map=bar_map,
            section_bounds=section_bounds,
        )

    def _build_section_lyric_context(
        self,
        lyric_context_model: LyricContextModel | None,
        *,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> dict[str, Any] | None:
        """Build section-scoped lyric context for narrative asset directives.

        Extracts story beats, key phrases, characters, and themes relevant
        to the current section from the full LyricContextModel.

        Uses a two-pass matching strategy:
        1. Primary: match by section_id (fast, exact)
        2. Fallback: match by timestamp overlap (resilient to ID mismatches)

        Args:
            lyric_context_model: LyricContextModel from lyrics analysis (or None)
            section_id: Current section identifier
            start_ms: Section start time in milliseconds
            end_ms: Section end time in milliseconds

        Returns:
            Section-scoped lyric context dict, or None if no lyrics available
        """
        if lyric_context_model is None:
            return None

        if not getattr(lyric_context_model, "has_lyrics", False):
            return None

        # Filter story beats to this section (by ID, then timestamp fallback)
        section_beats = []
        if lyric_context_model.story_beats:
            for beat in lyric_context_model.story_beats:
                if self._beat_matches_section(beat, section_id, start_ms, end_ms):
                    section_beats.append(
                        {
                            "beat_type": beat.beat_type,
                            "description": beat.description,
                            "visual_opportunity": beat.visual_opportunity,
                        }
                    )

        # Filter key phrases to this section (by ID, then timestamp fallback)
        section_phrases = []
        if lyric_context_model.key_phrases:
            for phrase in lyric_context_model.key_phrases:
                if self._phrase_matches_section(phrase, section_id, start_ms, end_ms):
                    section_phrases.append(
                        {
                            "text": phrase.text,
                            "visual_hint": phrase.visual_hint,
                            "emphasis": phrase.emphasis,
                        }
                    )

        # Skip if no section-specific content
        if not section_beats and not section_phrases:
            return None

        return {
            "has_narrative": lyric_context_model.has_narrative,
            "characters": lyric_context_model.characters or [],
            "themes": lyric_context_model.themes or [],
            "mood_arc": lyric_context_model.mood_arc or "",
            "story_beats": section_beats,
            "key_phrases": section_phrases,
        }

    @staticmethod
    def _beat_matches_section(
        beat: StoryBeat,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> bool:
        """Check if a story beat belongs to a section.

        Primary match: exact section_id match.
        Fallback: timestamp_range overlaps the section time window.

        Args:
            beat: StoryBeat with section_id and timestamp_range
            section_id: Target section identifier
            start_ms: Section start in milliseconds
            end_ms: Section end in milliseconds

        Returns:
            True if the beat matches this section
        """
        if beat.section_id == section_id:
            return True

        # Timestamp fallback — beat's timestamp_range overlaps section
        beat_start, beat_end = beat.timestamp_range
        return bool(beat_start < end_ms and beat_end > start_ms)

    @staticmethod
    def _phrase_matches_section(
        phrase: KeyPhrase,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> bool:
        """Check if a key phrase belongs to a section.

        Primary match: exact section_id match.
        Fallback: timestamp_ms falls within the section time window.

        Args:
            phrase: KeyPhrase with section_id and timestamp_ms
            section_id: Target section identifier
            start_ms: Section start in milliseconds
            end_ms: Section end in milliseconds

        Returns:
            True if the phrase matches this section
        """
        if phrase.section_id == section_id:
            return True

        # Timestamp fallback — phrase timestamp is within section bounds
        return bool(start_ms <= phrase.timestamp_ms < end_ms)


class GroupPlanAggregatorStage:
    """Pipeline stage that aggregates section plans into GroupPlanSet.

    Takes list of SectionCoordinationPlan (from FAN_OUT) and produces
    a single GroupPlanSet for holistic evaluation.

    Input: list[SectionCoordinationPlan] (from FAN_OUT results)
    Output: GroupPlanSet

    Example:
        StageDefinition(
            id="aggregate",
            stage=GroupPlanAggregatorStage(),
            inputs=["groups"],  # Output from FAN_OUT stage
        )
    """

    def __init__(self, plan_set_id: str = "default") -> None:
        """Initialize aggregator stage.

        Args:
            plan_set_id: ID for the resulting GroupPlanSet
        """
        self.plan_set_id = plan_set_id

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "group_plan_aggregator"

    async def execute(
        self,
        input: list[SectionCoordinationPlan],
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Aggregate section plans into GroupPlanSet.

        Args:
            input: List of SectionCoordinationPlan from FAN_OUT
            context: Pipeline context

        Returns:
            StageResult containing GroupPlanSet
        """
        try:
            if not input:
                return failure_result("No section plans to aggregate", stage_name=self.name)

            logger.debug(f"Aggregating {len(input)} section plans")

            # Aggregate + deduplicate narrative directives across sections
            aggregated_narratives = self._aggregate_narrative_directives(input)

            # Create GroupPlanSet from section plans
            group_plan_set = GroupPlanSet(
                plan_set_id=self.plan_set_id,
                section_plans=input,
                narrative_assets=aggregated_narratives,
            )

            logger.debug(
                f"GroupPlanSet created: {len(group_plan_set.section_plans)} sections, "
                f"{len(aggregated_narratives)} narrative directives"
            )

            # Track metrics
            context.add_metric("group_plan_sections", len(group_plan_set.section_plans))
            context.add_metric("narrative_directives", len(aggregated_narratives))

            return success_result(group_plan_set, stage_name=self.name)

        except Exception as e:
            logger.exception("Aggregation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    @staticmethod
    def _aggregate_narrative_directives(
        section_plans: list[SectionCoordinationPlan],
    ) -> list[NarrativeAssetDirective]:
        """Collect and deduplicate narrative directives across sections.

        Deduplicates by directive_id. When duplicates exist, the first occurrence
        is kept and section_ids are merged.

        Args:
            section_plans: List of SectionCoordinationPlan objects

        Returns:
            List of NarrativeAssetDirective with section_ids populated
        """

        # Collect directives by ID, tracking which sections reference each
        directives_by_id: dict[str, NarrativeAssetDirective] = {}
        section_map: dict[str, list[str]] = {}

        for plan in section_plans:
            # Handle both Pydantic model and dict (cache deserialization)
            if isinstance(plan, dict):
                section_id = plan.get("section_id", "unknown")
                raw_assets = plan.get("narrative_assets", [])
            else:
                section_id = getattr(plan, "section_id", "unknown")
                raw_assets = getattr(plan, "narrative_assets", [])

            for raw_directive in raw_assets:
                # Normalize to NarrativeAssetDirective if dict
                if isinstance(raw_directive, dict):
                    directive = NarrativeAssetDirective.model_validate(raw_directive)
                else:
                    directive = raw_directive

                did = directive.directive_id
                if did not in directives_by_id:
                    directives_by_id[did] = directive
                    section_map[did] = []
                section_map[did].append(section_id)

        # Build aggregated directives with section_ids populated
        aggregated = [
            d.model_copy(update={"section_ids": section_map[d.directive_id]})
            for d in directives_by_id.values()
        ]

        if aggregated:
            logger.debug(
                f"Aggregated {len(aggregated)} unique narrative directives "
                f"from {len(section_plans)} sections"
            )

        return aggregated
