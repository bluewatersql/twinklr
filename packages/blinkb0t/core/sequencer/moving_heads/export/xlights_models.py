"""xLights Data Models for the moving head sequencer.

Pydantic models representing xLights sequence structure including
timing tracks, effects, layers, elements, and the complete sequence.

These models are independent from the legacy sequencing module and
designed specifically for the new IR-to-export pipeline.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimingMarker(BaseModel):
    """A timing marker in a timing track.

    Attributes:
        label: Marker label/name.
        time_ms: Time position in milliseconds.
        end_time_ms: Optional end time for range markers.

    Example:
        >>> marker = TimingMarker(label="Beat 1", time_ms=0)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(..., min_length=1)
    time_ms: int = Field(..., ge=0)
    end_time_ms: int | None = Field(None, ge=0)

    @field_validator("end_time_ms")
    @classmethod
    def validate_end_time(cls, v: int | None, info: Any) -> int | None:
        """Validate end_time_ms >= time_ms."""
        if v is not None:
            time_ms = info.data.get("time_ms", 0)
            if v < time_ms:
                raise ValueError(f"end_time_ms ({v}) must be >= time_ms ({time_ms})")
        return v


class TimingTrack(BaseModel):
    """A timing track containing timing markers.

    Attributes:
        name: Track name (e.g., "Beats", "Bars", "Phrases").
        markers: List of timing markers in this track.

    Example:
        >>> track = TimingTrack(name="Beats", markers=[...])
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    markers: list[TimingMarker] = Field(default_factory=list)


class Effect(BaseModel):
    """An effect applied to an element.

    Represents a single effect block in xLights with timing,
    type, settings, and optional value curves.

    Attributes:
        effect_type: Effect type (e.g., "On", "DMX", "ColorWash").
        start_time_ms: Start time in milliseconds.
        end_time_ms: End time in milliseconds.
        settings: Effect settings string.
        value_curves: Mapping of channel names to value curve strings.
        palette_ref: Optional color palette reference.
        effectdb_ref: Optional EffectDB reference index.

    Example:
        >>> effect = Effect(
        ...     effect_type="DMX",
        ...     start_time_ms=0,
        ...     end_time_ms=1000,
        ...     settings="E_TEXTCTRL_DMX1=128",
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    effect_type: str = Field(..., min_length=1)
    start_time_ms: int = Field(..., ge=0)
    end_time_ms: int = Field(..., ge=0)
    settings: str = Field(default="")
    value_curves: dict[str, str] = Field(default_factory=dict)
    palette_ref: int | None = Field(None, ge=0)
    effectdb_ref: int | None = Field(None, ge=0)

    @field_validator("end_time_ms")
    @classmethod
    def validate_end_time(cls, v: int, info: Any) -> int:
        """Validate end_time_ms >= start_time_ms."""
        start_time_ms = info.data.get("start_time_ms", 0)
        if v < start_time_ms:
            raise ValueError(f"end_time_ms ({v}) must be >= start_time_ms ({start_time_ms})")
        return v

    @property
    def duration_ms(self) -> int:
        """Get effect duration in milliseconds."""
        return self.end_time_ms - self.start_time_ms


class EffectLayer(BaseModel):
    """A layer of effects on an element.

    xLights supports multiple effect layers per element,
    allowing effect stacking and blending.

    Attributes:
        index: Layer index (0-based).
        name: Optional layer name.
        effects: List of effects in this layer.

    Example:
        >>> layer = EffectLayer(index=0, effects=[...])
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    name: str = Field(default="")
    effects: list[Effect] = Field(default_factory=list)


class ElementEffects(BaseModel):
    """Effects for a single element (model, group, submodel).

    Represents all effects applied to a single xLights element
    across all its layers.

    Attributes:
        element_name: Name of the element (fixture name in DMX).
        element_type: Type of element (model, group, submodel).
        layers: Effect layers for this element.

    Example:
        >>> element = ElementEffects(element_name="MH_1")
        >>> element.add_effect(effect, layer_index=0)
    """

    model_config = ConfigDict(extra="forbid")

    element_name: str = Field(..., min_length=1)
    element_type: str = Field(default="model")
    layers: list[EffectLayer] = Field(default_factory=list)

    def add_effect(self, effect: Effect, layer_index: int = 0) -> None:
        """Add effect to a layer, creating layers as needed.

        Args:
            effect: Effect to add.
            layer_index: Layer index to add to (creates layers if needed).
        """
        # Ensure enough layers exist
        while layer_index >= len(self.layers):
            self.layers.append(EffectLayer(index=len(self.layers)))

        self.layers[layer_index].effects.append(effect)


class EffectDB(BaseModel):
    """Effect database containing effect settings strings.

    xLights uses an EffectDB to deduplicate effect settings.
    Effects reference entries by index.

    Attributes:
        entries: List of effect settings strings.

    Example:
        >>> db = EffectDB()
        >>> idx = db.append("E_TEXTCTRL_DMX1=128")
        >>> settings = db.get(idx)
    """

    model_config = ConfigDict(extra="forbid")

    entries: list[str] = Field(default_factory=list)

    def append(self, settings: str) -> int:
        """Append settings string and return index.

        Args:
            settings: Effect settings string.

        Returns:
            Index of the added entry.
        """
        self.entries.append(settings)
        return len(self.entries) - 1

    def get(self, index: int) -> str | None:
        """Get settings by index.

        Args:
            index: EffectDB index.

        Returns:
            Settings string or None if index out of range.
        """
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None


class ColorPalette(BaseModel):
    """A color palette definition.

    Attributes:
        settings: Palette settings string.

    Example:
        >>> palette = ColorPalette(settings="C_BUTTON_Palette1=#FF0000")
    """

    model_config = ConfigDict(extra="forbid")

    settings: str = Field(..., min_length=1)


class SequenceHead(BaseModel):
    """Sequence header/metadata.

    Contains all metadata for an xLights sequence including
    version, media file, duration, and optional author info.

    Attributes:
        version: xLights version string.
        media_file: Path to media file.
        sequence_duration_ms: Total sequence duration in milliseconds.
        author: Optional author name.
        song: Optional song name.
        artist: Optional artist name.
        album: Optional album name.
        sequence_timing: Timing resolution (e.g., "50 ms").
        sequence_type: Sequence type (e.g., "Media").

    Example:
        >>> head = SequenceHead(
        ...     version="2024.1",
        ...     media_file="song.mp3",
        ...     sequence_duration_ms=180000,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., min_length=1)
    media_file: str = Field(..., min_length=1)
    sequence_duration_ms: int = Field(..., ge=0)

    author: str = Field(default="")
    author_email: str = Field(default="")
    song: str = Field(default="")
    artist: str = Field(default="")
    album: str = Field(default="")
    comment: str = Field(default="")
    sequence_timing: str = Field(default="50 ms")
    sequence_type: str = Field(default="Media")


class XLightsSequence(BaseModel):
    """Complete xLights sequence model.

    Top-level model representing a complete xLights sequence
    with all elements, effects, timing tracks, and metadata.

    Attributes:
        head: Sequence header/metadata.
        elements: List of elements with effects.
        timing_tracks: Timing tracks.
        effect_db: Effect database.
        color_palettes: Color palette definitions.

    Example:
        >>> head = SequenceHead(...)
        >>> seq = XLightsSequence(head=head)
        >>> seq.add_effect("MH_1", effect)
    """

    model_config = ConfigDict(extra="forbid")

    head: SequenceHead
    elements: list[ElementEffects] = Field(default_factory=list)
    timing_tracks: list[TimingTrack] = Field(default_factory=list)
    effect_db: EffectDB = Field(default_factory=EffectDB)
    color_palettes: list[ColorPalette] = Field(default_factory=list)

    @property
    def version(self) -> str:
        """Get xLights version."""
        return self.head.version

    @property
    def media_file(self) -> str:
        """Get media file path."""
        return self.head.media_file

    @property
    def duration_ms(self) -> int:
        """Get sequence duration in milliseconds."""
        return self.head.sequence_duration_ms

    def get_element(self, element_name: str) -> ElementEffects | None:
        """Get element by name.

        Args:
            element_name: Name of element to find.

        Returns:
            ElementEffects if found, None otherwise.
        """
        for element in self.elements:
            if element.element_name == element_name:
                return element
        return None

    def ensure_element(self, element_name: str, *, element_type: str = "model") -> ElementEffects:
        """Ensure element exists, creating if necessary.

        Args:
            element_name: Name of element.
            element_type: Type of element (default: "model").

        Returns:
            ElementEffects instance.
        """
        element = self.get_element(element_name)
        if element is None:
            element = ElementEffects(
                element_name=element_name,
                element_type=element_type,
            )
            self.elements.append(element)
        return element

    def add_effect(
        self,
        element_name: str,
        effect: Effect,
        layer_index: int = 0,
    ) -> None:
        """Add effect to an element.

        Creates the element if it doesn't exist.

        Args:
            element_name: Name of element.
            effect: Effect to add.
            layer_index: Layer index to add to.
        """
        element = self.ensure_element(element_name)
        element.add_effect(effect, layer_index)
