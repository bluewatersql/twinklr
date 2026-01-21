"""Curve rendering pipeline with Native/Custom hybrid support.

The CurvePipeline is responsible for rendering ValueCurveSpec objects into
actual curve points (list[CurvePoint]). It handles both Native curves (xLights
built-in types) and Custom curves (user-defined point arrays).

Key responsibilities:
- Render curve specifications → actual points
- Detect Native vs Custom curves per fixture
- Apply blending (if all Custom)
- Handle SNAP transitions (if any Native)
- Return RenderedEffect objects

Architecture:
    SequencedEffect (with ValueCurveSpec)
        ↓
    CurvePipeline.render()
        ↓
    RenderedEffect (with list[CurvePoint])

Phase 4 Implementation Strategy:
- Per-fixture processing (no cross-fixture concerns)
- Detects Native vs Custom per fixture
- Different logic paths based on curve types
- Blending only when all curves are Custom
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CurveGenerator
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
    CustomCurveSpec,
)
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.domains.sequencing.rendering.curve_blending import CurveBlender
from blinkb0t.core.domains.sequencing.rendering.curve_detector import CurveTypeDetector
from blinkb0t.core.utils.logging import get_logger

from .models import RenderedEffect, SequencedEffect

logger = get_logger(__name__)


class CurvePipeline:
    """Standalone curve generation and blending pipeline.

    The CurvePipeline converts SequencedEffect objects (which contain curve
    specifications) into RenderedEffect objects (which contain actual curve points).

    It handles two types of curves:
    - Native curves: xLights built-in curve types (requires generation)
    - Custom curves: User-defined point arrays (already have points)

    Key Design Decisions:
    - Per-fixture processing: Each fixture's curves are rendered independently
    - Hybrid Native/Custom support: Can mix both types in same show
    - Conditional blending: Only blend when ALL curves are Custom
    - SNAP transitions: Used when ANY Native curves present

    Attributes:
        curve_generator: Generator for rendering Native curves to points
    """

    def __init__(self, curve_generator: CurveGenerator):
        """Initialize CurvePipeline with required dependencies.

        Args:
            curve_generator: Generator for curve rendering (Native curves)

        Example:
            >>> from blinkb0t.core.domains.sequencing.infrastructure.curves import CurveGenerator
            >>> generator = CurveGenerator()
            >>> pipeline = CurvePipeline(curve_generator=generator)
        """
        self.curve_generator = curve_generator
        self.blender = CurveBlender()
        self.detector = CurveTypeDetector()
        logger.debug("CurvePipeline initialized with blender and detector")

    def render(
        self,
        effects: list[SequencedEffect],
    ) -> list[RenderedEffect]:
        """Render SequencedEffects to RenderedEffects.

        Main entry point for the curve pipeline. Takes effects with curve
        specifications and returns effects with rendered curve points.

        Pipeline stages:
        1. Group effects by fixture_id
        2. For each fixture:
            a. Detect if Native curves present
            b. If Native → use SNAP-only rendering
            c. If all Custom → use blending rendering
        3. Collect and return all rendered effects

        Args:
            effects: SequencedEffect objects with ValueCurveSpec

        Returns:
            RenderedEffect objects with actual CurvePoint arrays

        Example:
            >>> sequenced_effects = [
            ...     SequencedEffect(fixture_id="MH1", start_ms=0, end_ms=1000, ...),
            ...     SequencedEffect(fixture_id="MH2", start_ms=0, end_ms=1000, ...),
            ... ]
            >>> rendered = pipeline.render(sequenced_effects)
            >>> assert all(isinstance(e, RenderedEffect) for e in rendered)
        """
        logger.info(f"CurvePipeline: Rendering {len(effects)} effects")

        # Group by fixture
        by_fixture = self._group_by_fixture(effects)
        logger.info(f"  Grouped into {len(by_fixture)} fixtures")

        # Render per fixture
        rendered_effects = []
        for fixture_id, fixture_effects in by_fixture.items():
            rendered = self._render_fixture(fixture_id, fixture_effects)
            rendered_effects.extend(rendered)

        logger.info(f"  Rendered {len(rendered_effects)} effects")
        return rendered_effects

    def _group_by_fixture(
        self,
        effects: list[SequencedEffect],
    ) -> dict[str, list[SequencedEffect]]:
        """Group effects by fixture ID.

        Takes a flat list of effects and groups them by fixture_id, returning
        a dictionary where keys are fixture IDs and values are lists of effects
        for that fixture.

        Order is preserved: effects appear in the same order they were in the
        input list for each fixture.

        Args:
            effects: List of SequencedEffect objects (possibly mixed fixtures)

        Returns:
            Dictionary mapping fixture_id → list of effects for that fixture

        Example:
            >>> effects = [
            ...     SequencedEffect(fixture_id="MH1", ...),
            ...     SequencedEffect(fixture_id="MH2", ...),
            ...     SequencedEffect(fixture_id="MH1", ...),
            ... ]
            >>> grouped = pipeline._group_by_fixture(effects)
            >>> assert len(grouped["MH1"]) == 2
            >>> assert len(grouped["MH2"]) == 1
        """
        by_fixture: dict[str, list[SequencedEffect]] = {}

        for effect in effects:
            if effect.fixture_id not in by_fixture:
                by_fixture[effect.fixture_id] = []
            by_fixture[effect.fixture_id].append(effect)

        return by_fixture

    def _render_snap_only(
        self,
        effects: list[SequencedEffect],
    ) -> list[RenderedEffect]:
        """Render effects with SNAP transitions (no blending).

        Used when Native curves are present. Renders all channels for each
        effect independently without applying blending at boundaries.

        Args:
            effects: Effects to render (for single fixture)

        Returns:
            List of RenderedEffect objects with rendered curve points

        Example:
            >>> effects = [SequencedEffect(...), SequencedEffect(...)]
            >>> rendered = pipeline._render_snap_only(effects)
            >>> assert all(isinstance(e, RenderedEffect) for e in rendered)
        """
        from .models import RenderedChannels

        rendered = []

        for effect in effects:
            # Render all required channels (pan, tilt, dimmer)
            pan_points = self._render_channel(effect.channels.pan, effect)
            tilt_points = self._render_channel(effect.channels.tilt, effect)
            dimmer_points = self._render_channel(effect.channels.dimmer, effect)

            # Render optional appearance channels
            shutter_points = None
            if effect.channels.shutter is not None:
                shutter_points = self._render_channel(effect.channels.shutter, effect)

            color_points = None
            if effect.channels.color is not None:
                # TODO: Handle RGB color tuples in Phase 4 - for now skip
                if isinstance(effect.channels.color, int):
                    color_points = self._render_channel(effect.channels.color, effect)

            gobo_points = None
            if effect.channels.gobo is not None:
                gobo_points = self._render_channel(effect.channels.gobo, effect)

            # Create RenderedChannels
            rendered_channels = RenderedChannels(
                pan=pan_points,
                tilt=tilt_points,
                dimmer=dimmer_points,
                shutter=shutter_points,
                color=color_points,
                gobo=gobo_points,
            )

            # Create RenderedEffect
            rendered_effect = RenderedEffect(
                fixture_id=effect.fixture_id,
                start_ms=effect.start_ms,
                end_ms=effect.end_ms,
                rendered_channels=rendered_channels,
                label=effect.label,
                metadata=effect.metadata,
            )

            rendered.append(rendered_effect)

        return rendered

    def _render_fixture(
        self,
        fixture_id: str,
        effects: list[SequencedEffect],
    ) -> list[RenderedEffect]:
        """Render all effects for a single fixture.

        Orchestrates rendering by:
        1. Sorting effects by start time
        2. Detecting Native vs Custom curves
        3. Routing to appropriate renderer (SNAP or blending)

        Args:
            fixture_id: Fixture identifier
            effects: Effects for this fixture (possibly unsorted)

        Returns:
            List of RenderedEffect objects

        Example:
            >>> effects = [SequencedEffect(...), SequencedEffect(...)]
            >>> rendered = pipeline._render_fixture("MH1", effects)
            >>> assert all(e.fixture_id == "MH1" for e in rendered)
        """
        # Sort by time
        effects = sorted(effects, key=lambda e: e.start_ms)

        # Detect if any Native curves present
        has_native = self.detector.detect_native_curves(effects)

        if has_native:
            logger.debug(f"Fixture {fixture_id}: Native curves detected → SNAP only")
            return self._render_snap_only(effects)
        else:
            logger.debug(f"Fixture {fixture_id}: All Custom curves → blending enabled")
            return self._render_with_blending(effects)

    # ========================================================================
    # Blending Logic (delegated to CurveBlender)
    # ========================================================================

    def _render_with_blending(
        self,
        effects: list[SequencedEffect],
    ) -> list[RenderedEffect]:
        """Render effects with crossfade blending at boundaries.

        Two-pass rendering:
        1. First pass: Render all curves (SNAP mode - no blending)
        2. Second pass: Apply blending at adjacent boundaries where:
           - Effects are adjacent (no gap)
           - Transition mode is CROSSFADE (not SNAP)

        Args:
            effects: Effects to render (for single fixture, sorted by time)

        Returns:
            List of RenderedEffect objects with blending applied

        Example:
            >>> effects = [effect1, effect2, effect3]
            >>> rendered = pipeline._render_with_blending(effects)
            >>> # Adjacent CROSSFADE transitions are blended
        """
        # First pass: Render all curves without blending
        rendered = self._render_snap_only(effects)

        # Second pass: Apply blending at adjacent boundaries
        for i in range(len(rendered) - 1):
            curr = rendered[i]
            next_effect = rendered[i + 1]

            # Get corresponding SequencedEffects for boundary info
            curr_seq = effects[i]
            next_seq = effects[i + 1]

            # Check if effects are adjacent (no gap)
            is_adjacent = curr.end_ms == next_effect.start_ms

            if not is_adjacent:
                logger.debug(
                    f"Gap detected between effects {i} and {i + 1} "
                    f"({curr.end_ms}ms -> {next_effect.start_ms}ms), skipping blend"
                )
                continue

            # Get transition mode
            transition_mode = self.blender.get_transition_mode(curr_seq, next_seq)

            if transition_mode == "CROSSFADE":
                # Apply crossfade blending
                blend_duration = self.blender.get_blend_duration(curr_seq, next_seq)
                logger.debug(
                    f"Applying CROSSFADE blend between effects {i} and {i + 1} "
                    f"(duration: {blend_duration}ms)"
                )
                self.blender.apply_crossfade_channels(curr, next_effect, blend_duration)
            else:
                logger.debug(f"SNAP transition between effects {i} and {i + 1}, no blending")

        return rendered

    def _render_channel(
        self,
        spec: ValueCurveSpec | CustomCurveSpec | int,
        effect: SequencedEffect,
    ) -> ValueCurveSpec | list[CurvePoint] | int:
        """Render a single channel specification.

        Converts a channel specification to either:
        - ValueCurveSpec: Native curve (pass through unchanged for xLights)
        - list[CurvePoint]: Custom curve points (we render them)
        - int: Static value (pass through for XLights slider)

        Native curves (ValueCurveSpec) are NOT rendered - they pass through
        unchanged for xLights to render parametrically. This is more efficient
        and preserves the native curve's mathematical properties.

        Custom curves (CustomCurveSpec) already have points, so we return them.
        Static integer values REMAIN as integers (not converted to curves).

        Args:
            spec: Channel specification (int, ValueCurveSpec, or CustomCurveSpec)
            effect: SequencedEffect containing this channel

        Returns:
            ValueCurveSpec (Native curve) OR list[CurvePoint] (Custom) OR int (static)

        Examples:
            >>> # Static value → pass through as int
            >>> result = pipeline._render_channel(127, effect)
            >>> assert isinstance(result, int)
            >>> assert result == 127

            >>> # Native curve → pass through unchanged
            >>> spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=200.0)
            >>> result = pipeline._render_channel(spec, effect)
            >>> assert isinstance(result, ValueCurveSpec)
            >>> assert result is spec  # Same object!

            >>> # Custom curve → return points
            >>> spec = CustomCurveSpec(points=[...])
            >>> points = pipeline._render_channel(spec, effect)
            >>> assert isinstance(points, list)
        """
        # Import here to avoid circular dependency
        from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
            CustomCurveSpec,
        )

        """Render a single channel specification.

        Converts a channel specification to either:
        - ValueCurveSpec: Native curve (pass through unchanged for xLights)
        - list[CurvePoint]: Custom curve points (we render them)
        - int: Static value (pass through for XLights slider)

        Native curves (ValueCurveSpec) are NOT rendered - they pass through
        unchanged for xLights to render parametrically. This is more efficient
        and preserves the native curve's mathematical properties.

        Custom curves (CustomCurveSpec) already have points, so we return them.
        Static integer values REMAIN as integers (not converted to curves).

        Args:
            spec: Channel specification (int, ValueCurveSpec, or CustomCurveSpec)
            effect: SequencedEffect containing this channel

        Returns:
            ValueCurveSpec (Native curve) OR list[CurvePoint] (Custom) OR int (static)

        Examples:
            >>> # Static value → pass through as int
            >>> result = pipeline._render_channel(127, effect)
            >>> assert isinstance(result, int)
            >>> assert result == 127

            >>> # Native curve → pass through unchanged
            >>> spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=200.0)
            >>> result = pipeline._render_channel(spec, effect)
            >>> assert isinstance(result, ValueCurveSpec)
            >>> assert result is spec  # Same object!

            >>> # Custom curve → return points
            >>> spec = CustomCurveSpec(points=[...])
            >>> points = pipeline._render_channel(spec, effect)
            >>> assert isinstance(points, list)
        """
        # Static value → pass through as int (for XLights slider)
        if isinstance(spec, int):
            return spec  # ✅ Keep as int for slider rendering

        # Native curve (ValueCurveSpec) → pass through unchanged!
        # xLights will render it parametrically (more efficient)
        if isinstance(spec, ValueCurveSpec):
            return spec  # ✅ Don't render Native curves!

        # Custom curve → render with smoothing
        if isinstance(spec, CustomCurveSpec):
            points = spec.points

            # Use fixed target point count for PCHIP interpolation
            # PCHIP mathematically determines optimal smoothing
            target_count = 25

            # Apply smoothing to normalize point count
            smooth_points = self._smooth_custom_curve(points, target_count)

            return smooth_points  # ✅ Smoothed points

        # Unknown type
        logger.error(f"Unknown channel spec type: {type(spec)}")
        return [
            CurvePoint(time=0.0, value=0.0),
            CurvePoint(time=1.0, value=0.0),
        ]

    def _smooth_custom_curve(
        self,
        points: list[CurvePoint],
        target_point_count: int,
    ) -> list[CurvePoint]:
        """Apply PCHIP smoothing to Custom curve points.

        Normalizes point count using scipy PCHIP interpolation for
        computational efficiency and visual smoothness. This method
        should ONLY be used for Custom curves, NOT Native curves!

        Native curves (ValueCurveSpec) pass through unchanged and are
        rendered by xLights parametrically.

        Args:
            points: Input curve points (may be sparse or dense)
            target_point_count: Fixed target (typically 300 points)

        Returns:
            Smoothed curve points with normalized count

        Examples:
            >>> # Sparse curve → smooth to 100 points
            >>> points = [CurvePoint(0.0, 0.0), CurvePoint(1.0, 255.0)]
            >>> smooth = pipeline._smooth_custom_curve(points, 100)
            >>> len(smooth)
            100

            >>> # Dense curve → reduce to 200 points
            >>> points = [CurvePoint(i/500, i) for i in range(500)]
            >>> smooth = pipeline._smooth_custom_curve(points, 200)
            >>> len(smooth)
            200
        """
        import numpy as np
        from scipy.interpolate import PchipInterpolator

        # Edge case: Empty or single-point curve
        if len(points) <= 1:
            return points

        # Edge case: Already optimal count
        if len(points) == target_point_count:
            return points

        # Extract time and value arrays
        times = np.array([p.time for p in points])
        values = np.array([p.value for p in points])

        # Create PCHIP interpolator (shape-preserving, monotonic)
        interpolator = PchipInterpolator(times, values)

        # Generate smooth output points
        output_times = np.linspace(0.0, 1.0, target_point_count)
        output_values = interpolator(output_times)

        # Convert back to CurvePoint array
        return [
            CurvePoint(time=float(t), value=float(v))
            for t, v in zip(output_times, output_values, strict=False)
        ]
