"""Semantic classification helpers for layout profiling."""

from __future__ import annotations

import re

from twinklr.core.profiling.models.enums import ModelCategory, SemanticSize

DMX_MODEL_TYPES: frozenset[str] = frozenset(
    {
        "dmxmovinghead",
        "dmxmovingheadadv",
        "dmxgeneral",
        "dmxservo",
        "dmxservo3d",
        "dmxfloodlight",
        "dmxfloodarea",
        "dmxskull",
    }
)

DMX_CONTROL_KEYWORDS: list[str] = [
    "dmx mh",
    "dmx-mh",
    "moving head",
    "dmx pan",
    "dmx tilt",
    "dmx dimmer",
    "dmx shutter",
    "dmx gobo",
    "dmx prism",
    "dmx frost",
    "dmx focus",
    "dmx color",
    "dmx fogger",
    "dmx snowmachine",
    "dmx hazer",
    "dmx laser",
]

SEMANTIC_CATEGORIES: dict[str, list[str]] = {
    "tree": ["tree", "megatree", "minitree", "xmas tree"],
    "arch": ["arch"],
    "icicle": ["icicle"],
    "matrix": ["matrix"],
    "spinner": ["spinner", "pinwheel"],
    "star": ["star", "topper"],
    "snowflake": ["snowflake", "flake"],
    "wreath": ["wreath", "poinsettia"],
    "cane": ["cane", "candy cane"],
    "roof": ["roof", "roofline"],
    "window": ["window"],
    "outline": ["outline"],
    "column": ["column", "pillar"],
    "character": ["deer", "elf", "gingerbread", "reindeer", "santa", "snowman"],
    "prop": ["lollipop", "igloo", "lamp", "lantern", "present", "gift", "stocking"],
    "bulb": ["singing bulb", "bulb"],
    "sign": ["sign", "merry", "letters"],
    "flood": ["flood"],
    "vertical": ["vertical"],
    "horizontal": ["horizontal"],
    "pixel_forest": ["pixel forest", "pixel tree"],
    "face": ["face", "singing face"],
    "moving_head": ["mh", "moving head"],
    "cube": ["cube"],
}

DISPLAY_AS_TO_SEMANTIC: dict[str, str] = {
    "arches": "arch",
    "candy canes": "cane",
    "circle": "spinner",
    "cube": "cube",
    "custom": "",
    "dmxfloodarea": "flood",
    "dmxfloodlight": "flood",
    "dmxmovinghead": "moving_head",
    "dmxmovingheadadv": "moving_head",
    "horiz matrix": "matrix",
    "icicles": "icicle",
    "poly line": "",
    "single line": "",
    "snowflakes": "snowflake",
    "spinner": "spinner",
    "star": "star",
    "tree 90": "tree",
    "tree 180": "tree",
    "tree 270": "tree",
    "tree 360": "tree",
    "tree flat": "tree",
    "vert matrix": "matrix",
    "window frame": "window",
    "wreath": "wreath",
}

SIZE_KEYWORDS_MEGA: list[str] = ["mega", "large", "lg", "big", "giant", "xl", "huge"]
SIZE_KEYWORDS_MINI: list[str] = ["mini", "small", "sm", "tiny", "little"]

_WORD_BOUNDARY = re.compile(r"\b")


def classify_semantic_tags(name: str, display_as: str = "") -> frozenset[str]:
    """Classify semantic tags from model/group naming.

    Args:
        name: Model or group name.
        display_as: xLights DisplayAs value used as fallback when name has no match.

    Returns:
        A deduplicated immutable set of semantic tags.
    """
    name_lower = name.lower()
    tags: set[str] = set()
    for category, keywords in SEMANTIC_CATEGORIES.items():
        if any(keyword in name_lower for keyword in keywords):
            tags.add(category)

    if not tags and display_as:
        fallback = DISPLAY_AS_TO_SEMANTIC.get(display_as.lower(), "")
        if fallback:
            tags.add(fallback)

    return frozenset(tags)


def classify_semantic_size(name: str) -> SemanticSize | None:
    """Infer coarse size hints from model name.

    Args:
        name: Model/group name.

    Returns:
        SemanticSize.MEGA, SemanticSize.MINI, or None when unspecified.
    """
    name_lower = name.lower()
    if any(keyword in name_lower for keyword in SIZE_KEYWORDS_MEGA):
        return SemanticSize.MEGA
    if any(keyword in name_lower for keyword in SIZE_KEYWORDS_MINI):
        return SemanticSize.MINI
    return None


def classify_model_category(name: str, display_as: str, is_active: bool) -> ModelCategory:
    """Classify a model into broad behavioral category.

    Args:
        name: Model name.
        display_as: xLights DisplayAs type.
        is_active: Whether model is active in the layout.

    Returns:
        ModelCategory enum value.
    """
    display_as_lower = display_as.lower()

    if display_as_lower in DMX_MODEL_TYPES:
        return ModelCategory.DMX_FIXTURE

    if display_as_lower == "single line":
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in DMX_CONTROL_KEYWORDS):
            return ModelCategory.AUXILIARY

    if not is_active:
        return ModelCategory.INACTIVE

    return ModelCategory.DISPLAY
