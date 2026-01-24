from typing import Any

from blinkb0t.core.utils.logging import get_logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = get_logger(__name__)


class Alias(BaseModel):
    """Alias for a model or modelGroup."""

    model_config = ConfigDict(extra="forbid")  # Only accept known fields
    name: str


class AliasesContainer(BaseModel):
    """Container for model aliases."""

    model_config = ConfigDict(extra="forbid")
    alias: list[Alias] | Alias = Field(default_factory=list)


class ControllerConnection(BaseModel):
    """Controller connection configuration."""

    model_config = ConfigDict(extra="allow")  # Allow any controller attributes


class Model(BaseModel):
    """Individual lighting model/fixture in the layout."""

    model_config = ConfigDict(extra="allow")  # Allow unknown model attributes

    # Core attributes we care about
    name: str
    DisplayAs: str | None = None
    StartSide: str | None = None
    Dir: str | None = None
    LayoutGroup: str | None = None
    CustomColor: str | None = None
    StringType: str | None = None
    StartChannel: str | None = None

    # Position attributes
    WorldPosX: str | None = None
    WorldPosY: str | None = None
    WorldPosZ: str | None = None

    # Dynamic fields
    strings: dict[int, str] = Field(default_factory=dict, exclude=True)

    # Child elements we know about
    aliases: AliasesContainer | None = Field(default=None, alias="Aliases")
    controller_connection: ControllerConnection | None = Field(
        default=None, alias="ControllerConnection"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_dynamic_strings(cls, data: Any) -> Any:
        """Extract String1, String2, etc. into strings dict."""
        if not isinstance(data, dict):
            return data

        strings = {}
        keys_to_remove = []

        for key, value in data.items():
            if key.startswith("String") and key[6:].isdigit():
                num = int(key[6:])
                strings[num] = value
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del data[key]

        if strings:
            data["strings"] = strings

        return data

    def get_string(self, num: int) -> str | None:
        """Get a string by number."""
        return self.strings.get(num)


class SubModel(BaseModel):
    """Sub-model within a parent model."""

    model_config = ConfigDict(extra="allow")

    name: str
    layout: str | None = None
    type: str | None = None
    bufferstyle: str | None = None

    # Dynamic fields
    lines: dict[int, str] = Field(default_factory=dict, exclude=True)

    # Child elements
    aliases: AliasesContainer | None = Field(default=None, alias="Aliases")
    controller_connection: ControllerConnection | None = Field(
        default=None, alias="ControllerConnection"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_dynamic_lines(cls, data: Any) -> Any:
        """Extract line0, line1, etc. into lines dict."""
        if not isinstance(data, dict):
            return data

        lines = {}
        keys_to_remove = []

        for key, value in data.items():
            if key.startswith("line") and key[4:].isdigit():
                num = int(key[4:])
                lines[num] = value
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del data[key]

        if lines:
            data["lines"] = lines

        return data

    def get_line(self, num: int) -> str | None:
        """Get a line by number."""
        return self.lines.get(num)


class Models(BaseModel):
    """Container for all models in the layout."""

    model_config = ConfigDict(extra="forbid")

    model: list[Model] = Field(default_factory=list)
    subModel: list[SubModel] = Field(default_factory=list)


class ModelGroup(BaseModel):
    """Group of models that can be controlled together."""

    model_config = ConfigDict(extra="allow")

    name: str
    models: str | None = None
    LayoutGroup: str | None = None

    # Child elements
    aliases: AliasesContainer | None = Field(default=None, alias="Aliases")

    def get_model_list(self) -> list[str]:
        """Get list of model names in this group."""
        if not self.models:
            return []
        return [m.strip() for m in self.models.split(",")]


class ModelGroups(BaseModel):
    """Container for all model groups."""

    model_config = ConfigDict(extra="forbid")

    modelGroup: list[ModelGroup] = Field(default_factory=list)


class Settings(BaseModel):
    """Global settings for the layout."""

    model_config = ConfigDict(extra="allow")

    backgroundImage: str | None = None
    backgroundBrightness: str | None = None
    previewWidth: str | None = None
    previewHeight: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def extract_value(cls, v):
        """Extract 'value' attribute from dict if present."""
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return v


class Camera(BaseModel):
    """Camera viewpoint configuration."""

    model_config = ConfigDict(extra="allow")

    name: str
    zoom: str | None = None
    panx: str | None = None
    pany: str | None = None
    panz: str | None = None


class Viewpoints(BaseModel):
    """Container for camera viewpoints."""

    model_config = ConfigDict(extra="forbid")

    DefaultCamera2D: Camera | None = None
    DefaultCamera3D: Camera | None = None


class Layout(BaseModel):
    """Root model representing the xLights layout.

    Only parses known sections. Unknown XML elements are ignored.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Only parse what we have models for
    models: Models | None = None
    modelGroups: ModelGroups | None = None
    settings: Settings | None = None
    viewpoints: Viewpoints | None = Field(default=None, alias="Viewpoints")
