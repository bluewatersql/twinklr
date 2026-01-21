"""Rendering pipeline data models.

Core data models for the rendering pipeline from AgentImplementation to XSQ.
All models use Pydantic for validation and type safety.

Models:
    BoundaryInfo: Metadata about effect boundaries for blending and transitions
    ChannelSpecs: Type-safe channel specifications (pre-rendering)
    SequencedEffect: Effect with curve specifications (not yet rendered)
    RenderedChannels: Type-safe rendered channels (post-rendering)
    RenderedEffect: Fully rendered effect with curve points
    ChannelOverlay: Section-level appearance channel settings
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec


class BoundaryInfo(BaseModel):
    """Metadata about effect boundaries for blending and transitions.

    Used by SegmentRenderer to track section boundaries and enable proper
    SOFT_HOME transitions at section starts/ends.

    Attributes:
        is_section_start: True if this is the first segment of a section
        is_section_end: True if this is the last segment of a section
        section_id: Identifier of the section this effect belongs to
        entry_transition: Transition configuration for effect entry (Phase 3+)
        exit_transition: Transition configuration for effect exit (Phase 3+)
        is_gap_fill: True if this effect is a gap fill (not from template)
        gap_type: Type of gap ("intra_section", "inter_section", "soft_home")
    """

    is_section_start: bool = False
    is_section_end: bool = False
    section_id: str | None = None

    entry_transition: Any | None = None  # TransitionConfig - will be defined in Phase 3
    exit_transition: Any | None = None  # TransitionConfig - will be defined in Phase 3

    is_gap_fill: bool = False
    gap_type: str | None = None


class ChannelSpecs(BaseModel):
    """Type-safe channel specifications for a single effect.

    All movement channels (pan, tilt, dimmer) must be present.
    Appearance channels (shutter, color, gobo) are optional (from overlays).

    Each channel can be either:
    - ValueCurveSpec (NativeCurveSpec or CustomCurveSpec) for dynamic curves
    - int for static values
    - tuple[int, int, int] for RGB color (color channel only)

    Benefits of typed model vs dict:
    - Type safety and compile-time checking
    - IDE autocomplete (specs.pan vs specs["pan"])
    - Pydantic validation
    - Self-documenting
    - No typo errors

    Attributes:
        pan: Pan channel specification or static value
        tilt: Tilt channel specification or static value
        dimmer: Dimmer channel specification or static value
        shutter: Optional shutter specification or static value
        color: Optional color (DMX value or RGB tuple)
        gobo: Optional gobo specification or static value
    """

    # Movement channels (required)
    pan: ValueCurveSpec | CustomCurveSpec | int
    tilt: ValueCurveSpec | CustomCurveSpec | int
    dimmer: ValueCurveSpec | CustomCurveSpec | int

    # Appearance channels (optional - from overlays)
    shutter: ValueCurveSpec | CustomCurveSpec | int | None = None
    color: int | tuple[int, int, int] | None = None
    gobo: ValueCurveSpec | CustomCurveSpec | int | None = None


class SequencedEffect(BaseModel):
    """Effect with curve specifications (not yet rendered).

    This is the core effect representation throughout the rendering pipeline
    until CurvePipeline renders the curves.

    Key: ALWAYS per-fixture (groups already expanded by SegmentRenderer).

    The effect contains ChannelSpecs which define what curves to generate,
    but the curves are not yet rendered to point arrays. That happens later
    in CurvePipeline.

    Attributes:
        fixture_id: Single fixture identifier (e.g., "MH1", "MH2")
        start_ms: Effect start time in milliseconds
        end_ms: Effect end time in milliseconds
        channels: Type-safe channel specifications
        boundary_info: Optional boundary metadata for blending logic
        label: Optional human-readable label
        metadata: General metadata for debugging/tracking
    """

    fixture_id: str
    start_ms: int
    end_ms: int
    channels: ChannelSpecs

    boundary_info: BoundaryInfo | None = None
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderedChannels(BaseModel):
    """Type-safe rendered channels (Native specs, rendered points, OR static values).

    Channels can contain either:
    - ValueCurveSpec: Native curves (xLights renders them parametrically)
    - list[CurvePoint]: Custom curves (we rendered them to points)
    - int: Static values (xLights renders as slider values)

    This preserves Native curve efficiency while supporting Custom curves and
    avoids unnecessary curve generation for static values.

    Attributes:
        pan: Pan channel (Native spec, rendered points, or static value)
        tilt: Tilt channel (Native spec, rendered points, or static value)
        dimmer: Dimmer channel (Native spec, rendered points, or static value)
        shutter: Optional shutter channel (Native spec, rendered points, or static value)
        color: Optional color channel (Native spec, rendered points, or static value)
        gobo: Optional gobo channel (Native spec, rendered points, or static value)
    """

    # Movement channels (required)
    pan: ValueCurveSpec | list[CurvePoint] | int
    tilt: ValueCurveSpec | list[CurvePoint] | int
    dimmer: ValueCurveSpec | list[CurvePoint] | int

    # Appearance channels (optional)
    shutter: ValueCurveSpec | list[CurvePoint] | int | None = None
    color: ValueCurveSpec | list[CurvePoint] | int | None = None
    gobo: ValueCurveSpec | list[CurvePoint] | int | None = None


class RenderedEffect(BaseModel):
    """Effect with Native specs or rendered curves (ready for format conversion).

    Output of CurvePipeline. Native curves (ValueCurveSpec) are passed through
    unchanged for xLights to render parametrically. Custom curves and static
    values are rendered to point arrays. Blending is applied where appropriate
    (only to Custom curves, not Native curves).

    This is the final internal representation before conversion to xLights format.

    Attributes:
        fixture_id: Single fixture identifier
        start_ms: Effect start time in milliseconds
        end_ms: Effect end time in milliseconds
        rendered_channels: Type-safe rendered channels (Native or Custom)
        label: Optional human-readable label
        metadata: Preserved metadata from SequencedEffect
    """

    fixture_id: str
    start_ms: int
    end_ms: int
    rendered_channels: RenderedChannels

    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelOverlay(BaseModel):
    """Channel overlay for a section (appearance channels only).

    Resolved once per section by resolve_channel_overlays() and applied
    to all effects in that section.

    Appearance channels only - movement channels (pan/tilt) come from templates.

    Phase 5B: Currently holds string IDs that will be resolved later.
    Phase 6: Will be updated to hold resolved values (int, RGB, ValueCurveSpec).

    Each channel can be:
    - String ID (Phase 5B - e.g., "open", "white", "stars")
    - Static value (int) (Phase 6+)
    - RGB tuple (color only) (Phase 6+)
    - ValueCurveSpec for dynamic patterns (Phase 6+)

    Attributes:
        shutter: Shutter setting (string ID or resolved value)
        color: Color setting (string ID, DMX value, or RGB tuple)
        gobo: Gobo setting (string ID or resolved value)
    """

    shutter: str | ValueCurveSpec | int
    color: str | int | tuple[int, int, int]
    gobo: str | int
