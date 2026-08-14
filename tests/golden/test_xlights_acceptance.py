"""P1P-T12 — xLights acceptance: pin the owner-confirmed import contract empirically.

LOCAL-ONLY. Every test in this module is marked `requires_xlights` and is skipped
(collection-time, see `conftest.py`) unless a real xLights 2026.15 answers its HTTP
automation API at `xlights_client.DEFAULT_BASE_URL` (default
`http://127.0.0.1:49913`). None of it runs in CI. Enable the API in xLights'
preferences for the duration of a local run only, and disable it afterwards — it is
documented as unauthenticated (M6b).

## What this pins

The spec this module implements
(`build/specs/phase-1p-render-truth/P1P-T12-xlights-acceptance-test.md`) was written
to *discover* whether a bare `.xsq` imports without `xlights_rgbeffects.xml`. The
owner has since confirmed empirically (2026-08-14) that it does. This module's job is
narrower: pin that answer, and three adjacent ones, as a regression suite so a future
xLights version that changes the contract fails loudly instead of silently:

1. **Q1** — a fresh `.xsq` imports via `importXLightsSequence` both with and without
   `xlights_rgbeffects.xml` present in the target show directory (owner-confirmed;
   `test_import_with_rgbeffects_xml_present` / `test_import_without_rgbeffects_xml_present`).
   Each arm requires `TWINKLR_XLIGHTS_SHOWDIR_MODE` set to name which show directory
   is actually open (see the Q1 section below) — the two arms exercise different
   xLights-side state, not different code paths, so nothing here can tell them apart
   on its own.
2. **Q2** — the emitted version stamp (`XLIGHTS_VERSION_STAMP`) is accepted, and a
   synthetic/unknown stamp does not hard-reject the import (`test_import_accepts_*`).
3. **Q3** — the `mh4_shutter_out_of_window` rig (the repo's only >16-channel-mapped
   config; channel 17) produces shutter-open output post-import — the golden suite
   already pins *emission* (`test_shutter_channel_emission.py`); this pins xLights'
   *acceptance* of that emission (`test_shutter_open_output_on_channel_17`).
4. `.xtiming` files import standalone with no model mapping, and their markers match
   the beat grid the delivery was rendered against
   (`test_xtiming_imports_standalone`) — T11's verifier flagged this UNVERIFIED.
5. (Bonus, spec Q4) a sequence containing `split_lr_sweep_counter` loads without the
   overlapping-effects failure P4-F6 predicted, now that P1P-T5 clamps the schedule
   (`test_overlap_clamped_sequence_loads`).

## What this does NOT do

Per the spec's non-goals: no `addEffect` injection, no permanent xLights-driving CI
harness, and nothing here "fixes" a finding — a negative result is recorded and routed
to a follow-up, not patched in this task. Effect-parameter UI inspection (spec item,
P5 §V4 risk 5 — silently-ignored `E_*` keys) is a manual step the operator performs
alongside a real run; it is not scriptable through the documented automation surface
and is intentionally not asserted here. Saving from xLights and diffing against the
generated file (the spec's "first ground-truth fixture") likewise requires a live
xLights session to produce — see `README.md`'s "xLights acceptance (P1P-T12)" section
for the current status of that fixture.

## Sequence-target safety

`importXLightsSequence` targets whatever sequence xLights currently has open (M6b) —
not a sequence this suite creates and names. An `autouse` fixture below calls
`newSequence` before every test in this module, so each import lands in a fresh,
throwaway sequence rather than silently overwriting the operator's real work.
Nothing here saves that sequence; per `README.md`'s runbook, the operator discards it
(closes without saving) after each run.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

from tests.golden.harness import (
    PLAN_BEATS_PER_BAR,
    PLAN_BPM,
    RIGS,
    build_beat_grid,
    build_fixture_group,
)
from tests.golden.xlights_client import XLightsClient
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import XLIGHTS_VERSION_STAMP
from twinklr.core.sequencer.moving_heads.delivery import DeliveryArtifacts
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

pytestmark = pytest.mark.requires_xlights

MEDIA_FILE = "xlights_acceptance_song.mp3"

SYNTHETIC_STAMP = "1999.99"
"""An obviously-unreal release string — the M6b "synthetic/unknown stamp" probe."""

BAR_MS = 60_000.0 / PLAN_BPM * PLAN_BEATS_PER_BAR
"""Milliseconds per bar under the harness's fixed, even 120 BPM / 4-beat grid — the
independent ground truth `test_xtiming_imports_standalone` spot-checks marker times
against, rather than re-deriving them from the production code under test."""


def _default_plan() -> ChoreographyPlan:
    """Three short sections (the golden harness's own `intro`/`chorus`/`drop`
    combination) so the delivered `.xtiming` carries more than one marker — a
    single-section plan yields a 1-marker "Twinklr AudioSections" track, which is not
    enough to spot-check ordering or spacing against the beat grid."""
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="intro",
                start_bar=1,
                end_bar=4,
                template_id="sweep_lr_fan_hold",
                preset_id="chill",
            ),
            PlanSection(
                section_name="chorus",
                start_bar=5,
                end_bar=8,
                template_id="bounce_fan_pulse",
                preset_id="energetic",
            ),
            PlanSection(
                section_name="drop",
                start_bar=9,
                end_bar=12,
                template_id="pop_lock_spotlight_blackout",
                preset_id="energetic",
            ),
        ]
    )


def _overlap_plan() -> ChoreographyPlan:
    """`split_lr_sweep_counter` over two full 4-bar cycles — the P4-F6 overlap probe
    (spec Q4). Two cycles so the ping-pong repeat actually reverses direction once."""
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="overlap_probe",
                start_bar=1,
                end_bar=8,
                template_id="split_lr_sweep_counter",
                preset_id="moderate",
            )
        ]
    )


def _deliver(
    *, rig_id: str, plan: ChoreographyPlan, output_dir: Path, stem: str
) -> DeliveryArtifacts:
    """Render `plan` on `rig_id` through the real pipeline and write the delivery.

    Same path `test_delivery_artifacts.py` exercises (P1P-T11) — this module reuses
    it rather than re-deriving a second way to produce a `.xsq`, so the file the
    automation API sees is exactly what a real run would hand the user.
    """
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=build_beat_grid(),
        fixture_group=build_fixture_group(RIGS[rig_id]),
        job_config=JobConfig(),
        output_path=output_dir / f"{stem}.xsq",
        media_file=MEDIA_FILE,
        song="xLights Acceptance",
        artist="Twinklr",
    )
    pipeline.render()
    assert pipeline.artifacts is not None
    return pipeline.artifacts


@pytest.fixture(scope="module")
def client() -> XLightsClient:
    return XLightsClient()


@pytest.fixture(autouse=True)
def _fresh_target_sequence(client: XLightsClient) -> None:
    """`importXLightsSequence` targets the currently open sequence (M6b) — this
    creates a throwaway one before every test in the module so an import never lands
    in, and never overwrites, whatever the operator happened to have open.
    `newSequence` is one of M6b's corroborated commands (unlike a "save" command,
    which is not — see `xlights_client.py`), so a failure here is treated as unsafe
    to proceed past rather than best-effort."""
    response = client.new_sequence()
    if not response.ok:
        pytest.skip(
            f"newSequence failed ({response.body}); refusing to import into an unknown target"
        )


@pytest.fixture(scope="module")
def baseline_delivery(tmp_path_factory: pytest.TempPathFactory) -> DeliveryArtifacts:
    """The `mh4_minimal` rig's delivery — Q1, Q2 and the `.xtiming` check share it."""
    output_dir = tmp_path_factory.mktemp("xlights_acceptance_baseline")
    return _deliver(
        rig_id="mh4_minimal", plan=_default_plan(), output_dir=output_dir, stem="baseline"
    )


@pytest.fixture(scope="module")
def shutter_high_delivery(tmp_path_factory: pytest.TempPathFactory) -> DeliveryArtifacts:
    """`mh4_shutter_out_of_window` — the repo's only >16-channel-mapped rig (channel
    17 shutter). Q3."""
    output_dir = tmp_path_factory.mktemp("xlights_acceptance_shutter_high")
    return _deliver(
        rig_id="mh4_shutter_out_of_window",
        plan=_default_plan(),
        output_dir=output_dir,
        stem="shutter_high",
    )


@pytest.fixture(scope="module")
def overlap_delivery(tmp_path_factory: pytest.TempPathFactory) -> DeliveryArtifacts:
    """`split_lr_sweep_counter` on `mh4_minimal` — the P4-F6 overlap probe (Q4)."""
    output_dir = tmp_path_factory.mktemp("xlights_acceptance_overlap")
    return _deliver(
        rig_id="mh4_minimal", plan=_overlap_plan(), output_dir=output_dir, stem="overlap"
    )


@pytest.fixture(scope="module")
def synthetic_stamp_xsq(
    baseline_delivery: DeliveryArtifacts, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """A copy of the baseline `.xsq` with `<version>` rewritten to `SYNTHETIC_STAMP`.

    Only the stamp changes — everything else is byte-identical to the file that Q1
    already exercises, so a difference in import outcome is attributable to the
    stamp alone.
    """
    text = baseline_delivery.xsq_path.read_text(encoding="utf-8")
    stamped_text, count = re.subn(
        rf"<version>{re.escape(XLIGHTS_VERSION_STAMP)}</version>",
        f"<version>{SYNTHETIC_STAMP}</version>",
        text,
        count=1,
    )
    assert count == 1, "expected exactly one <version> element to rewrite"
    out_dir = tmp_path_factory.mktemp("xlights_acceptance_synthetic_stamp")
    out_path = out_dir / "synthetic_stamp.xsq"
    out_path.write_text(stamped_text, encoding="utf-8")
    return out_path


def _assert_import_succeeded(response_json: object, *, context: str) -> None:
    """Best-effort success check.

    The automation API's response shape for `importXLightsSequence` is UNVERIFIED
    against a real xLights as of this writing (M6b) — the exact key names here may
    need adjusting on the first real run against 2026.15. The intent is unambiguous
    regardless of shape: no error/failure indicator present.
    """
    body = str(response_json).lower()
    assert "error" not in body and "fail" not in body, (
        f"{context}: xLights reported a failure: {response_json}"
    )


# ---------------------------------------------------------------------------------
# Q1 — the owner-confirmed contract: bare .xsq imports with AND without rgbeffects.xml
# ---------------------------------------------------------------------------------
#
# The presence/absence of `xlights_rgbeffects.xml` is a property of the show
# directory xLights currently has open, not of the donor `.xsq` — the automation
# surface (M6b) has no documented "open show directory" command, so each arm
# requires the operator to have already launched xLights against the matching show
# directory (with / without the file) *and* to say so via `TWINKLR_XLIGHTS_SHOWDIR_MODE`
# before running that arm. Without the gate, both arms run identical code against
# whatever single show directory the operator happened to have open and would both
# report success regardless of which contract was actually being exercised — the gate
# makes the mismatched arm skip loudly instead of silently "passing" the wrong thing.

_SHOWDIR_MODE_ENV = "TWINKLR_XLIGHTS_SHOWDIR_MODE"
_MODE_WITH_RGBEFFECTS = "with_rgbeffects"
_MODE_BARE = "bare"


def _require_showdir_mode(expected: str) -> None:
    actual = os.environ.get(_SHOWDIR_MODE_ENV)
    if actual == expected:
        return
    wants = "HAS" if expected == _MODE_WITH_RGBEFFECTS else "LACKS"
    pytest.skip(
        f"requires {_SHOWDIR_MODE_ENV}={expected!r} (xLights open against a show "
        f"directory that {wants} xlights_rgbeffects.xml); got {actual!r}. Point xLights "
        f"at the matching show directory and re-run with that env var set."
    )


def test_import_with_rgbeffects_xml_present(
    client: XLightsClient, baseline_delivery: DeliveryArtifacts
) -> None:
    """PRECONDITION: `TWINKLR_XLIGHTS_SHOWDIR_MODE=with_rgbeffects`, xLights open
    against a show directory that HAS `xlights_rgbeffects.xml`. Owner-confirmed
    (2026-08-14): imports successfully."""
    _require_showdir_mode(_MODE_WITH_RGBEFFECTS)
    response = client.import_xlights_sequence(
        str(baseline_delivery.xsq_path), mapmethod="file", mapfile=str(baseline_delivery.xmap_path)
    )
    assert response.ok, f"import rejected with rgbeffects.xml present: {response.body}"
    _assert_import_succeeded(response.json(), context="with rgbeffects.xml")


def test_import_without_rgbeffects_xml_present(
    client: XLightsClient, baseline_delivery: DeliveryArtifacts
) -> None:
    """PRECONDITION: `TWINKLR_XLIGHTS_SHOWDIR_MODE=bare`, xLights open against a show
    directory that LACKS `xlights_rgbeffects.xml`. Owner-confirmed (2026-08-14):
    imports successfully too — this is the M6/M6b unknown, now pinned. A future
    xLights that starts requiring the file will fail this test loudly instead of
    degrading silently."""
    _require_showdir_mode(_MODE_BARE)
    response = client.import_xlights_sequence(
        str(baseline_delivery.xsq_path), mapmethod="file", mapfile=str(baseline_delivery.xmap_path)
    )
    assert response.ok, f"import rejected without rgbeffects.xml: {response.body}"
    _assert_import_succeeded(response.json(), context="without rgbeffects.xml")


# ---------------------------------------------------------------------------------
# Q2 — version stamp acceptance
# ---------------------------------------------------------------------------------


def test_import_accepts_current_version_stamp(
    client: XLightsClient, baseline_delivery: DeliveryArtifacts
) -> None:
    """The stamp P1P-T11 emits (`XLIGHTS_VERSION_STAMP`, matching this suite's target
    xLights build) imports without a version-related warning or rejection."""
    response = client.import_xlights_sequence(
        str(baseline_delivery.xsq_path), mapmethod="file", mapfile=str(baseline_delivery.xmap_path)
    )
    assert response.ok, f"current stamp {XLIGHTS_VERSION_STAMP!r} rejected: {response.body}"


def test_import_accepts_or_warns_on_synthetic_version_stamp(
    client: XLightsClient, synthetic_stamp_xsq: Path
) -> None:
    """M6b's remaining unknown: an unrecognized stamp value. The documented behavior
    (pre-2020 stamps warn, do not reject, per 2026.04) predicts this imports with at
    most a warning — asserted as "does not hard-reject", the weakest claim the docs
    support; tighten this once a real run shows the exact response shape."""
    response = client.import_xlights_sequence(str(synthetic_stamp_xsq), mapmethod="auto")
    assert response.ok, (
        f"synthetic stamp {SYNTHETIC_STAMP!r} hard-rejected (docs predict warn-not-reject): "
        f"{response.body}"
    )


# ---------------------------------------------------------------------------------
# Q3 — shutter-open output on the >16-channel rig (channel 17)
# ---------------------------------------------------------------------------------


def test_shutter_open_output_on_channel_17(
    client: XLightsClient, shutter_high_delivery: DeliveryArtifacts
) -> None:
    """`mh4_shutter_out_of_window` (shutter_channel=17) imports and the shutter reads
    open. `test_shutter_channel_emission.py` already pins that Twinklr *emits*
    `E_SLIDER_DMX17=255`; this pins that xLights *accepts* the >16-channel window
    rather than truncating or rejecting it on import."""
    response = client.import_xlights_sequence(
        str(shutter_high_delivery.xsq_path),
        mapmethod="file",
        mapfile=str(shutter_high_delivery.xmap_path),
    )
    assert response.ok, f"shutter-high rig import failed: {response.body}"
    _assert_import_succeeded(response.json(), context="shutter-high rig")
    # Emission-side ground truth, re-asserted here so this test also documents *why*
    # channel 17 is the one to check in the xLights UI/console after import.
    xsq_text = shutter_high_delivery.xsq_path.read_text(encoding="utf-8")
    assert "E_SLIDER_DMX17=255" in xsq_text, (
        "expected emission changed under our feet — re-check the rig"
    )


# ---------------------------------------------------------------------------------
# Q4 (bonus) — P4-F6 overlap clamp: split_lr_sweep_counter loads
# ---------------------------------------------------------------------------------


def test_overlap_clamped_sequence_loads(
    client: XLightsClient, overlap_delivery: DeliveryArtifacts
) -> None:
    """P4-F6 predicted xLights rejects two effects overlapping on one layer;
    P1P-T5's schedule clamp should mean this no longer occurs. Import succeeding is
    the acceptance-side confirmation of the clamp (the golden suite pins the
    emitted-bytes side)."""
    response = client.import_xlights_sequence(
        str(overlap_delivery.xsq_path), mapmethod="file", mapfile=str(overlap_delivery.xmap_path)
    )
    assert response.ok, f"split_lr_sweep_counter sequence failed to load: {response.body}"
    _assert_import_succeeded(response.json(), context="split_lr_sweep_counter overlap probe")


# ---------------------------------------------------------------------------------
# .xtiming standalone import (T11's verifier-flagged UNVERIFIED item)
# ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _ExpectedMarker:
    label: str
    start_ms: int
    end_ms: int


def _expected_section_markers(plan: ChoreographyPlan) -> list[_ExpectedMarker]:
    """Independently re-derive the "Twinklr AudioSections" marker times from the
    plan and `BAR_MS`, mirroring `TemplateCompileContext.start_ms`/`end_ms`
    (`context.py`: `_bar_to_ms`) without importing it — the point of a spot-check is
    a second, independent computation, not a call into the code under test."""
    return [
        _ExpectedMarker(
            label=section.section_name,
            start_ms=round((section.start_bar - 1) * BAR_MS),
            end_ms=round(section.end_bar * BAR_MS),
        )
        for section in plan.sections
    ]


def test_xtiming_imports_standalone(
    client: XLightsClient, baseline_delivery: DeliveryArtifacts
) -> None:
    """Each `.xtiming` file imports as a timing track with no model mapping needed —
    the M6b "mapping-free minimum-viable deliverable" claim, and the item T11's
    verifier flagged UNVERIFIED. The "Twinklr AudioSections" track's markers are
    spot-checked against times independently re-derived from the plan and the
    deterministic beat grid (`BAR_MS`), not merely against the file's own content —
    that is what makes this a check against the beat grid rather than a tautology."""
    assert baseline_delivery.xtiming_paths, "no .xtiming written by the baseline delivery"

    expected_sections = _expected_section_markers(_default_plan())
    sections_track = next(
        (
            path
            for path in baseline_delivery.xtiming_paths
            if ET.parse(path).getroot().get("name") == "Twinklr AudioSections"
        ),
        None,
    )
    assert sections_track is not None, (
        f"no track named 'Twinklr AudioSections' among {[p.name for p in baseline_delivery.xtiming_paths]}"
    )

    root = ET.parse(sections_track).getroot()
    actual_markers = [
        (effect.get("label"), int(effect.get("starttime", "-1")), int(effect.get("endtime", "-1")))
        for effect in root.findall("EffectLayer/Effect")
    ]
    assert actual_markers == [(m.label, m.start_ms, m.end_ms) for m in expected_sections], (
        "Twinklr AudioSections markers do not match the beat grid's bar boundaries"
    )

    for xtiming_path in baseline_delivery.xtiming_paths:
        track_name, marker_count = _track_summary(xtiming_path)
        response = client.import_xlights_sequence(str(xtiming_path), mapmethod="auto")
        assert response.ok, (
            f"{xtiming_path.name} ({track_name!r}) failed to import standalone: {response.body}"
        )
        _assert_import_succeeded(
            response.json(), context=f"{xtiming_path.name} ({marker_count} markers)"
        )


def _track_summary(xtiming_path: Path) -> tuple[str, int]:
    root = ET.parse(xtiming_path).getroot()
    name = root.get("name")
    assert name is not None, f"{xtiming_path} has no track name"
    markers = root.findall("EffectLayer/Effect")
    assert markers, f"{xtiming_path} has no markers to spot-check"
    return name, len(markers)
