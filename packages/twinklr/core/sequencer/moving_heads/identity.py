"""Functional identity of a moving-head render.

`render_fingerprint` hashes canonical JSON of everything that decides rendered output
and nothing that does not: diagnostic wording, wall-clock time and output paths are
left out, and neither mapping key order, the order templates are supplied in, nor the
spelling a plan uses for a template counts.
"""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import MHRenderPolicy, TransitionConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, XLIGHTS_VERSION_STAMP
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from pydantic import BaseModel

LEGACY_BACKEND_ID = "xlights_dmx"
"""The backend the legacy renderer writes: xLights DMX effects in an `.xsq`."""

LEGACY_RENDERER_REVISION = "1"
"""Bumped by hand in the commit that intentionally changes legacy rendering."""

PHYSICAL_RENDERER_REVISION = "1"
"""Bumped by hand in the commit that intentionally changes physical rendering; the
render identity also carries the frame encoder's own version."""


def render_fingerprint(
    *,
    plan: BaseModel,
    beat_grid: BeatGrid,
    fixtures: FixtureGroup,
    templates: Sequence[TemplateDoc],
    policy: MHRenderPolicy,
    transitions: TransitionConfig | None,
    backend_id: str,
    renderer_revision: str,
    seed: int | None = None,
    phase_map: BaseModel | None = None,
    locks: Sequence[BaseModel] = (),
) -> str:
    """Hash the functional inputs of a render.

    Args:
        plan: The plan to render.
        beat_grid: The grid the plan is placed on.
        fixtures: The rig; fixture order counts.
        templates: Template documents, presets included; their order does not count.
        policy: The moving-head render policy.
        transitions: Transition settings, which change legacy segments; None for a
            renderer that ignores them.
        backend_id: Output backend identity, e.g. `LEGACY_BACKEND_ID`.
        renderer_revision: Renderer revision, e.g. `LEGACY_RENDERER_REVISION`.
        seed: Seed of any seeded choice the render depends on.
        phase_map: A typed boundary map, when the renderer takes one.
        locks: Render locks the output must honor; hashed only when there are any, so
            a render without locks keeps its earlier identity. Neither the order of the
            locks nor of their fixtures and channels counts.

    Returns:
        A 64-character lowercase SHA-256 hex digest.
    """
    payload = {
        "plan": _plan_payload(plan),
        "beat_grid": beat_grid.model_dump(mode="json"),
        "fixtures": fixtures.model_dump(mode="json"),
        "templates": sorted(
            (doc.model_dump(mode="json") for doc in templates),
            key=lambda doc: doc["template"]["template_id"],
        ),
        "policy": policy.model_dump(mode="json"),
        "transitions": transitions.model_dump(mode="json") if transitions is not None else None,
        "backend_id": backend_id,
        "renderer_revision": renderer_revision,
        "seed": seed,
        "phase_map": phase_map.model_dump(mode="json") if phase_map is not None else None,
        "effect_grid_ms": EFFECT_GRID_MS,
        "xlights_version_stamp": XLIGHTS_VERSION_STAMP,
    }
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
    """Dump the plan with canonical template ids and each section's legacy-intent flag.

    `PlanSection` keeps that flag out of `model_dump`, yet the renderer ignores a
    section's intent when it is set, so it is functional. The renderer looks every
    template up in the registry, which resolves case, separators, display names and
    aliases, so only the canonical id counts.
    """
    payload = plan.model_dump(mode="json")
    if isinstance(plan, ChoreographyPlan):
        for dumped, section in zip(payload["sections"], plan.sections, strict=True):
            dumped["legacy_intent_omitted"] = section.legacy_intent_omitted
            for selection in [dumped, *(dumped["segments"] or [])]:
                if selection["template_id"]:
                    selection["template_id"] = _canonical_template_id(selection["template_id"])
    return payload


def _canonical_template_id(key: str) -> str:
    return get_template(key).template.template_id
