"""Pydantic models for xLights sequence files (XSQ).

These models represent the complete structure of an xLights sequence
with full validation and type safety.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeMarker(BaseModel):
    """A timing marker in a timing track."""

    name: str = Field(..., description="Marker name")
    time_ms: int = Field(..., ge=0, description="Time in milliseconds (startTime)")
    position: float = Field(..., ge=0.0, description="Normalized position (0.0-1.0)")
    end_time_ms: int | None = Field(
        default=None, description="Optional end time in milliseconds (endTime as offset from start)"
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("time_ms")
    @classmethod
    def validate_time_positive(cls, v: int) -> int:
        """Validate time is non-negative."""
        if v < 0:
            raise ValueError(f"time_ms must be non-negative, got {v}")
        return v

    @field_validator("end_time_ms")
    @classmethod
    def validate_end_time(cls, v: int | None, info: Any) -> int | None:
        """Validate end_time_ms is after start time if provided."""
        if v is not None and "time_ms" in info.data and v < info.data["time_ms"]:
            raise ValueError(f"end_time_ms ({v}) must be >= time_ms ({info.data['time_ms']})")
        return v


class TimingTrack(BaseModel):
    """A timing track containing timing markers."""

    name: str = Field(..., description="Track name")
    type: str = Field(default="timing", description="Track type")
    markers: list[TimeMarker] = Field(default_factory=list, description="Timing markers")

    model_config = ConfigDict(extra="ignore")


class Effect(BaseModel):
    """An effect applied to an element."""

    effect_type: str = Field(..., description="Effect type (e.g., 'On', 'ColorWash')")
    start_time_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_time_ms: int = Field(..., ge=0, description="End time in milliseconds")
    palette: str = Field(default="", description="Color palette reference")
    protected: bool = Field(default=False, description="Whether effect is locked")
    ref: int | None = Field(default=None, description="EffectDB reference index")
    label: str | None = Field(default=None, description="Effect label (for timing markers)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Effect parameters")

    model_config = ConfigDict(extra="ignore")

    @field_validator("end_time_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info) -> int:
        """Validate end_time >= start_time."""
        start_time = info.data.get("start_time_ms")
        if start_time is not None and v < start_time:
            raise ValueError(f"end_time_ms ({v}) must be >= start_time_ms ({start_time})")
        return v

    @property
    def duration_ms(self) -> int:
        """Get effect duration in milliseconds."""
        return self.end_time_ms - self.start_time_ms


class EffectLayer(BaseModel):
    """A layer of effects on an element."""

    index: int = Field(..., ge=0, description="Layer index")
    name: str = Field(default="", description="Layer name")
    effects: list[Effect] = Field(default_factory=list, description="Effects in this layer")

    model_config = ConfigDict(extra="ignore")


class ElementEffects(BaseModel):
    """Effects for a single element (model, group, etc.)."""

    element_name: str = Field(..., description="Element name")
    element_type: str = Field(default="model", description="Element type")
    layers: list[EffectLayer] = Field(default_factory=list, description="Effect layers")

    model_config = ConfigDict(extra="ignore")


class EffectDB(BaseModel):
    """Effect database containing effect settings strings."""

    entries: list[str] = Field(default_factory=list, description="Effect settings strings")

    model_config = ConfigDict(extra="ignore")

    def append(self, settings: str) -> int:
        """Append a settings string to EffectDB.

        Args:
            settings: Effect settings string

        Returns:
            Index of the added entry
        """
        self.entries.append(settings)
        return len(self.entries) - 1

    def get(self, index: int) -> str | None:
        """Get effect settings string by index.

        Args:
            index: EffectDB index

        Returns:
            Settings string or None if index out of range
        """
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None


class ColorPalette(BaseModel):
    """A color palette definition."""

    settings: str = Field(..., description="Palette settings string")

    model_config = ConfigDict(extra="ignore")


class SequenceHead(BaseModel):
    """Sequence header/metadata."""

    version: str = Field(..., description="xLights version")
    author: str = Field(default="", description="Author name")
    author_email: str = Field(default="", description="Author email")
    author_website: str = Field(default="", description="Author website")
    song: str = Field(default="", description="Song name")
    artist: str = Field(default="", description="Artist name")
    album: str = Field(default="", description="Album name")
    music_url: str = Field(default="", description="Music URL")
    comment: str = Field(default="", description="Comment")
    sequence_timing: str = Field(default="50 ms", description="Sequence timing")
    sequence_type: str = Field(default="Media", description="Sequence type")
    media_file: str = Field(..., description="Media file path")
    sequence_duration_ms: int = Field(..., ge=0, description="Sequence duration in milliseconds")
    image_dir: str = Field(default="", description="Image directory")

    model_config = ConfigDict(extra="ignore")

    @field_validator("sequence_duration_ms")
    @classmethod
    def validate_duration_positive(cls, v: int) -> int:
        """Validate duration is non-negative."""
        if v < 0:
            raise ValueError(f"sequence_duration_ms must be non-negative, got {v}")
        return v


class XSequence(BaseModel):
    """Complete xLights sequence model."""

    # Root attributes
    base_channel: int = Field(default=0, description="Base channel")
    chan_ctrl_basic: int = Field(default=0, description="Channel control basic")
    chan_ctrl_color: int = Field(default=0, description="Channel control color")
    fixed_point_timing: bool = Field(default=True, description="Fixed point timing")
    model_blending: bool = Field(default=True, description="Model blending")

    # Head/metadata
    head: SequenceHead = Field(..., description="Sequence header")

    # Optional sections
    next_id: int = Field(default=1, description="Next ID")
    effect_db: EffectDB = Field(default_factory=EffectDB, description="Effect database")
    color_palettes: list[ColorPalette] = Field(default_factory=list, description="Color palettes")

    # Timing and effects
    timing_tracks: list[TimingTrack] = Field(default_factory=list, description="Timing tracks")
    element_effects: list[ElementEffects] = Field(
        default_factory=list, description="Element effects"
    )

    model_config = ConfigDict(extra="ignore")

    @property
    def version(self) -> str:
        """Get xLights version."""
        return self.head.version

    @property
    def media_file(self) -> str:
        """Get media file path."""
        return self.head.media_file

    @property
    def sequence_duration_ms(self) -> int:
        """Get sequence duration in milliseconds."""
        return self.head.sequence_duration_ms

    def get_element(self, element_name: str) -> ElementEffects | None:
        """Get element by name.

        Args:
            element_name: Name of element to find

        Returns:
            ElementEffects if found, None otherwise
        """
        for element in self.element_effects:
            if element.element_name == element_name:
                return element
        return None

    def has_element(self, element_name: str) -> bool:
        """Check if element exists.

        Args:
            element_name: Name of element to check

        Returns:
            True if element exists, False otherwise
        """
        return self.get_element(element_name) is not None

    def ensure_element(self, element_name: str, *, element_type: str = "model") -> ElementEffects:
        """Ensure element exists, creating if necessary.

        Args:
            element_name: Name of element
            element_type: Type of element (default: "model")

        Returns:
            ElementEffects instance
        """
        element = self.get_element(element_name)
        if element is None:
            element = ElementEffects(
                element_name=element_name,
                element_type=element_type,
                layers=[EffectLayer(index=0, name="", effects=[])],
            )
            self.element_effects.append(element)
        return element

    def drop_element(self, element_name: str) -> None:
        """Remove element from sequence.

        Args:
            element_name: Name of element to remove
        """
        self.element_effects = [e for e in self.element_effects if e.element_name != element_name]

    def reset_element_effects(self, element_name: str) -> None:
        """Reset all effects for an element, keeping the element.

        Args:
            element_name: Name of element to reset
        """
        element = self.get_element(element_name)
        if element is not None:
            element.layers = [EffectLayer(index=0, name="", effects=[])]

    def add_effect(self, element_name: str, effect: Effect, layer_index: int = 0) -> None:
        """Add effect to an element's layer.

        Args:
            element_name: Name of element
            effect: Effect to add
            layer_index: Layer index to add to

        Raises:
            ValueError: If element or layer not found
        """
        element = self.ensure_element(element_name)

        # Ensure layer exists
        while layer_index >= len(element.layers):
            element.layers.append(EffectLayer(index=len(element.layers), name="", effects=[]))

        element.layers[layer_index].effects.append(effect)

    def append_effectdb(self, settings: str) -> int:
        """Append settings string to EffectDB.

        Args:
            settings: Effect settings string

        Returns:
            Index of the added entry
        """
        return self.effect_db.append(settings)

    def get_effectdb(self) -> list[str]:
        """Get all EffectDB entries.

        Returns:
            List of effect settings strings
        """
        return self.effect_db.entries.copy()

    def iter_effect_placements(self) -> list[Any]:
        """Iterate all effect placements in the sequence.

        Returns:
            List of EffectPlacement objects (for backward compatibility)
        """
        from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import (
            EffectPlacement,
        )

        placements = []
        for element in self.element_effects:
            for layer in element.layers:
                for effect in layer.effects:
                    placements.append(
                        EffectPlacement(
                            element_name=element.element_name,
                            effect_name=effect.effect_type,
                            start_ms=effect.start_time_ms,
                            end_ms=effect.end_time_ms,
                            effect_label=effect.label,
                            ref=effect.ref,
                            palette=int(effect.palette) if effect.palette.isdigit() else 0,
                        )
                    )
        return placements

    def effect_type_histogram(self) -> dict[str, int]:
        """Get histogram of effect types.

        Returns:
            Dictionary mapping effect type names to counts
        """
        hist: dict[str, int] = {}
        for placement in self.iter_effect_placements():
            hist[placement.effect_name] = hist.get(placement.effect_name, 0) + 1
        return hist

    def get_version(self) -> str:
        """Get xLights version from sequence head.

        Returns:
            Version string (e.g., "2023.17")
        """
        return self.head.version

    def get_sequence_duration_s(self) -> float:
        """Get sequence duration in seconds.

        Returns:
            Duration in seconds
        """
        return self.head.sequence_duration_ms / 1000.0

    def list_timing_tracks(self) -> list[str]:
        """List all timing track names.

        Returns:
            List of timing track names
        """
        return [track.name for track in self.timing_tracks]

    def extract_timing_events(self, track_name: str) -> list[dict[str, Any]]:
        """Extract timing events from a timing track.

        Args:
            track_name: Name of timing track

        Returns:
            List of timing event dictionaries with 'time_ms' and 'label' keys
        """
        for track in self.timing_tracks:
            if track.name == track_name:
                return [
                    {"time_ms": marker.time_ms, "label": marker.name} for marker in track.markers
                ]
        return []
