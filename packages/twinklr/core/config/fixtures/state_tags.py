"""What a profile's tagged wheel and shutter states mean, and guidance to tag the rest.

A discrete state may carry one meaning tag (`DiscreteState.hex`, `.pattern`,
`.strobe`). The lookups here are pure functions of one profile (or of its tagged states),
which the rig offer and the resolution of the planner's colour and gobo use
(`sequencer/moving_heads/song_intent.py`). An untagged state is never guessed at: it is
not offered.

`tag_guidance` prints, for a profile with untagged states, the channels' states ready to
paste with each missing tag either a placeholder or a value suggested from the state's
name or the fixture's xLights model, marked as a suggestion for the user to confirm.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

PALE_CHROMA = 0.10
"""Below this chroma a requested tint (a pastel such as `#FFCCBC`) may also take a white
slot, when white is nearer it (Oklab) than the best slot with a hue."""

MIN_LIGHTNESS = 0.15
"""Below this Oklab lightness a request is too dark for any wheel slot: darkness is the
dimmer's, so it gets no match."""

EXACT_DISTANCE = 0.02
"""Graded difference (`ColorMatch.graded_distance`) within which a slot shows the request
exactly (about one just-noticeable difference)."""

CLOSE_DISTANCE = 0.10
"""Graded difference within which a slot shows the request closely..."""
CLOSE_HUE = 25.0
"""...when its hue is also within this many degrees."""

HUE_CAP = 75.0
"""Beyond this hue difference no slot with a hue stands in for the request."""

MIN_CHROMA_RATIO = 0.6
"""A slot with a hue stands in for a request only with at least this share of its
chroma, so a tint (a CTO or CTB slot) never stands in for a saturated colour."""

ColorFit = Literal["exact", "close", "approximate", "hue_mismatch"]
"""How faithfully a matched state shows a requested colour, graded on
`ColorMatch.graded_distance` (the slot at the dimmer level that brings it nearest).

- `exact`: within `EXACT_DISTANCE`.
- `close`: within `CLOSE_DISTANCE` and, for colours with a hue, `CLOSE_HUE`.
- `approximate`: the best slot, with a hue within `HUE_CAP` (or a white for a white or
  pale request, further than `CLOSE_DISTANCE`).
- `hue_mismatch`: no slot shows anything like it; the state is the nearest white slot
  (`neutral_fallback`) or, without one, the nearest by hue. Not to be offered.
"""


class ColorMatch(NamedTuple):
    """The tagged colour state chosen for a requested colour."""

    state: str
    hex: str
    distance: float
    """Oklab colour difference (ΔE_OK) between the request and `hex`: 0 is the same
    colour, about 0.02 a just-noticeable difference, black to white 1."""
    hue_difference: float | None
    """Degrees between the request's hue and `hex`'s (0 to 180); None when either is a
    white (chroma below `NEUTRAL_CHROMA`) and has no hue."""
    fit: ColorFit
    neutral_fallback: bool
    """A white slot was returned for a request with a hue because no slot matched it."""
    graded_distance: float
    """What `fit` grades: the Oklab difference between the request and the slot dimmed to
    the level that brings it nearest (never brighter than the slot). A dimmer scales
    linear RGB, which scales every Oklab coordinate alike, so a request that is the slot's
    colour at a lower level grades as that colour; a lighter or more saturated request
    than the slot still counts its difference. Equal to `distance` or less."""


def tagged_colors(profile: FixtureCapabilities) -> dict[str, str]:
    """Each colour-wheel state with a `hex` tag and its colour, by state name."""
    wheel = profile.discrete.get("color")
    if wheel is None:
        return {}
    return {name: state.hex for name, state in sorted(wheel.states.items()) if state.hex}


def nearest_color_state(profile: FixtureCapabilities, color: str) -> ColorMatch | None:
    """`nearest_tagged_color` over the profile's tagged colour states (`tagged_colors`)."""
    return nearest_tagged_color(tagged_colors(profile), color)


def nearest_tagged_color(colors: Mapping[str, str], color: str) -> ColorMatch | None:
    """The state of `colors` (state name → `#RRGGBB`) to show `color` (`#RRGGBB` or a
    colour preset name); None when `colors` is empty or the request is darker than
    `MIN_LIGHTNESS`.

    Hue first, in OKLCh:

    - A white request (chroma below `NEUTRAL_CHROMA`) takes the nearest white slot
      (Oklab); without one, the nearest slot, as a `hue_mismatch`.
    - A request with a hue takes, among the slots with a hue and at least
      `MIN_CHROMA_RATIO` of its chroma, the one whose hue is nearest, then whose chroma,
      then whose lightness. A pale request (chroma below `PALE_CHROMA`) takes the nearest
      white slot instead when that is nearer it (Oklab) or no slot with a hue qualifies.
      When no slot qualifies or the best is more than `HUE_CAP` away, the result is a `hue_mismatch`: the nearest white slot
      (`neutral_fallback`), else the slot with a hue nearest by hue.

    Ties go to the first state name. `fit` grades the result (`ColorFit`) on its
    `graded_distance`.

    Raises:
        ValueError: If `color` is not a colour.
    """
    slots = {name: (shown, _oklab(shown)) for name, shown in sorted(colors.items())}
    wanted = _oklab(canonical_hex(color))
    if not slots or wanted[0] < MIN_LIGHTNESS:
        return None
    whites = [name for name, (_, lab) in slots.items() if _chroma(lab) < NEUTRAL_CHROMA]
    hued = [name for name in slots if name not in whites]

    def distance(name: str) -> float:
        return math.dist(wanted, slots[name][1])

    def by_hue(name: str) -> tuple[float, ...]:
        lab = slots[name][1]
        return (
            _hue_difference(wanted, lab),
            abs(_chroma(wanted) - _chroma(lab)),
            abs(wanted[0] - lab[0]),
        )

    def result(name: str, fit: ColorFit | None = None, fallback: bool = False) -> ColorMatch:
        shown, lab = slots[name]
        hue = (
            _hue_difference(wanted, lab)
            if min(_chroma(wanted), _chroma(lab)) >= NEUTRAL_CHROMA
            else None
        )
        graded = _dimmed_distance(wanted, lab)
        if fit is None:
            if graded <= EXACT_DISTANCE:
                fit = "exact"
            elif graded <= CLOSE_DISTANCE and (hue is None or hue <= CLOSE_HUE):
                fit = "close"
            else:
                fit = "approximate"
        return ColorMatch(name, shown, distance(name), hue, fit, fallback, graded)

    def nearest(names: list[str]) -> str:
        return min(names, key=lambda name: (distance(name), name))

    if _chroma(wanted) < NEUTRAL_CHROMA:
        return result(nearest(whites)) if whites else result(nearest(hued), "hue_mismatch")
    able = [n for n in hued if _chroma(slots[n][1]) >= MIN_CHROMA_RATIO * _chroma(wanted)]
    best = min(able, key=lambda name: (*by_hue(name), name)) if able else None
    within = best is not None and by_hue(best)[0] <= HUE_CAP
    if _chroma(wanted) < PALE_CHROMA and whites:
        white = nearest(whites)
        if best is None or not within or distance(white) < distance(best):
            return result(white)
    if best is not None and within:
        return result(best)
    if whites:
        return result(nearest(whites), "hue_mismatch", fallback=True)
    return result(min(hued, key=lambda name: (*by_hue(name), name)), "hue_mismatch")


def oklch(color: str) -> tuple[float, float, float]:
    """`color` (`#RRGGBB` or a preset name) as OKLCh: lightness, chroma, hue in degrees
    (0 to 360; meaningless below `NEUTRAL_CHROMA`)."""
    lab = _oklab(canonical_hex(color))
    return lab[0], _chroma(lab), math.degrees(math.atan2(lab[2], lab[1])) % 360


def color_distance(first: str, second: str) -> float:
    """The Oklab colour difference (ΔE_OK) between two colours (`#RRGGBB` or preset
    names): the Euclidean distance between their Oklab coordinates."""
    return math.dist(_oklab(canonical_hex(first)), _oklab(canonical_hex(second)))


def gobo_state(profile: FixtureCapabilities, pattern: GoboPattern | str) -> str | None:
    """The gobo state tagged with `pattern`; None when none is. Among states sharing a
    pattern, the shortest name, then the first by name: a static `star` before its
    shaking copy `star_shake`."""
    wheel = profile.discrete.get("gobo")
    states = wheel.states.items() if wheel is not None else ()
    return tagged_gobo({name: state.pattern for name, state in states if state.pattern}, pattern)


def tagged_gobo(patterns: Mapping[str, str], pattern: GoboPattern | str) -> str | None:
    """The state of `patterns` (state name → pattern) showing `pattern`, by `gobo_state`'s
    rule; None when none does."""
    wanted = GoboPattern(pattern)
    names = [name for name, shown in patterns.items() if shown == wanted]
    return min(names, key=lambda name: (len(name), name), default=None)


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


def _dimmed_distance(wanted: tuple[float, float, float], slot: tuple[float, float, float]) -> float:
    """The Oklab difference between `wanted` and `slot` scaled by the factor in (0, 1]
    that brings it nearest: a dimmer level times linear RGB scales each Oklab coordinate
    by that level's cube root, so the slot at any level is `slot` times one factor."""
    norm = sum(value * value for value in slot)
    dot = sum(w * v for w, v in zip(wanted, slot, strict=True))
    scale = 1.0 if norm == 0 else min(1.0, max(0.0, dot / norm))
    return math.dist(wanted, tuple(scale * value for value in slot))


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
_OPT_OUT = (
    "A state that honestly has no such meaning (a pulse, a random strobe, a rainbow scroll, "
    'a gobo shake) takes "offer": false in place of the tag, and is never offered.'
)
_VARIABLE_STROBE = (
    "A shutter whose strobe is one variable slow-to-fast range offers one speed as one "
    "state; to offer slow, medium and fast, split the range into three states, one per "
    "speed."
)
"""What an untagged state gets in the snippet; each is refused if pasted unfilled."""

_STROBE_SPEEDS: tuple[str, ...] = get_args(StrobeSpeed)
_MODIFIERS = frozenset({"light", "dark", "deep", "pale"})
"""Words that make a colour name something other than the preset it contains."""


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
            if getattr(state, tag) is None and state.offer is None and name not in declared
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
        "(pasted unfilled, it is refused when the fixture file loads). "
        + _OPT_OUT
        + (f" {_VARIABLE_STROBE}" if "shutter" in snippet else "")
        + "\n"
        + _snippet_json(snippet)
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
    found: list[str] = []
    if channel == "color":
        if not _MODIFIERS & set(words):
            rest = list(words)
            while rest:
                pair = "_".join(rest[:2])
                if len(rest) > 1 and pair in COLOR_PRESET_HEX:
                    found.append(pair)
                    rest = rest[2:]
                    continue
                if rest[0] in COLOR_PRESET_HEX:
                    found.append(rest[0])
                rest = rest[1:]
        if not found and words == ["open"]:
            found = [ColorPreset.WHITE.value]  # a colour wheel's open slot shows white
    elif channel == "gobo":
        patterns = {pattern.value for pattern in GoboPattern}
        found = [form for word in words for form in (word, f"{word}s") if form in patterns]
    elif "strobe" in words:
        found = [speed for speed in _STROBE_SPEEDS if speed in words]
    # A modifier (`dark_blue`), two colours (`red_blue`), two patterns or two speeds (a
    # variable range) do not name one value: the user fills the placeholder.
    value = found[0] if len(set(found)) == 1 else None
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
