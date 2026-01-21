"""Pattern step processor - thin orchestration layer.

Follows MovingHeadSequencer pattern:
- All dependencies injected
- Delegates to GeometryEngine, ResolverRegistry, handlers
- No inline component creation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.channels.pipeline import (
    ChannelIntegrationPipeline,
    XsqAdapter,
)
from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import TimeResolver
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
    DIMMER_LIBRARY,
    GEOMETRY_LIBRARY,
    MOVEMENT_LIBRARY,
    CategoricalIntensity,
    DimmerID,
    GeometryID,
    MovementID,
)
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.models.templates import PatternStep, Template
from blinkb0t.core.domains.sequencing.models.transitions import Timeline, TimelineEffect
from blinkb0t.core.domains.sequencing.models.xsq import XSequence
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.template_handler_registry import (
    ResolverRegistry,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.context_builder import (
    ResolverContextBuilder,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.base import SequencerContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.planner import TemplateTimePlanner
from blinkb0t.core.domains.sequencing.moving_heads.transitions.gap_detector import GapDetector
from blinkb0t.core.domains.sequencing.moving_heads.transitions.processor import TransitionProcessor
from blinkb0t.core.domains.sequencing.moving_heads.transitions.renderer import TransitionRenderer
from blinkb0t.core.domains.sequencing.moving_heads.transitions.resolver import TransitionResolver
from blinkb0t.core.domains.sequencing.poses import PoseResolver

logger = logging.getLogger(__name__)


@dataclass
class StepContext:
    """Encapsulates all resolved data for a template step.

    This dataclass provides a clear, type-safe container for all the data
    resolved during step processing, improving code clarity and debuggability.
    """

    # Template data
    step: PatternStep

    # Resolved timing
    start_ms: int
    end_ms: int

    # Resolved pose
    pan_deg: float
    tilt_deg: float

    # Resolved categorical parameters (numeric)
    movement_numeric_params: dict[str, Any]
    geometry_numeric_params: dict[str, Any]
    dimmer_numeric_params: dict[str, Any]

    # Fixture context
    fixture: FixtureInstance


class PatternStepProcessor:
    """Processes templates into effect placements.

    Thin orchestration layer that:
    1. Resolves timing (via TimeResolver)
    2. Resolves poses (via PoseResolver)
    3. Applies geometry (via GeometryEngine)
    4. Routes to handlers (via ResolverRegistry)
    5. Builds contexts (via ResolverContextBuilder)

    All dependencies injected (no inline creation).
    """

    def __init__(
        self,
        time_resolver: TimeResolver,
        pose_resolver: PoseResolver,
        geometry_engine: GeometryEngine,
        resolver_registry: ResolverRegistry,
        sequencer_context: SequencerContext,
        xsq: XSequence,
        song_features: dict[str, Any],
        fixtures: FixtureGroup,
        job_config: JobConfig,
        channel_pipeline: ChannelIntegrationPipeline,
    ):
        """Initialize processor with injected dependencies.

        Args:
            time_resolver: Timing resolution (musical → absolute)
            pose_resolver: Pose resolution (pose ID → angles)
            geometry_engine: Geometry transformation engine
            resolver_registry: Handler registry for routing
            sequencer_context: Shared sequencer context
            xsq: XSequence object
            song_features: Song features
            fixtures: Fixture group
            job_config: Job configuration
            channel_pipeline: Channel integration pipeline
        """
        self.time_resolver = time_resolver
        self.pose_resolver = pose_resolver
        self.geometry_engine = geometry_engine
        self.resolver_registry = resolver_registry
        self.sequencer_context = sequencer_context
        self.xsq = xsq
        self.song_features = song_features
        self.fixtures = fixtures
        self.job_config = job_config
        self.channel_pipeline = channel_pipeline
        self.xsq_adapter = XsqAdapter()

        # Create context builder with injected JobConfig
        self.context_builder = ResolverContextBuilder(
            sequencer_context=sequencer_context,
            xsq=xsq,
            job_config=job_config,
        )

        # Create transition renderer for entry/exit transitions
        self.transition_renderer = TransitionRenderer(
            time_resolver=time_resolver,
            dmx_curve_mapper=sequencer_context.dmx_curve_mapper,
        )

        # Create unified transitions and gap filling components
        self.time_planner = TemplateTimePlanner(song_features=song_features)
        self.gap_detector = GapDetector()
        self.transition_resolver = TransitionResolver()
        self.transition_processor = TransitionProcessor(
            gap_detector=self.gap_detector,
            resolver=self.transition_resolver,
            transition_renderer=self.transition_renderer,
        )

        logger.debug("PatternStepProcessor initialized with proper DI")

    def process_template(
        self,
        template: Template,
        fixture: FixtureInstance,
        base_pose: PoseID,
        section_start_ms: float,
        section_end_ms: float,
    ) -> list[EffectPlacement]:
        """Process template for fixture with unified transitions and gap filling.

        New unified approach (Phase 1 + Phase 2):
        1. Use TemplateTimePlanner to create temporal layout (Timeline)
        2. Render actual DMX effects for each TimelineEffect
        3. Use TransitionProcessor to fill all gaps
        4. Return complete sorted list

        Args:
            template: Template to process
            fixture: Target fixture
            base_pose: Base pose for movement
            section_start_ms: Section start time
            section_end_ms: Section end time

        Returns:
            Complete list of effect placements (main effects + transition effects)
        """
        # Get song duration for gap detection
        song_duration_ms = self.song_features.get("duration_s", 0) * 1000
        section_duration_ms = section_end_ms - section_start_ms

        # Phase 1: Spatial Planning - Create temporal layout with gaps
        logger.debug(
            f"Phase 1: Planning template '{template.template_id}' "
            f"for section {section_start_ms}-{section_end_ms}ms"
        )
        planned_timeline = self.time_planner.plan_template(
            template=template,
            section_start_ms=section_start_ms,
            section_duration_ms=section_duration_ms,
            fixture_id=fixture.fixture_id,
        )

        # Render actual DMX effects for planned timeline effects
        logger.debug(
            f"Rendering {len([item for item in planned_timeline if isinstance(item, TimelineEffect)])} "
            f"main effects"
        )
        rendered_timeline: Timeline = []

        for item in planned_timeline:
            if isinstance(item, TimelineEffect):
                # Render the actual DMX effect for this TimelineEffect
                # Use the timing and parameters from the planned effect

                # Ensure pattern_step is available (should always be present for planned effects)
                if item.pattern_step is None:
                    logger.warning(
                        f"Skipping TimelineEffect without pattern_step at "
                        f"{item.start_ms}-{item.end_ms}ms"
                    )
                    continue

                step_effects = self._process_step(
                    step=item.pattern_step,
                    fixture=fixture,
                    base_pose=base_pose,
                    section_start_ms=item.start_ms,
                    section_end_ms=item.end_ms,
                )

                # Update TimelineEffect with actual rendered effects
                # (For now, we'll use the first effect if multiple are generated)
                if step_effects:
                    # Create new TimelineEffect with the actual rendered effect
                    rendered_effect = TimelineEffect(
                        start_ms=step_effects[0].start_ms,
                        end_ms=step_effects[-1].end_ms,
                        fixture_id=fixture.fixture_id,
                        effect=step_effects[0],  # Main effect
                        pan_start=item.pan_start,
                        pan_end=item.pan_end,
                        tilt_start=item.tilt_start,
                        tilt_end=item.tilt_end,
                        step_index=item.step_index,
                        template_id=item.template_id,
                        template_metadata=item.template_metadata,
                        pattern_step=item.pattern_step,
                    )
                    rendered_timeline.append(rendered_effect)
            else:
                # Keep gaps as-is
                rendered_timeline.append(item)

        # Phase 2: Temporal Rendering - Fill all gaps with transitions
        logger.debug("Phase 2: Processing transitions and gap fills")

        # Create a single-fixture FixtureGroup for TransitionProcessor
        fixture_group = FixtureGroup(
            group_id=f"single_{fixture.fixture_id}",
            fixtures=[fixture],
        )

        complete_effects = self.transition_processor.process(
            timeline=rendered_timeline,
            song_duration_ms=song_duration_ms,
            fixtures=fixture_group,
        )

        logger.info(
            f"Template '{template.template_id}' complete: "
            f"{len(complete_effects)} total effects "
            f"(main + transitions)"
        )

        return complete_effects

    def _apply_parameters(
        self,
        library_id: str,
        template_params: dict[str, Any],
        library_type: str,
    ) -> dict[str, Any]:
        """Map categorical parameters to numeric library parameters.

        This method resolves categorical parameters (e.g., "intensity": "SMOOTH")
        to numeric library-specific parameters (e.g., {"amplitude": 0.3, "frequency": 0.5}).

        Args:
            library_id: Pattern ID (e.g., "sweep_lr", "fan", "pulse")
            template_params: Parameters from template step (may contain categorical values)
            library_type: Type of library ("movement", "geometry", or "dimmer")

        Returns:
            Resolved numeric parameters ready for handlers

        Raises:
            ValueError: If library_id not found in library
        """
        # Look up pattern definition from Phase 0 library
        categorical_params_map: Any
        base_params: Any

        try:
            if library_type == "movement":
                movement_pattern = MOVEMENT_LIBRARY[MovementID(library_id)]
                categorical_params_map = movement_pattern.categorical_params
                base_params = movement_pattern.base_params
            elif library_type == "geometry":
                # Geometry library has simplified definitions without categorical params
                # Just validate the ID exists
                _ = GEOMETRY_LIBRARY[GeometryID(library_id)]
                # Geometry doesn't have categorical params - just pass through
                return dict(template_params)
            elif library_type == "dimmer":
                dimmer_pattern = DIMMER_LIBRARY[DimmerID(library_id)]
                categorical_params_map = dimmer_pattern.categorical_params
                base_params = dimmer_pattern.base_params
            else:
                raise ValueError(f"Unknown library type: {library_type}")
        except (KeyError, ValueError) as e:
            logger.error(f"Pattern '{library_id}' not found in {library_type} library: {e}")
            raise ValueError(f"Pattern '{library_id}' not found in {library_type} library") from e

        # Apply template parameters
        resolved_params = {}
        for param_name, param_value in template_params.items():
            # Check if this is a categorical parameter
            if param_name == "intensity" and isinstance(param_value, str):
                # Map categorical intensity to numeric params
                try:
                    intensity_enum = CategoricalIntensity(param_value)
                    if intensity_enum in categorical_params_map:
                        # Get categorical params (Pydantic model)
                        cat_params = categorical_params_map[intensity_enum]
                        # Convert to dict
                        resolved_params.update(cat_params.model_dump())
                    else:
                        logger.warning(
                            f"Intensity '{param_value}' not found in categorical_params "
                            f"for '{library_id}', using base params"
                        )
                except (ValueError, KeyError) as e:
                    logger.warning(
                        f"Unknown categorical intensity '{param_value}' "
                        f"for '{library_id}': {e}, using base params"
                    )
            else:
                # Direct parameter (pass through)
                resolved_params[param_name] = param_value

        # Merge base params with resolved params (resolved overrides base)
        final_params = {**base_params, **resolved_params}

        logger.debug(
            f"Applied parameters for {library_type} '{library_id}': "
            f"{template_params} → {final_params}"
        )

        return final_params

    def _build_step_context(
        self,
        step: PatternStep,
        fixture: FixtureInstance,
        base_pose: PoseID,
        section_start_ms: float,
        section_end_ms: float,
    ) -> StepContext:
        """Build complete step context by resolving all dependencies.

        This method encapsulates all resolution logic in one place, creating
        a clear, type-safe context object for step processing.

        Returns:
            StepContext with all resolved data
        """
        # 1. Resolve timing (musical → absolute)
        start_ms_float, end_ms_float = self.time_resolver.resolve_timing(step.timing.base_timing)
        start_ms = int(start_ms_float + section_start_ms)
        end_ms = int(end_ms_float + section_start_ms)

        # 2. Resolve pose (pose ID → angles)
        pan_deg, tilt_deg = self.pose_resolver.resolve_pose(base_pose)

        # 3. Apply categorical parameters to get numeric params
        movement_numeric_params = self._apply_parameters(
            library_id=step.movement_id,
            template_params=step.movement_params,
            library_type="movement",
        )

        geometry_numeric_params = {}
        if step.geometry_id:
            geometry_numeric_params = self._apply_parameters(
                library_id=step.geometry_id,
                template_params=step.geometry_params,
                library_type="geometry",
            )

        dimmer_numeric_params = self._apply_parameters(
            library_id=step.dimmer_id,
            template_params=step.dimmer_params,
            library_type="dimmer",
        )

        return StepContext(
            step=step,
            start_ms=start_ms,
            end_ms=end_ms,
            pan_deg=pan_deg,
            tilt_deg=tilt_deg,
            movement_numeric_params=movement_numeric_params,
            geometry_numeric_params=geometry_numeric_params,
            dimmer_numeric_params=dimmer_numeric_params,
            fixture=fixture,
        )

    def _process_step(
        self,
        step: PatternStep,
        fixture: FixtureInstance,
        base_pose: PoseID,
        section_start_ms: float,
        section_end_ms: float,
    ) -> list[EffectPlacement]:
        """Process single pattern step.

        Delegates to injected dependencies:
        - TimeResolver for timing
        - PoseResolver for poses
        - GeometryEngine for geometry transforms
        - ResolverRegistry for handler routing
        - ChannelIntegrationPipeline for SequencedEffect → DmxEffect
        - XsqAdapter for DmxEffect → EffectPlacement

        Uses StepContext to encapsulate all resolved data.
        """
        # Build step context (resolve all data in one place)
        context = self._build_step_context(
            step=step,
            fixture=fixture,
            base_pose=base_pose,
            section_start_ms=section_start_ms,
            section_end_ms=section_end_ms,
        )

        # Build base movement spec with RESOLVED numeric parameters
        movement_spec = {
            "pattern": step.movement_id,
            "pan_center_deg": context.pan_deg,
            "tilt_center_deg": context.tilt_deg,
            **context.movement_numeric_params,  # Now contains numeric values!
        }

        # Add curve_preset from movement library's primary_curve
        try:
            movement_pattern = MOVEMENT_LIBRARY[MovementID(step.movement_id)]
            primary_curve = movement_pattern.primary_curve
            # Convert curve type to lowercase (e.g., "FLAT" -> "flat")
            curve_preset = primary_curve.curve.value.lower()
            movement_spec["curve_preset"] = curve_preset
            logger.debug(
                f"Enriched movement '{step.movement_id}' with curve_preset='{curve_preset}'"
            )
        except (KeyError, ValueError) as e:
            logger.warning(
                f"Could not load curve_preset for movement '{step.movement_id}': {e}. "
                f"Will use handler default."
            )

        # Apply geometry (if present)
        if step.geometry_id:
            per_fixture_movements = self.geometry_engine.apply_geometry(
                geometry_type=step.geometry_id,
                targets=[fixture.fixture_id],
                base_movement=movement_spec,
                params=context.geometry_numeric_params,
            )
            movement_spec = per_fixture_movements[fixture.fixture_id]

        # Build dimmer spec with RESOLVED numeric parameters
        dimmer_spec = {
            "pattern": step.dimmer_id,
            **context.dimmer_numeric_params,  # Now contains numeric values!
        }

        # Build instruction
        instruction = {
            "movement": movement_spec,
            "dimmer": dimmer_spec,
            "time_ms": {"start": context.start_ms, "end": context.end_ms},
        }

        # Build section
        section = {
            "time_ms": {"start": context.start_ms, "end": context.end_ms},
            "template_id": step.step_id,
        }

        # Build resolver context
        resolver_context = self.context_builder.build_context(
            fixture=fixture,
            instruction=instruction,
            section=section,
            fixtures=FixtureGroup(group_id="template", fixtures=[fixture]),
        )

        # Route to handler
        resolver = self.resolver_registry.get_resolver(step.movement_id)

        # Invoke handler (returns list[SequencedEffect])
        sequenced_effects = resolver.resolve(
            instruction=instruction,
            context=resolver_context,
            targets=[fixture.fixture_id],
        )

        # Process through channel integration pipeline
        # (SequencedEffect → DmxEffect with fixture resolution, boundaries, gaps)
        fixture_group = FixtureGroup(group_id="template", fixtures=[fixture])
        dmx_effects = self.channel_pipeline.process_section(
            movement_effects=sequenced_effects,
            channel_effects=[],  # No channel effects in template processing
            fixtures=fixture_group,
            section_start_ms=int(section_start_ms),
            section_end_ms=int(section_end_ms),
        )

        # Convert to EffectPlacement (DmxEffect → EffectPlacement)
        effect_placements = self.xsq_adapter.convert(dmx_effects, fixture_group)

        return effect_placements
