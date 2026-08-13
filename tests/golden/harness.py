"""Reusable render harness for the golden suite.

Renders a fixed, LLM-free choreography plan through the *real* `RenderingPipeline`
(no mocking of `compile_template` — the compiler, handlers, curves and exporter all
execute) and exposes the emitted per-effect DMX settings strings so tests can pin them.

Everything here is deterministic: fixed BPM, fixed bar count, fixed template/preset ids,
no timestamps, no UUIDs, and a stable sort applied before any golden text is produced.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment

GOLDEN_ROOT = Path(__file__).resolve().parent

# --- Deterministic render inputs -------------------------------------------------
#
# P1P-T2 will deliver the tracked rig configs and plan fixtures for the phase. Until
# it lands, the golden suite owns the minimal deterministic set it needs; T2 is
# expected to *extend* these (add rigs / sections), not replace the harness.

PLAN_BPM = 120.0
PLAN_TOTAL_BARS = 8
PLAN_BEATS_PER_BAR = 4

# `TemplateCompileContext.n_samples` is not settable through RenderingPipeline, so the
# goldens depend on its default. `test_settings_golden.py` asserts this value so a
# change to the default surfaces as an explicit failure telling you to regenerate,
# rather than as unexplained golden churn.
EXPECTED_N_SAMPLES = 64


@dataclass(frozen=True)
class RigSpec:
    """A tracked fixture rig the golden suite renders against."""

    rig_id: str
    description: str
    fixture_count: int
    pan_channel: int
    tilt_channel: int
    dimmer_channel: int
    shutter_channel: int | None = None
    color_channel: int | None = None
    gobo_channel: int | None = None


RIGS: dict[str, RigSpec] = {
    "mh4_minimal": RigSpec(
        rig_id="mh4_minimal",
        description="4 heads, pan/tilt/dimmer only — the shape used by the repo's own tests",
        fixture_count=4,
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
    ),
    "mh4_shutter_in_window": RigSpec(
        rig_id="mh4_shutter_in_window",
        description="4 heads with shutter/colour/gobo mapped inside the emitted 1-16 window",
        fixture_count=4,
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=6,
        color_channel=7,
        gobo_channel=8,
    ),
    "mh4_shutter_out_of_window": RigSpec(
        rig_id="mh4_shutter_out_of_window",
        description=(
            "4 heads with shutter/colour above channel 16 — mirrors the only fixture "
            "configuration tracked in the repository today "
            "(tests/unit/config/test_fixtures.py, shutter_channel=17)"
        ),
        fixture_count=4,
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=17,
        color_channel=18,
    ),
}


def build_fixture_group(rig: RigSpec) -> FixtureGroup:
    """Build the FixtureGroup for a rig. Pure function of the spec — no I/O."""
    group = FixtureGroup(
        group_id="MOVING_HEADS",
        xlights_group="GROUP - MOVING HEADS",
    )
    for index in range(rig.fixture_count):
        fixture_id = f"MH{index + 1}"
        config = FixtureConfig(
            fixture_id=fixture_id,
            dmx_start_address=1 + index * 16,
            channel_count=16,
            dmx_mapping=DmxMapping(
                pan_channel=rig.pan_channel,
                tilt_channel=rig.tilt_channel,
                dimmer_channel=rig.dimmer_channel,
                shutter_channel=rig.shutter_channel,
                color_channel=rig.color_channel,
                gobo_channel=rig.gobo_channel,
            ),
        )
        group.add_fixture(
            FixtureInstance(
                fixture_id=fixture_id,
                config=config,
                xlights_model_name=f"Dmx {fixture_id}",
            )
        )
    return group


def build_plan() -> ChoreographyPlan:
    """The deterministic plan fixture: two 4-bar sections, fixed templates and presets."""
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
        ]
    )


def build_beat_grid() -> BeatGrid:
    return BeatGrid.from_tempo(
        tempo_bpm=PLAN_BPM,
        total_bars=PLAN_TOTAL_BARS,
        beats_per_bar=PLAN_BEATS_PER_BAR,
    )


@dataclass(frozen=True)
class EmittedEffect:
    """One rendered segment together with the settings string it emits."""

    section_id: str
    fixture_id: str
    segment_id: str
    step_id: str
    template_id: str
    preset_id: str | None
    t0_ms: int
    t1_ms: int
    settings: str

    @property
    def sort_key(self) -> tuple[int, str, str, str, str]:
        return (self.t0_ms, self.section_id, self.fixture_id, self.segment_id, self.step_id)

    @property
    def header(self) -> str:
        return (
            f"## fixture={self.fixture_id} segment={self.segment_id} step={self.step_id} "
            f"t0={self.t0_ms} t1={self.t1_ms} "
            f"template={self.template_id} preset={self.preset_id or '-'}"
        )


@dataclass(frozen=True)
class RenderResult:
    """The output of one harness render."""

    rig: RigSpec
    segments: list[FixtureSegment]
    effects: list[EmittedEffect]
    xsq_path: Path | None

    def sections(self) -> list[str]:
        """Section ids in first-emission order."""
        seen: list[str] = []
        for effect in self.effects:
            if effect.section_id not in seen:
                seen.append(effect.section_id)
        return seen

    def for_section(self, section_id: str) -> list[EmittedEffect]:
        return [effect for effect in self.effects if effect.section_id == section_id]


def render_rig(rig: RigSpec, *, output_path: Path | None = None) -> RenderResult:
    """Render the deterministic plan against `rig` through the real pipeline.

    Args:
        rig: Rig to render.
        output_path: If given, the pipeline also exports a `.xsq` there.

    Returns:
        RenderResult with segments sorted deterministically and their settings strings.
    """
    fixture_group = build_fixture_group(rig)
    pipeline = RenderingPipeline(
        choreography_plan=build_plan(),
        beat_grid=build_beat_grid(),
        fixture_group=fixture_group,
        job_config=JobConfig(),
        output_path=output_path,
    )
    segments = pipeline.render()

    effects: list[EmittedEffect] = []
    for segment in segments:
        fixture = _require_fixture(fixture_group, segment.fixture_id)
        effects.append(
            EmittedEffect(
                section_id=segment.section_id,
                fixture_id=segment.fixture_id,
                segment_id=segment.segment_id,
                step_id=segment.step_id,
                template_id=segment.template_id,
                preset_id=segment.preset_id,
                t0_ms=segment.t0_ms,
                t1_ms=segment.t1_ms,
                settings=DmxSettingsBuilder(fixture).build_settings_string(segment),
            )
        )
    effects.sort(key=lambda effect: effect.sort_key)

    return RenderResult(rig=rig, segments=segments, effects=effects, xsq_path=output_path)


def render_single_section(
    rig: RigSpec, *, template_id: str, preset_id: str | None
) -> list[EmittedEffect]:
    """Render one 4-bar section with an explicit template/preset, for A/B pins.

    Used by the preset-sensitivity pin, where the whole point is to vary one input and
    compare the emitted settings strings.
    """
    fixture_group = build_fixture_group(rig)
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="section",
                    start_bar=1,
                    end_bar=4,
                    template_id=template_id,
                    preset_id=preset_id,
                )
            ]
        ),
        beat_grid=BeatGrid.from_tempo(
            tempo_bpm=PLAN_BPM, total_bars=4, beats_per_bar=PLAN_BEATS_PER_BAR
        ),
        fixture_group=fixture_group,
        job_config=JobConfig(),
    )
    effects = [
        EmittedEffect(
            section_id=segment.section_id,
            fixture_id=segment.fixture_id,
            segment_id=segment.segment_id,
            step_id=segment.step_id,
            template_id=segment.template_id,
            preset_id=segment.preset_id,
            t0_ms=segment.t0_ms,
            t1_ms=segment.t1_ms,
            settings=DmxSettingsBuilder(
                _require_fixture(fixture_group, segment.fixture_id)
            ).build_settings_string(segment),
        )
        for segment in pipeline.render()
    ]
    effects.sort(key=lambda effect: effect.sort_key)
    return effects


def _require_fixture(fixture_group: FixtureGroup, fixture_id: str) -> FixtureInstance:
    fixture = fixture_group.get_fixture(fixture_id)
    if fixture is None:  # pragma: no cover - would mean the rig spec is inconsistent
        raise AssertionError(f"no fixture {fixture_id} in group")
    return fixture


def actual_n_samples() -> int:
    """The `n_samples` the pipeline's compile context actually uses."""
    field = TemplateCompileContext.model_fields["n_samples"]
    return int(field.default)


# --- Golden file I/O -------------------------------------------------------------

_GOLDEN_BANNER = (
    "# GOLDEN — DO NOT HAND-EDIT. Regenerate with:\n"
    "#   uv run pytest tests/golden --regen-goldens -q\n"
    "# (or TWINKLR_REGEN_GOLDENS=1 uv run pytest tests/golden -q)\n"
    "#\n"
    "# These pins encode the render's CURRENT behavior at the P1P baseline, defects\n"
    "# included. They are a diff surface for Lane R, not a statement of desired output.\n"
    "# Known-defective behavior visible below (fixed in P1P-T3..T6, not here):\n"
    "#   P4-F3  every channel 1..16 is emitted, unchoreographed ones zero-filled --\n"
    "#          so E_SLIDER_DMX<n>=0 here means 'zero-filled', not 'commanded to 0'\n"
    "#   P4-F1  movement curves can be identical across preset_id (see\n"
    "#          test_preset_id_does_not_change_movement_curve)\n"
    "#   P4-F10 value-curve points are written at 2-decimal resolution\n"
    "#   NEW    every transition segment emits an all-zero settings string with no\n"
    "#          value curves at all -- see test_transition_segments_emit_all_zero\n"
)


def golden_path(rig_id: str, section_id: str) -> Path:
    return GOLDEN_ROOT / rig_id / f"{section_id}.settings.txt"


def render_golden_text(result: RenderResult, section_id: str) -> str:
    """Serialize one section of a render into golden text.

    Deterministic by construction: effects are pre-sorted and each settings string is
    written verbatim, so a diff shows exactly which channel or curve point moved.
    """
    lines = [
        _GOLDEN_BANNER,
        f"# rig={result.rig.rig_id} section={section_id}",
        f"# {result.rig.description}",
        f"# plan: {PLAN_BPM:.1f} bpm, {PLAN_TOTAL_BARS} bars, n_samples={actual_n_samples()}",
        "",
    ]
    for effect in result.for_section(section_id):
        lines.append(effect.header)
        lines.append(effect.settings)
        lines.append("")
    return "\n".join(lines)


def regen_requested(pytestconfig: object | None = None) -> bool:
    """True when goldens should be rewritten rather than compared."""
    if os.environ.get("TWINKLR_REGEN_GOLDENS", "").strip() not in {"", "0", "false", "False"}:
        return True
    if pytestconfig is None:
        return False
    getoption = getattr(pytestconfig, "getoption", None)
    if getoption is None:
        return False
    return bool(getoption("--regen-goldens", default=False))


def assert_or_write_golden(path: Path, actual: str, *, regen: bool) -> None:
    """Compare `actual` against the golden at `path`, or rewrite it when regenerating."""
    if regen:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return

    if not path.exists():
        raise AssertionError(
            f"Missing golden file {path}. Create it with:\n"
            f"  uv run pytest tests/golden --regen-goldens -q"
        )

    expected = path.read_text(encoding="utf-8")
    if expected != actual:
        raise AssertionError(
            f"Golden mismatch for {path.relative_to(GOLDEN_ROOT.parent.parent)}.\n"
            "If this change is intended, review the diff carefully (it is a real change "
            "in emitted DMX) and regenerate with:\n"
            "  uv run pytest tests/golden --regen-goldens -q\n"
            f"{_first_difference(expected, actual)}"
        )


def _first_difference(expected: str, actual: str) -> str:
    """A compact pointer at the first differing line — full diffs here are unreadable."""
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    for index, (expected_line, actual_line) in enumerate(
        zip(expected_lines, actual_lines, strict=False), start=1
    ):
        if expected_line != actual_line:
            return (
                f"first difference at line {index}:\n"
                f"  expected: {expected_line[:400]}\n"
                f"  actual  : {actual_line[:400]}"
            )
    return f"line counts differ: expected {len(expected_lines)}, actual {len(actual_lines)}"
