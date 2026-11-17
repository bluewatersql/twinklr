"""Functional identity of a moving-head render.

`render_fingerprint` hashes canonical JSON of everything that decides rendered output
and nothing that does not: diagnostic wording, wall-clock time and output paths are
left out, and neither mapping key order, the order templates are supplied in, nor the
spelling a plan uses for a template counts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, XLIGHTS_VERSION_STAMP
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from pydantic import BaseModel

BACKEND_ID = "xlights_dmx"
"""The backend the renderer writes: xLights DMX effects in an `.xsq`."""

RENDERER_REVISION = "8"
"""Bumped by hand in the commit that intentionally changes the renderer's output; the
render identity also carries the frame encoder's own version. 3: a section's colour and
gobo are rendered (song-intent rendering W4), so a plan that sets them renders
differently from revision 2. 4 (W3/W4 review fix round): a colour change that cannot dip
before a lit boundary turns in the section's first dark window instead of not at all, a
held state an overlay mask cannot reach falls back to the authored one, and a palette
role the section's palette lacks plays PRIMARY's stop instead of the fixed table's. 5
(W5): DRAMATIC and INTENSE play on the dimmer (`intensity.shape_section`), and under
`twinklr show` the moving heads' macro focal role adjusts a section's intensity, so a
plan that sets either, or a show render, renders differently from revision 4. 6 (W3/W4
second review): a boundary dip counts the darkness the previous cue already commands (a
dark span) and is bounded by the darkness it adds, so where a dark span meets a colour
change the dip adds less, or plays where revision 5 deferred or kept the change. 7 (W5
review fix round): intensity is shaped per lit run once every darkness is placed, every
run starting on an accent, accents on the frame nearest the beat, a run reaching 85% of
full shaped as full (the authored shape scaled), headroom gains capped so the peak
reaches full, and the dimmer latency lead capped under half a beat. 8 (W6/W7, and the W5
re-review): the plan's events play (`events`: closed/open, strobes, pulse, hits, colour and
gobo events, their lyric cues' emphasis), so a plan with events renders differently from
revision 7; and intensity's accents start no flash on a lit run's last frames, take a beat
just after a reveal in place of the reveal's own, start a run's own only after half a beat
of darkness, and blend the headroom and full shapes between 0.8 and 1.0 of full."""


def render_fingerprint(
    *,
    plan: BaseModel,
    beat_grid: BeatGrid,
    fixtures: FixtureGroup,
    templates: Sequence[TemplateDoc],
    policy: MHRenderPolicy,
    backend_id: str,
    renderer_revision: str,
    seed: int | None = None,
    phase_map: BaseModel | None = None,
    locks: Sequence[BaseModel] = (),
    preset_substitutions: Sequence[tuple[str, str | None]] = (),
    dark_spans: Sequence[tuple[int, int]] = (),
    palettes: Mapping[str, BaseModel] | None = None,
    focal_roles: Mapping[str, str] | None = None,
) -> str:
    """Hash the functional inputs of a render.

    Args:
        plan: The plan to render.
        beat_grid: The grid the plan is placed on.
        fixtures: The rig; fixture order counts.
        templates: Template documents, presets included; their order does not count.
        policy: The moving-head render policy.
        backend_id: Output backend identity, e.g. `BACKEND_ID`.
        renderer_revision: Renderer revision, from `RENDERER_REVISION`.
        seed: Seed of any seeded choice the render depends on.
        phase_map: A typed boundary map, when the renderer takes one.
        locks: Render locks the output must honor; hashed only when there are any, so
            a render without locks keeps its earlier identity. Neither the order of the
            locks nor of their fixtures and channels counts.
        preset_substitutions: `(section name, preset id or None)` for each section that
            renders a preset other than the one it names; hashed only when there are
            any, so a render without one keeps its earlier identity.
        dark_spans: `(start_ms, end_ms)` spans every fixture is held dark over, as the
            renderer snapped and merged them; hashed only when there are any, so a
            render without one keeps its earlier identity.
        palettes: The macro palette each section that names a palette-role colour
            resolves it through, by section id; hashed only when there are any, so a
            render without one keeps its earlier identity.
        focal_roles: The moving heads' macro focal role by song section id (`twinklr
            show`), which adjusts each section's intensity; hashed only when there are
            any, so a render without them keeps its earlier identity.

    Returns:
        A 64-character lowercase SHA-256 hex digest.
    """
    payload: dict[str, Any] = {
        "plan": _plan_payload(plan),
        "beat_grid": beat_grid.model_dump(mode="json"),
        "fixtures": fixtures.model_dump(mode="json"),
        "templates": sorted(
            (doc.model_dump(mode="json") for doc in templates),
            key=lambda doc: doc["template"]["template_id"],
        ),
        "policy": policy.model_dump(mode="json"),
        "backend_id": backend_id,
        "renderer_revision": renderer_revision,
        "seed": seed,
        "phase_map": phase_map.model_dump(mode="json") if phase_map is not None else None,
        "effect_grid_ms": EFFECT_GRID_MS,
        "xlights_version_stamp": XLIGHTS_VERSION_STAMP,
    }
    if preset_substitutions:
        payload["preset_substitutions"] = [list(item) for item in preset_substitutions]
    if dark_spans:
        payload["dark_spans"] = [list(span) for span in dark_spans]
    if palettes:
        payload["palettes"] = {
            section_id: palette.model_dump(mode="json") for section_id, palette in palettes.items()
        }
    if focal_roles:
        payload["focal_roles"] = dict(focal_roles)
    if locks:
        payload["locks"] = sorted(
            (_canonical_lock(lock.model_dump(mode="json")) for lock in locks),
            key=lambda lock: json.dumps(lock, sort_keys=True),
        )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _canonical_lock(lock: dict[str, Any]) -> dict[str, Any]:
    """A lock's dump with its fixtures and channels in sorted order."""
    return {
        key: sorted(value) if key in ("fixture_ids", "channels") else value
        for key, value in lock.items()
    }


def _plan_payload(plan: BaseModel) -> dict[str, Any]:
    """Dump the plan with canonical template ids.

    The renderer looks every template up in the registry, which resolves case,
    separators, display names and aliases, so only the canonical id counts.
    """
    payload = plan.model_dump(mode="json")
    if isinstance(plan, ChoreographyPlan):
        for dumped in payload["sections"]:
            for part in dumped["parts"]:
                part["template_id"] = _canonical_template_id(part["template_id"])
    return payload


def _canonical_template_id(key: str) -> str:
    return get_template(key).template.template_id
