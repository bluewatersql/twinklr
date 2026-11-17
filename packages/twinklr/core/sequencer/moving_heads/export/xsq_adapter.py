"""XSQ output of the moving-head render: the layout model check and one constant DMX
effect request per coalesced frame run."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import accumulate
import logging
from typing import TYPE_CHECKING

from twinklr.core.formats.xlights.sequence.emission import (
    EmissionRequest,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.formats.xlights.sequence.trace import (
    MovingHeadEmissionTrace,
)
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import (
    DmxSettingsBuilder,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    OutputError,
    segment_frame_span,
)

if TYPE_CHECKING:
    from twinklr.core.config.fixtures.instances import FixtureInstance
    from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
    from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
    from twinklr.core.sequencer.moving_heads.export.frame_encoder import FrameRun

logger = logging.getLogger(__name__)


DMX_DISPLAY_AS_PREFIX = "dmx"
"""Lower-cased `DisplayAs` prefix of an xLights DMX model; the display pipeline treats
the same prefix as DMX (`formats/xlights/layout/choreography.py::_dmx_model_names`).
xLights 2026.19 writes `DmxMovingHeadAdv` and `DmxGeneral` (observed 2026-11-14)."""

SINGLE_COLOR_STRING_TYPE_PREFIX = "single color"
"""Lower-cased `StringType` prefix accepted for the channel mapping: one channel per
node, as the layout profiler reads it
(`profiling/layout/profiler.py::_infer_channels_per_node`). xLights 2026.19 writes
`Single Color White` on DMX models (observed 2026-11-14); other single-color spellings
are accepted but unobserved, and a model without a `StringType` is accepted."""


def check_models(fixtures: Sequence[FixtureInstance], models: Sequence[Model]) -> None:
    """Refuse a fixture whose xLights model the channel mapping cannot drive.

    The mapping writes model-relative DMX channels 1..footprint on every frame, so the
    fixture's model must be in the layout, a DMX model (`DisplayAs` prefix
    `DMX_DISPLAY_AS_PREFIX`), single color when the layout records a `StringType`
    (`SINGLE_COLOR_STRING_TYPE_PREFIX`), and declare a channel count of at least the
    profile's footprint: `DmxChannelCount`, as xLights 2026.19 writes it, else the
    unverified `parm1` fallback (`Model.dmx_channel_count`). A missing or non-numeric
    channel count is refused, never assumed; diagnostics name the attribute read.

    Args:
        fixtures: The rig's fixtures, each with a physical profile.
        models: The xLights layout's models.

    Raises:
        OutputError: With code `unsupported_backend_channel`, naming each
            refused fixture, model and item.
    """
    by_name = {model.name: model for model in models}
    refused: dict[str, str] = {}
    for fixture in fixtures:
        name = fixture.xlights_model_name
        model = by_name.get(name)
        profile = fixture.config.physical_profile
        if model is None:
            refused[fixture.fixture_id] = f"model {name!r} is not in the xLights layout"
            continue
        display_as = model.DisplayAs or ""
        string_type = model.StringType
        declared = model.dmx_channel_count()
        if not display_as.lower().startswith(DMX_DISPLAY_AS_PREFIX):
            reason = f"model {name!r} is DisplayAs={display_as!r}, not DMX"
        elif string_type is not None and not string_type.lower().startswith(
            SINGLE_COLOR_STRING_TYPE_PREFIX
        ):
            reason = f"model {name!r} has StringType={string_type!r}, not single color"
        elif declared is None:
            reason = f"model {name!r} declares no channel count (DmxChannelCount or parm1)"
        elif not declared[1].isdigit():
            reason = f"model {name!r} has {declared[0]}={declared[1]!r}, not a channel count"
        elif profile is not None and int(declared[1]) < profile.footprint:
            reason = (
                f"model {name!r} has {int(declared[1])} channels by {declared[0]}; profile "
                f"{profile.profile_id!r} writes channels 1-{profile.footprint}"
            )
        else:
            continue
        refused[fixture.fixture_id] = reason
    if refused:
        raise OutputError(
            MHDiagnostic(
                code="unsupported_backend_channel",
                severity="error",
                message="Moving-head output needs single-color DMX models wide enough for their "
                "profiles: "
                + "; ".join(f"{fixture_id}: {reason}" for fixture_id, reason in refused.items()),
                fixture_id=next(iter(refused)) if len(refused) == 1 else None,
                action="rejected",
            )
        )


def run_requests(
    runs: Sequence[FrameRun],
    segments: Sequence[FixtureSegment],
    targets: Mapping[str, str],
    *,
    logical_layer: int = 0,
) -> tuple[EmissionRequest, ...]:
    """Convert frame runs into one constant DMX effect request each.

    Every run targets its own fixture's
    model; moving-head output is never grouped. Runs are already frame-aligned, so the
    emission session's quantization leaves them unchanged; a misaligned run is refused
    rather than shifted a second time. A run's trace sources are the segments whose
    frame span overlaps it, earliest first; the earliest represents the run.

    Args:
        runs: Coalesced frame runs.
        segments: The segments the runs were encoded from.
        targets: Fixture id to xLights model name.
        logical_layer: Logical layer for every request.

    Raises:
        ValueError: If a run is not frame-aligned or its fixture has no model.
    """
    # Per fixture: spans ordered by start, and the furthest end reached by each prefix,
    # so a run's overlapping segments are found by bisection, not by a full scan.
    spans: dict[str, list[tuple[int, int, FixtureSegment]]] = defaultdict(list)
    for segment in segments:
        spans[segment.fixture_id].append((*segment_frame_span(segment), segment))
    starts: dict[str, list[int]] = {}
    reach: dict[str, list[int]] = {}
    for fixture_id, fixture_spans in spans.items():
        fixture_spans.sort(key=lambda item: (item[0], item[2].segment_id, item[2].step_id))
        starts[fixture_id] = [start for start, _, _ in fixture_spans]
        reach[fixture_id] = list(accumulate((end for _, end, _ in fixture_spans), max))

    requests: list[EmissionRequest] = []
    for run in runs:
        fixture_id, start_ms, end_ms = run.frame.fixture_id, run.start_ms, run.end_ms
        if start_ms % EFFECT_GRID_MS or end_ms % EFFECT_GRID_MS or end_ms <= start_ms:
            raise ValueError(
                f"{fixture_id} run {start_ms}-{end_ms} ms is not frame-aligned to the "
                f"{EFFECT_GRID_MS} ms grid"
            )
        target = targets.get(fixture_id)
        if not target:
            raise ValueError(f"no xLights model for fixture {fixture_id}")
        sources: list[FixtureSegment] = []
        candidate = bisect_left(starts.get(fixture_id, []), end_ms) - 1
        while candidate >= 0 and reach[fixture_id][candidate] > start_ms:
            _, span_end, segment = spans[fixture_id][candidate]
            if span_end > start_ms:
                sources.append(segment)
            candidate -= 1
        sources.reverse()
        representative = sources[0] if sources else None
        trace: MovingHeadEmissionTrace = {
            "backend": "moving_head",
            "event_id": f"mh:{target}:{start_ms}:{end_ms}:{logical_layer}",
            "section_id": representative.section_id if representative else "",
            "lane": "TRANSITION" if logical_layer else "BASE",
            "group_id": target,
            "template_id": representative.template_id if representative else "",
            "sources": [
                {
                    "fixture_id": item.fixture_id,
                    "segment_id": item.segment_id,
                    "step_id": item.step_id,
                }
                for item in sources
            ],
        }
        requests.append(
            EmissionRequest(
                target=target,
                effect="DMX",
                settings=DmxSettingsBuilder.build_frame_settings(run.frame),
                palette=None,
                start_ms=start_ms,
                end_ms=end_ms,
                logical_layer=logical_layer,
                label=representative.metatag if representative else None,
                trace=trace,
            )
        )
    return tuple(requests)
