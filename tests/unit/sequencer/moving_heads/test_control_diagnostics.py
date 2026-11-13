"""Diagnostics for moving-head controls a plan or rig requests and legacy rendering ignores.

One test per `LegacyControl`: its predicate yields exactly that diagnostic, and its
absence yields none. The ignored behavior itself is owned by the legacy renderer and
pinned elsewhere (see `changes/2026_11_12_mh_true_up/plan/phase-0-foundation.md`,
"Diagnostics and fingerprint"); these tests pin only what the audit reports.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
import pytest

from tests.golden.harness import (
    RIGS,
    build_beat_grid,
    build_fixture_group,
    build_plan,
    render_single_section,
)
from tests.support.mh_true_up import synthetic_case
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
    ShutterEvent,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.config.models import JobConfig
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.diagnostics import (
    LegacyControl,
    MHDiagnostic,
    audit_legacy_controls,
)
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    resolve_section_preset,
)
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates

load_builtin_templates()

# Requests nothing on its own: SMOOTH movement, a HOLD dimmer at 255 against its
# declared 60-DMX floor, and no shutter step.
QUIET_TEMPLATE = "sweep_lr_fan_hold"
# SMOOTH movement whose dimmer reaches 0.1 normalized (~26 DMX), below its 60 floor.
FLOOR_TEMPLATE = "sweep_lr_pingpong_phase"
# Every step holds position; only geometry places the beams.
STATIC_MOVEMENT_TEMPLATE = "fan_pulse"
# The one builtin with a template-level shutter step.
SHUTTER_STEP_TEMPLATE = "figure8_mirror_strobe"


def _plan(template_id: str, **section: Any) -> ChoreographyPlan:
    fields: dict[str, Any] = {
        "section_name": "section",
        "start_bar": 1,
        "end_bar": 4,
        "template_id": template_id,
        "preset_id": None,
        **section,
    }
    return ChoreographyPlan(sections=[PlanSection.model_validate(fields)])


def _docs(plan: ChoreographyPlan) -> list[TemplateDoc]:
    ids = {section.template_id for section in plan.sections if section.template_id}
    return [get_template(template_id) for template_id in sorted(ids)]


def _audit(
    plan: ChoreographyPlan,
    fixtures: FixtureGroup,
    templates: list[TemplateDoc] | None = None,
) -> tuple[MHDiagnostic, ...]:
    return audit_legacy_controls(
        plan, fixtures, templates if templates is not None else _docs(plan)
    )


def _controls(diagnostics: tuple[MHDiagnostic, ...]) -> set[LegacyControl | None]:
    return {diagnostic.control for diagnostic in diagnostics}


def _minimal() -> FixtureGroup:
    return build_fixture_group(RIGS["mh4_minimal"])


def _strobe_event() -> list[ShutterEvent]:
    return [ShutterEvent(bar=1, beat=1, pattern=ShutterPattern.STROBE_FAST, moment_cue_id=None)]


def _template_with_step(template_id: str, **step_updates: Any) -> TemplateDoc:
    doc = get_template(template_id)
    steps = [step.model_copy(update=step_updates, deep=True) for step in doc.template.steps]
    template = doc.template.model_copy(update={"steps": steps}, deep=True)
    return doc.model_copy(update={"template": template}, deep=True)


def test_legacy_control_vocabulary_is_closed() -> None:
    assert {control.value for control in LegacyControl} == {
        "pan_tilt_fine",
        "movement_intensity",
        "movement_limits",
        "template_dimmer_floor",
        "shutter_channel_scope",
    }


def test_coarse_only_rig_and_quiet_template_produce_no_diagnostic() -> None:
    assert _audit(_plan(QUIET_TEMPLATE), _minimal()) == ()


class TestPanTiltFine:
    def test_16bit_request_with_fine_channels_is_reported_per_fine_channel(self) -> None:
        case = synthetic_case("fine_carry")
        assert case.plan is not None

        diagnostics = _audit(case.plan, case.fixture_groups[0])

        assert _controls(diagnostics) == {LegacyControl.PAN_TILT_FINE}
        assert [(d.fixture_id, d.channel, d.section_id) for d in diagnostics] == [
            ("MH1", "pan_fine", None),
            ("MH1", "tilt_fine", None),
            ("MH2", "pan_fine", None),
            ("MH2", "tilt_fine", None),
        ]
        assert all(d.code == "legacy_ignored" and d.action == "unchanged" for d in diagnostics)

    def test_fine_channel_without_the_16bit_flag_is_not_a_request(self) -> None:
        case = synthetic_case("fine_carry")
        assert case.plan is not None
        group = case.fixture_groups[0]
        for fixture in group.fixtures:
            assert isinstance(fixture, FixtureInstance)
            fixture.config.dmx_mapping = DmxMapping.model_validate(
                {**fixture.config.dmx_mapping.model_dump(), "use_16bit_pan_tilt": False}
            )

        assert _audit(case.plan, group) == ()

    def test_legacy_output_carries_no_fine_channel_value(self) -> None:
        """The fact the diagnostic reports: fine channels get an inversion flag only."""
        case = synthetic_case("fine_carry")
        assert case.plan is not None
        group = case.fixture_groups[0]
        segments = RenderingPipeline(
            choreography_plan=case.plan,
            beat_grid=case.beat_grid,
            fixture_group=group,
            job_config=JobConfig(),
        ).render()
        fixtures = {fixture.fixture_id: fixture for fixture in group.expand_fixtures()}

        assert segments
        for segment in segments:
            settings = DmxSettingsBuilder(fixtures[segment.fixture_id]).build_settings_string(
                segment
            )
            for fine in (2, 9):
                assert f"E_CHECKBOX_INVDMX{fine}=" in settings
                assert f"E_SLIDER_DMX{fine}=" not in settings
                assert f"E_VALUECURVE_DMX{fine}=" not in settings


class TestMovementIntensity:
    @pytest.mark.parametrize(
        "section",
        [
            pytest.param({"preset_id": "chill"}, id="inferred-preset"),
            pytest.param(
                {
                    "intensity": Intensity.FAST,
                    "shutter_events": [],
                    "gobo_events": [],
                    "moment_cues": [],
                },
                id="section-intent",
            ),
        ],
    )
    def test_non_smooth_request_without_params_key_is_reported(
        self, section: dict[str, Any]
    ) -> None:
        diagnostics = _audit(_plan(QUIET_TEMPLATE, **section), _minimal())

        assert _controls(diagnostics) == {LegacyControl.MOVEMENT_INTENSITY}
        assert len(diagnostics) == 1
        assert diagnostics[0].section_id == "section"
        assert diagnostics[0].fixture_id is None

    def test_template_declared_intensity_is_reported(self) -> None:
        doc = _template_with_step(QUIET_TEMPLATE)
        for step in doc.template.steps:
            step.movement.intensity = Intensity.DRAMATIC

        diagnostics = _audit(_plan(QUIET_TEMPLATE), _minimal(), [doc])

        assert _controls(diagnostics) == {LegacyControl.MOVEMENT_INTENSITY}

    def test_smooth_request_is_not_reported(self) -> None:
        assert _audit(_plan(QUIET_TEMPLATE, preset_id="moderate"), _minimal()) == ()

    def test_params_key_matching_the_request_is_honored(self) -> None:
        doc = _template_with_step(QUIET_TEMPLATE)
        for step in doc.template.steps:
            step.movement.params["intensity"] = Intensity.SLOW.value

        assert _audit(_plan(QUIET_TEMPLATE, preset_id="chill"), _minimal(), [doc]) == ()

    def test_hold_only_movement_is_not_reported(self) -> None:
        """A hold renders the same curve at every intensity, so nothing is lost."""
        diagnostics = _audit(_plan(STATIC_MOVEMENT_TEMPLATE, preset_id="chill"), _minimal())

        assert LegacyControl.MOVEMENT_INTENSITY not in _controls(diagnostics)

    def test_only_moving_steps_are_named(self) -> None:
        diagnostics = _audit(_plan("intro_main_outro_phrase", preset_id="chill"), _minimal())

        intensity = [d for d in diagnostics if d.control == LegacyControl.MOVEMENT_INTENSITY]
        assert len(intensity) == 1
        assert "main requests SLOW" in intensity[0].message
        assert "intro requests" not in intensity[0].message
        assert "outro requests" not in intensity[0].message


class TestMovementLimits:
    def test_non_default_window_is_reported_per_fixture(self) -> None:
        narrow = build_fixture_group(RIGS["mh4_narrow_calibration"])

        diagnostics = _audit(_plan(QUIET_TEMPLATE), narrow)

        assert _controls(diagnostics) == {LegacyControl.MOVEMENT_LIMITS}
        assert [d.fixture_id for d in diagnostics] == ["MH1", "MH2", "MH3", "MH4"]
        assert all(d.section_id is None for d in diagnostics)

    def test_default_window_is_not_a_request(self) -> None:
        assert _audit(_plan(STATIC_MOVEMENT_TEMPLATE), _minimal()) == ()

    def test_static_movement_also_leaves_the_window(self) -> None:
        """Hold-only movement is not bounded either: geometry places it outside."""
        rig = RIGS["mh4_narrow_calibration"]
        assert rig.limits is not None
        pan = [
            float(point.split(":")[1]) * 255
            for effect in render_single_section(
                rig, template_id=STATIC_MOVEMENT_TEMPLATE, preset_id=None
            )
            for part in effect.settings.split(",")
            if part.startswith("E_VALUECURVE_DMX11=")
            for point in part.split("Values=")[1].rstrip("|").split(";")
        ]
        assert pan
        assert min(pan) < rig.limits.pan_min or max(pan) > rig.limits.pan_max

        diagnostics = _audit(_plan(STATIC_MOVEMENT_TEMPLATE), build_fixture_group(rig))
        assert LegacyControl.MOVEMENT_LIMITS in _controls(diagnostics)


class TestTemplateDimmerFloor:
    def test_floor_above_the_dimmer_reach_is_reported(self) -> None:
        diagnostics = _audit(_plan(FLOOR_TEMPLATE), _minimal())

        assert _controls(diagnostics) == {LegacyControl.TEMPLATE_DIMMER_FLOOR}
        assert len(diagnostics) == 1
        assert diagnostics[0].section_id == "section"
        assert diagnostics[0].channel == "dimmer"

    def test_undeclared_floor_is_not_a_request(self) -> None:
        doc = get_template(FLOOR_TEMPLATE)
        defaults = {k: v for k, v in doc.template.defaults.items() if k != "dimmer_floor_dmx"}
        template = doc.template.model_copy(update={"defaults": defaults}, deep=True)
        undeclared = doc.model_copy(update={"template": template}, deep=True)

        assert _audit(_plan(FLOOR_TEMPLATE), _minimal(), [undeclared]) == ()

    def test_floor_the_dimmer_never_dips_below_is_not_reported(self) -> None:
        # The quiet template's HOLD dimmer sits at 255, above its 60 floor.
        assert get_template(QUIET_TEMPLATE).template.defaults["dimmer_floor_dmx"] == 60
        assert _audit(_plan(QUIET_TEMPLATE), _minimal()) == ()

    def test_dramatic_intensity_lifts_the_dimmer_above_the_floor(self) -> None:
        """The reach follows the resolved dimmer intensity, as the handler does.

        `energetic` infers DRAMATIC for movement and dimmer alike, so the movement
        request is still reported while the dimmer now stays above its floor.
        """
        diagnostics = _audit(_plan(FLOOR_TEMPLATE, preset_id="energetic"), _minimal())

        assert _controls(diagnostics) == {LegacyControl.MOVEMENT_INTENSITY}

    def test_message_states_the_range_not_a_reached_value(self) -> None:
        """Under one cycle a pulse never reaches its base, so only the range is claimed."""
        diagnostics = _audit(_plan("ballyhoo_chaos", preset_id="moderate"), _minimal())

        floor = [d for d in diagnostics if d.control == LegacyControl.TEMPLATE_DIMMER_FLOOR]
        assert len(floor) == 1
        message = floor[0].message.lower()
        assert "reach" not in message
        assert "down to 26 dmx" in message
        assert "not applied" in message


class TestShutterChannelScope:
    def test_plan_intent_above_channel_16_is_reported_per_fixture(self) -> None:
        case = synthetic_case("channel_edges")
        assert case.plan is not None

        diagnostics = _audit(case.plan, case.fixture_groups[0])

        assert _controls(diagnostics) == {LegacyControl.SHUTTER_CHANNEL_SCOPE}
        assert [(d.fixture_id, d.section_id, d.channel) for d in diagnostics] == [
            (f"MH{index}", "section", "shutter") for index in range(1, 5)
        ]
        # Intent is dropped; the declared default (255) is still emitted.
        assert all("17" in d.message and "255" in d.message for d in diagnostics)

    def test_only_fixtures_the_template_targets_are_reported(self) -> None:
        """`inner_pendulum_breathe` targets INNER: only MH2 and MH3 receive the event."""
        out_of_window = build_fixture_group(RIGS["mh4_shutter_out_of_window"])
        plan = _plan(
            "inner_pendulum_breathe",
            shutter_events=_strobe_event(),
            gobo_events=[],
            moment_cues=[],
        )
        segments = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=build_beat_grid(),
            fixture_group=out_of_window,
            job_config=JobConfig(),
        ).render()
        dropped = {
            segment.fixture_id
            for segment in segments
            if str(segment.metadata.get("shutter_trace", "")).startswith("warning:")
        }

        diagnostics = [
            d
            for d in _audit(plan, out_of_window)
            if d.control == LegacyControl.SHUTTER_CHANNEL_SCOPE
        ]

        assert [d.fixture_id for d in diagnostics] == ["MH2", "MH3"]
        assert dropped == {"MH2", "MH3"}

    def test_template_shutter_step_above_channel_16_is_reported(self) -> None:
        out_of_window = build_fixture_group(RIGS["mh4_shutter_out_of_window"])

        diagnostics = _audit(_plan(SHUTTER_STEP_TEMPLATE), out_of_window)

        assert LegacyControl.SHUTTER_CHANNEL_SCOPE in _controls(diagnostics)

    def test_channel_17_without_shutter_intent_is_not_reported(self) -> None:
        """Only the default is emitted there, and that default is honored."""
        out_of_window = build_fixture_group(RIGS["mh4_shutter_out_of_window"])

        assert _audit(_plan(QUIET_TEMPLATE), out_of_window) == ()

    def test_intent_on_an_in_window_channel_is_not_reported(self) -> None:
        in_window = build_fixture_group(RIGS["mh4_shutter_in_window"])
        plan = _plan(
            QUIET_TEMPLATE,
            shutter_events=_strobe_event(),
            gobo_events=[],
            moment_cues=[],
        )

        assert _audit(plan, in_window) == ()


class TestAuditContract:
    def _everything(self) -> tuple[ChoreographyPlan, FixtureGroup]:
        """Every control at once: fine + narrow window + shutter 17, three sections."""
        group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="GROUP - MOVING HEADS")
        for fixture_id in ("MH1", "MH2"):
            group.add_fixture(
                FixtureInstance(
                    fixture_id=fixture_id,
                    config=FixtureConfig(
                        fixture_id=fixture_id,
                        dmx_mapping=DmxMapping(
                            pan_channel=11,
                            pan_fine_channel=12,
                            tilt_channel=13,
                            tilt_fine_channel=14,
                            dimmer_channel=15,
                            shutter_channel=17,
                            use_16bit_pan_tilt=True,
                        ),
                        limits=RIGS["mh4_narrow_calibration"].limits,
                    ),
                    xlights_model_name=f"Dmx {fixture_id}",
                )
            )
        plan = ChoreographyPlan(
            sections=[
                PlanSection.model_validate(
                    {
                        "section_name": "a",
                        "start_bar": 1,
                        "end_bar": 4,
                        "template_id": QUIET_TEMPLATE,
                        "preset_id": "chill",
                    }
                ),
                PlanSection.model_validate(
                    {
                        "section_name": "b",
                        "start_bar": 5,
                        "end_bar": 8,
                        "template_id": FLOOR_TEMPLATE,
                        "preset_id": None,
                        "intensity": Intensity.SMOOTH,
                        "shutter_events": [
                            ShutterEvent(
                                bar=5, beat=1, pattern=ShutterPattern.OPEN, moment_cue_id=None
                            )
                        ],
                        "gobo_events": [],
                        "moment_cues": [],
                    }
                ),
                PlanSection.model_validate(
                    {
                        "section_name": "c",
                        "start_bar": 9,
                        "end_bar": 12,
                        "template_id": SHUTTER_STEP_TEMPLATE,
                        "preset_id": None,
                    }
                ),
            ]
        )
        return plan, group

    def test_every_control_is_reported_in_a_fixed_order(self) -> None:
        plan, group = self._everything()

        diagnostics = _audit(plan, group)

        assert [(d.control, d.fixture_id, d.section_id) for d in diagnostics] == [
            (LegacyControl.PAN_TILT_FINE, "MH1", None),
            (LegacyControl.PAN_TILT_FINE, "MH1", None),
            (LegacyControl.MOVEMENT_LIMITS, "MH1", None),
            (LegacyControl.PAN_TILT_FINE, "MH2", None),
            (LegacyControl.PAN_TILT_FINE, "MH2", None),
            (LegacyControl.MOVEMENT_LIMITS, "MH2", None),
            (LegacyControl.MOVEMENT_INTENSITY, None, "a"),
            (LegacyControl.TEMPLATE_DIMMER_FLOOR, None, "b"),
            (LegacyControl.SHUTTER_CHANNEL_SCOPE, "MH1", "b"),
            (LegacyControl.SHUTTER_CHANNEL_SCOPE, "MH2", "b"),
            (LegacyControl.MOVEMENT_INTENSITY, None, "c"),
            (LegacyControl.SHUTTER_CHANNEL_SCOPE, "MH1", "c"),
            (LegacyControl.SHUTTER_CHANNEL_SCOPE, "MH2", "c"),
        ]

    def test_ordering_is_deterministic_and_ignores_template_order(self) -> None:
        plan, group = self._everything()
        templates = _docs(plan)

        first = audit_legacy_controls(plan, group, templates)

        assert audit_legacy_controls(plan, group, templates) == first
        assert audit_legacy_controls(plan, group, list(reversed(templates))) == first

    def test_inputs_are_not_mutated(self) -> None:
        plan, group = self._everything()
        templates = _docs(plan)
        before = (
            plan.model_dump(),
            [section.legacy_intent_omitted for section in plan.sections],
            group.model_dump(),
            [doc.model_dump() for doc in templates],
        )

        audit_legacy_controls(plan, group, templates)

        assert before == (
            plan.model_dump(),
            [section.legacy_intent_omitted for section in plan.sections],
            group.model_dump(),
            [doc.model_dump() for doc in templates],
        )

    def test_segmented_sections_are_audited_per_segment(self) -> None:
        plan = ChoreographyPlan(
            sections=[
                PlanSection.model_validate(
                    {
                        "section_name": "verse",
                        "start_bar": 1,
                        "end_bar": 8,
                        "segments": [
                            {
                                "segment_id": "A",
                                "start_bar": 1,
                                "end_bar": 4,
                                "template_id": QUIET_TEMPLATE,
                            },
                            {
                                "segment_id": "B",
                                "start_bar": 5,
                                "end_bar": 8,
                                "template_id": QUIET_TEMPLATE,
                                "preset_id": "chill",
                            },
                        ],
                    }
                )
            ]
        )

        diagnostics = _audit(plan, _minimal(), [get_template(QUIET_TEMPLATE)])

        assert [(d.control, d.section_id) for d in diagnostics] == [
            (LegacyControl.MOVEMENT_INTENSITY, "verse|B")
        ]

    def test_unknown_template_is_an_error(self) -> None:
        with pytest.raises(ValueError, match=QUIET_TEMPLATE):
            audit_legacy_controls(_plan(QUIET_TEMPLATE), _minimal(), [])

    def test_diagnostic_is_frozen_and_codes_are_bounded(self) -> None:
        diagnostic = MHDiagnostic(
            code="legacy_ignored",
            severity="warning",
            message="m",
            control=LegacyControl.MOVEMENT_LIMITS,
            action="unchanged",
        )
        with pytest.raises(ValidationError):
            diagnostic.message = "changed"  # type: ignore[misc]
        with pytest.raises(ValidationError):
            MHDiagnostic.model_validate({**diagnostic.model_dump(), "code": "something_else"})

    def test_control_is_set_exactly_for_legacy_ignored(self) -> None:
        with pytest.raises(ValidationError):
            MHDiagnostic(code="legacy_ignored", severity="warning", message="m", action="unchanged")
        with pytest.raises(ValidationError):
            MHDiagnostic(
                code="lock_conflict",
                severity="error",
                message="m",
                control=LegacyControl.MOVEMENT_LIMITS,
                action="rejected",
            )


class TestPipelineAccessor:
    def test_diagnostics_audit_the_plans_templates(self) -> None:
        plan = build_plan()
        group = build_fixture_group(RIGS["mh4_narrow_calibration"])
        pipeline = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=build_beat_grid(),
            fixture_group=group,
            job_config=JobConfig(),
        )

        assert pipeline.diagnostics == audit_legacy_controls(plan, group, _docs(plan))
        assert pipeline.diagnostics

    def test_accessors_do_not_change_rendered_output(self) -> None:
        def render(*, inspect: bool) -> list[dict[str, Any]]:
            pipeline = RenderingPipeline(
                choreography_plan=build_plan(),
                beat_grid=build_beat_grid(),
                fixture_group=build_fixture_group(RIGS["mh4_narrow_calibration"]),
                job_config=JobConfig(),
            )
            if inspect:
                assert pipeline.diagnostics
                assert pipeline.fingerprint()
            return [segment.model_dump() for segment in pipeline.render()]

        assert render(inspect=True) == render(inspect=False)


class TestTemplateLookup:
    @pytest.mark.parametrize(
        ("spelling", "canonical"),
        [
            pytest.param("SWEEP_LR_FAN_HOLD", "sweep_lr_fan_hold", id="upper-case"),
            pytest.param(
                "Wave Vertical Spotlight Fade", "wave_vertical_spotlight_fade", id="display-name"
            ),
        ],
    )
    def test_any_registry_spelling_is_audited_like_the_canonical_id(
        self, spelling: str, canonical: str
    ) -> None:
        group = _minimal()
        expected = audit_legacy_controls(
            _plan(canonical, preset_id="chill"), group, [get_template(canonical)]
        )
        plan = _plan(spelling, preset_id="chill")

        assert expected
        assert audit_legacy_controls(plan, group, [get_template(canonical)]) == expected
        pipeline = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=build_beat_grid(),
            fixture_group=group,
            job_config=JobConfig(),
        )
        assert pipeline.diagnostics == expected


class TestResolveSectionPreset:
    """The one preset resolution `render()` and the audit share."""

    def _section(self, preset_id: str | None) -> PlanSection:
        return _plan("cascade_pulse_lr", preset_id=preset_id).sections[0]

    def test_a_declared_preset_is_returned(self) -> None:
        doc = get_template("cascade_pulse_lr")

        preset = resolve_section_preset(self._section("gentle"), doc)

        assert preset == next(p for p in doc.presets if p.preset_id == "gentle")

    def test_an_energy_named_id_patches_every_step(self) -> None:
        doc = get_template("cascade_pulse_lr")

        preset = resolve_section_preset(self._section("chill"), doc)

        assert preset is not None
        assert set(preset.step_patches) == {step.step_id for step in doc.template.steps}
        for patch in preset.step_patches.values():
            assert patch.movement == {"intensity": Intensity.SLOW.value}
            assert patch.dimmer == {"intensity": Intensity.SLOW.value}

    @pytest.mark.parametrize("preset_id", [None, "no_such_preset"])
    def test_no_or_unknown_preset_resolves_to_none(self, preset_id: str | None) -> None:
        assert (
            resolve_section_preset(self._section(preset_id), get_template("cascade_pulse_lr"))
            is None
        )
