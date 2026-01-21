"""Channel effect libraries (color, gobo, shutter)."""

from blinkb0t.core.domains.sequencing.libraries.channels.color import (
    COLOR_LIBRARY,
    ColorLibrary,
    ColorMood,
    ColorPresetDefinition,
)
from blinkb0t.core.domains.sequencing.libraries.channels.gobo import (
    GOBO_LIBRARY,
    GoboLibrary,
    GoboPatternDefinition,
)
from blinkb0t.core.domains.sequencing.libraries.channels.shutter import (
    SHUTTER_LIBRARY,
    ShutterLibrary,
    ShutterPatternDefinition,
)

__all__ = [
    # Singletons
    "COLOR_LIBRARY",
    "GOBO_LIBRARY",
    "SHUTTER_LIBRARY",
    # Classes
    "ColorLibrary",
    "GoboLibrary",
    "ShutterLibrary",
    # Models
    "ColorMood",
    "ColorPresetDefinition",
    "GoboPatternDefinition",
    "ShutterPatternDefinition",
]
