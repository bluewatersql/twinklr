"""What a profile's tagged wheel and shutter states mean, and guidance to tag the rest.

A discrete state may carry one meaning tag (`DiscreteState.hex`, `.pattern`,
`.strobe`). The lookups here are pure functions of one profile, for the planner's rig
offer and the resolution of its colour, gobo and strobe choices (song-intent rendering
W3/W4); nothing renders from a tag yet. An untagged state is never guessed at: it is
not offered.

`tag_guidance` prints, for a profile with untagged states, the channels' states ready to
paste with each missing tag either a placeholder or a value suggested from the state's
name or the fixture's xLights model, marked as a suggestion for the user to confirm.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise
import json
import math
import re
from typing import Literal, NamedTuple, get_args

from twinklr.core.config.fixtures.capabilities import (
    STATE_TAGS,
    FixtureCapabilities,
    StrobeSpeed,
)
from twinklr.core.config.fixtures.instances import FixtureInstance
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
from twinklr.core.sequencer.moving_heads.libraries.color import (
    COLOR_PRESET_HEX,
    ColorPreset,
    canonical_hex,
)
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern

NEUTRAL_CHROMA = 0.04
"""OKLCh chroma below which a colour counts as a white. The colour presets' whites reach
0.029 (`cool_white`) and the palette catalog's tinted whites 0.013, while its palest
tints start at 0.060; saturated wheel colours are 0.15 and above."""

ColorFit = Literal["exact", "approximate", "no_chromatic_match_used_neutral"]
"""How faithfully a matched state shows a requested colour: the same colour; another
colour (the nearest by the rules of `nearest_color_state`); or a white, because the
request has a hue and the wheel has no tagged slot that does."""


class ColorMatch(NamedTuple):
    """The tagged colour state chosen for a requested colour."""

    state: str
    hex: str
    distance: float
    """Oklab colour difference (ΔE_OK) between the request and `hex`: 0 is the same
    colour, about 0.02 a just-noticeable difference, black to white 1."""
    fit: ColorFit


def tagged_colors(profile: FixtureCapabilities) -> dict[str, str]:
    """Each colour-wheel state with a `hex` tag and its colour, by state name."""
    wheel = profile.discrete.get("color")
    if wheel is None:
        return {}
    return {name: state.hex for name, state in sorted(wheel.states.items()) if state.hex}


def nearest_color_state(profile: FixtureCapabilities, color: str) -> ColorMatch | None:
    """The tagged colour state to show `color` (`#RRGGBB` or a colour preset name); None
    when no colour state is tagged.

    Hue first, in OKLCh. A request with a hue (chroma at least `NEUTRAL_CHROMA`) goes to
    the tagged slot with a hue whose hue angle is nearest, then whose chroma, then whose
    lightness is nearest; a white slot is chosen only when no tagged slot has a hue
    (`fit` says so). A white request goes to the white slot nearest in lightness and
    tint (`color_distance`), or, on a wheel without one, to the nearest slot. Ties go to
    the first state name.

    Raises:
        ValueError: If `color` is not a colour.
    """
    target = canonical_hex(color)
    slots = {name: (shown, _oklab(shown)) for name, shown in tagged_colors(profile).items()}
    if not slots:
        return None
    wanted = _oklab(target)
    hued = {name for name, (_, lab) in slots.items() if _chroma(lab) >= NEUTRAL_CHROMA}
    pool = (hued if _chroma(wanted) >= NEUTRAL_CHROMA else slots.keys() - hued) or slots.keys()

    def rank(name: str) -> tuple[float, ...]:
        lab = slots[name][1]
        if _chroma(wanted) >= NEUTRAL_CHROMA and name in hued:
            return (
                _hue_difference(wanted, lab),
                abs(_chroma(wanted) - _chroma(lab)),
                abs(wanted[0] - lab[0]),
            )
        return (math.dist(wanted, lab),)

    state = min(sorted(pool), key=rank)
    shown, lab = slots[state]
    distance = math.dist(wanted, lab)
    fit: ColorFit = "exact" if distance == 0 else "approximate"
    if _chroma(wanted) >= NEUTRAL_CHROMA and state not in hued:
        fit = "no_chromatic_match_used_neutral"
    return ColorMatch(state, shown, distance, fit)


def color_distance(first: str, second: str) -> float:
    """The Oklab colour difference (ΔE_OK) between two colours (`#RRGGBB` or preset
    names): the Euclidean distance between their Oklab coordinates."""
    return math.dist(_oklab(canonical_hex(first)), _oklab(canonical_hex(second)))


def gobo_state(profile: FixtureCapabilities, pattern: GoboPattern | str) -> str | None:
    """The first gobo state, by name, tagged with `pattern`; None when none is."""
    wanted = GoboPattern(pattern)
    wheel = profile.discrete.get("gobo")
    states = sorted(wheel.states.items()) if wheel is not None else []
    return next((name for name, state in states if state.pattern == wanted), None)


def strobe_state(profile: FixtureCapabilities, speed: StrobeSpeed) -> str | None:
    """The shutter state tagged as strobing at `speed` (at most one); None when none is."""
    shutter = profile.discrete.get("shutter")
    states = shutter.states.items() if shutter is not None else ()
    return next((name for name, state in states if state.strobe == speed), None)


# Oklab (Ottosson 2020): sRGB linearised (IEC 61966-2-1), to LMS, cube root, to Lab.
_SRGB_TO_LMS = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_LMS_TO_OKLAB = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)


def _oklab(hex_color: str) -> tuple[float, float, float]:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    def times(matrix: tuple[tuple[float, ...], ...], vector: list[float]) -> list[float]:
        return [sum(w * v for w, v in zip(row, vector, strict=True)) for row in matrix]

    rgb = [linear(int(hex_color[index : index + 2], 16)) for index in (1, 3, 5)]
    lms = [value ** (1 / 3) for value in times(_SRGB_TO_LMS, rgb)]
    lightness, a, b = times(_LMS_TO_OKLAB, lms)
    return lightness, a, b


def _chroma(lab: tuple[float, float, float]) -> float:
    return math.hypot(lab[1], lab[2])


def _hue_difference(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    """The angle between two colours' hues, in degrees (0 to 180)."""
    turn = abs(math.atan2(first[2], first[1]) - math.atan2(second[2], second[1]))
    return math.degrees(min(turn, 2 * math.pi - turn))


# --- Guidance ---------------------------------------------------------------------------

_PLACEHOLDERS = {
    "hex": f"<#RRGGBB or a colour name: {', '.join(ColorPreset)}>",
    "pattern": f"<one of: {', '.join(GoboPattern)}>",
    "strobe": "<slow, medium or fast; delete this key if the state does not strobe>",
}
"""What an untagged state gets in the snippet; each is refused if pasted unfilled."""

_STROBE_SPEEDS: tuple[str, ...] = get_args(StrobeSpeed)


def tag_guidance(
    profile: FixtureCapabilities,
    *,
    layout_hex: Mapping[str, str] | None = None,
    layout_model: str | None = None,
) -> str | None:
    """Paste-ready tags for `profile`'s untagged states, or None when there are none.

    An untagged state is a color or gobo state without its tag, or a shutter state
    without one that is not the open, closed or an extinguishing state (those already
    say what they do). The snippet holds each such channel's whole `states`, so it
    replaces that object; a missing tag is a placeholder or a suggestion, and every
    suggestion is listed after the snippet for the user to confirm. Nothing is applied.

    Args:
        profile: The profile to tag.
        layout_hex: Colours proposed for colour states (`layout_color_tags`); they win
            over a suggestion from the state's name.
        layout_model: The xLights model `layout_hex` was read from, to name the source.
    """
    snippet: dict[str, dict[str, dict[str, object]]] = {}
    suggested: list[str] = []
    count = 0
    for channel, wheel in profile.discrete.items():
        tag = STATE_TAGS[channel]
        declared = _declared_shutter_states(profile) if channel == "shutter" else set()
        untagged = [
            name
            for name, state in wheel.states.items()
            if getattr(state, tag) is None and name not in declared
        ]
        if not untagged:
            continue
        count += len(untagged)
        states: dict[str, dict[str, object]] = {}
        for name, state in wheel.states.items():
            entry: dict[str, object] = state.model_dump(mode="json", exclude_none=True)
            if name in untagged:
                value, source = _suggestion(channel, name, layout_hex or {}, layout_model)
                entry[tag] = _PLACEHOLDERS[tag] if value is None else value
                if value is not None:
                    suggested.append(
                        f'  {channel}.{name}: {tag} "{value}" (suggested from {source})'
                    )
            states[name] = entry
        snippet[channel] = states
    if not snippet:
        return None
    many = count > 1
    text = (
        f"{count} wheel or shutter state{'s do' if many else ' does'} not say what "
        f"{'they show' if many else 'it shows'}, so the planner's colour, gobo and strobe "
        f"choices cannot use {'them' if many else 'it'}. Under the profile's `discrete`, "
        "replace each channel's `states` with the one below; fill every <...> placeholder "
        "(pasted unfilled, it is refused when the fixture file loads):\n" + _snippet_json(snippet)
    )
    if suggested:
        text += (
            "These values are only suggestions; confirm each against the fixture before "
            "pasting:\n" + "\n".join(suggested) + "\n"
        )
    return text


def _snippet_json(snippet: Mapping[str, Mapping[str, object]]) -> str:
    """`{"<channel>": {"states": {...}}, ...}` as JSON with one line per state."""
    channels = []
    for channel, states in snippet.items():
        rows = ",\n".join(
            f"    {json.dumps(name)}: {json.dumps(entry)}" for name, entry in states.items()
        )
        channels.append(f'  {json.dumps(channel)}: {{"states": {{\n{rows}\n  }}}}')
    return "{\n" + ",\n".join(channels) + "\n}\n"


def _declared_shutter_states(profile: FixtureCapabilities) -> set[str]:
    shutter = profile.discrete["shutter"]
    declared = {name for name in (shutter.open_state, shutter.closed_state) if name}
    return declared | set(profile.visibility.extinguishing_shutter_states)


def _suggestion(
    channel: str, name: str, layout_hex: Mapping[str, str], layout_model: str | None
) -> tuple[str | None, str]:
    """A tag value for state `name` and where it came from, or `(None, "")`."""
    if channel == "color" and name in layout_hex:
        return layout_hex[name], f"xLights model {layout_model!r}"
    words = [word for word in re.split(r"[^a-z]+", name.lower()) if word]
    value: str | None = None
    if channel == "color":
        candidates = ["_".join(pair) for pair in pairwise(words)] + words
        value = next((word for word in candidates if word in COLOR_PRESET_HEX), None)
        if value is None and words == ["open"]:
            value = ColorPreset.WHITE.value  # a colour wheel's open slot shows white
    elif channel == "gobo":
        patterns = {pattern.value for pattern in GoboPattern}
        value = next(
            (form for word in words for form in (word, f"{word}s") if form in patterns),
            None,
        )
    elif "strobe" in words:
        value = next((speed for speed in _STROBE_SPEEDS if speed in words), None)
    return value, "the state name" if value is not None else ""


def layout_color_tags(profile: FixtureCapabilities, model: Model) -> dict[str, str]:
    """Colours an xLights DMX model's colour-wheel slots propose for `profile`'s colour
    states: each slot whose byte lies in a state's range proposes its colour for that
    state. A state with two different proposed colours gets none, and a slot whose byte
    or colour does not read as one is skipped. Proposals are for the user to confirm.
    """
    wheel = profile.discrete.get("color")
    if wheel is None:
        return {}
    proposed: dict[str, set[str]] = {}
    for raw_byte, raw_color in model.dmx_color_wheel():
        try:
            byte = int(raw_byte.strip())
            color = canonical_hex(raw_color.strip())
        except ValueError:
            continue
        for name, state in wheel.states.items():
            if state.range_min <= byte <= state.range_max:
                proposed.setdefault(name, set()).add(color)
    return {name: colors.pop() for name, colors in sorted(proposed.items()) if len(colors) == 1}


class RigTagGuidance(NamedTuple):
    """`tag_guidance` for the fixtures that share it."""

    fixture_ids: tuple[str, ...]
    text: str
    """The guidance, headed by the fixtures and their profile id."""


def rig_tag_guidance(
    fixtures: Sequence[FixtureInstance], models: Sequence[Model] = ()
) -> tuple[RigTagGuidance, ...]:
    """`tag_guidance` for each profiled fixture, with colour proposals from its own
    xLights model when `models` (a layout's) has it; one entry per distinct guidance,
    naming every fixture it applies to and its profile id. Empty for a rig whose every
    state that can carry a meaning does."""
    by_name = {model.name: model for model in models}
    grouped: dict[tuple[str, str], list[str]] = {}
    for fixture in fixtures:
        profile = fixture.config.physical_profile
        if profile is None:
            continue
        model = by_name.get(fixture.xlights_model_name)
        layout_hex = layout_color_tags(profile, model) if model is not None else {}
        guidance = tag_guidance(
            profile, layout_hex=layout_hex, layout_model=fixture.xlights_model_name
        )
        if guidance is not None:
            grouped.setdefault((profile.profile_id, guidance), []).append(fixture.fixture_id)
    return tuple(
        RigTagGuidance(
            tuple(fixture_ids), f"{', '.join(fixture_ids)} (profile {profile_id!r}): {guidance}"
        )
        for (profile_id, guidance), fixture_ids in grouped.items()
    )
