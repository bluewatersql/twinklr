"""Offline contract tests for the live xLights injection workflow (P2P-T12)."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import httpx
import pytest

from twinklr.core.api.xlights import XLightsAutomationClient
from twinklr.core.api.xlights.injection import (
    TWINKLR_LAYER_BASE,
    InjectionCollisionError,
    JsonOwnershipStore,
    LiveEffect,
    LiveInjectionWorkflow,
    MemoryOwnershipStore,
    live_effects_from_segments,
    reconcile_live_layout,
)
from twinklr.core.config.fixtures import DmxMapping, FixtureConfig, FixtureGroup, FixtureInstance
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter


def _rig(*names: str) -> FixtureGroup:
    group = FixtureGroup(
        group_id="MOVING_HEADS",
        xlights_group="GROUP - MOVING HEADS",
    )
    for index, name in enumerate(names):
        fixture_id = f"MH{index + 1}"
        group.add_fixture(
            FixtureInstance(
                fixture_id=fixture_id,
                config=FixtureConfig(
                    fixture_id=fixture_id,
                    dmx_mapping=DmxMapping(
                        pan_channel=11,
                        tilt_channel=13,
                        dimmer_channel=15,
                    ),
                ),
                xlights_model_name=name,
            )
        )
    return group


def test_getmodels_parsed_into_rig_and_divergence_reported() -> None:
    reconciliation = reconcile_live_layout(
        _rig("Dmx MH1", "Dmx MH2"),
        model_names=("Dmx MH1", "Unconfigured Prop"),
        group_names=("Other Group",),
    )

    assert [fixture.xlights_model_name for fixture in reconciliation.rig.expand_fixtures()] == [
        "Dmx MH1"
    ]
    assert reconciliation.report.configured_only_models == ("Dmx MH2",)
    assert reconciliation.report.live_only_models == ("Unconfigured Prop",)
    assert reconciliation.report.missing_configured_groups == ("GROUP - MOVING HEADS",)
    assert reconciliation.report.has_divergence


def test_injection_settings_match_golden_export_builder() -> None:
    rig = _rig("Dmx MH1")
    segment = FixtureSegment(
        section_id="chorus",
        segment_id="segment",
        step_id="step",
        template_id="template",
        fixture_id="MH1",
        t0_ms=100,
        t1_ms=900,
        channels={
            ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=11),
            ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=22),
            ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=233),
        },
        allow_grouping=False,
    )

    live = live_effects_from_segments([segment], rig)
    expected = DmxSettingsBuilder(rig.expand_fixtures()[0]).build_settings_string(segment)

    assert len(live) == 1
    assert live[0].settings == expected
    assert live[0].request().to_wire()["settings"] == expected


def test_golden_live_layers_preserve_xsq_topology_without_self_overlap() -> None:
    rig = _rig("Dmx MH1")
    regular = FixtureSegment(
        section_id="chorus",
        segment_id="regular",
        step_id="step",
        template_id="template",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=1000,
        channels={ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)},
        allow_grouping=False,
    )
    transition = regular.model_copy(
        update={
            "segment_id": "transition",
            "t0_ms": 400,
            "t1_ms": 600,
            "metadata": {"is_transition": "true"},
        }
    )

    placements = XsqAdapter().convert(
        [regular, transition],
        rig,
        build_fresh_sequence(media_file="golden.wav", duration_ms=1000),
    )
    live = live_effects_from_segments([regular, transition], rig)

    expected_topology = sorted(
        (item.element_name, item.layer_index, item.start_ms, item.end_ms) for item in placements
    )
    live_topology = sorted(
        (
            item.target,
            item.layer - TWINKLR_LAYER_BASE,
            item.start_ms,
            item.end_ms,
        )
        for item in live
    )
    assert live_topology == expected_topology
    assert live[0].target == live[1].target
    assert live[0].start_ms < live[1].end_ms and live[1].start_ms < live[0].end_ms
    assert live[0].layer != live[1].layer


class _StatefulXLights:
    def __init__(self) -> None:
        self.effects: dict[str, list[list[dict[str, object]]]] = {}
        self.requests: list[dict[str, object]] = []
        self.next_id = 1
        self.fail_add_number: int | None = None
        self.ambiguous_add_number: int | None = None
        self.add_count = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        body: dict[str, object] = json.loads(request.content)
        self.requests.append(body)
        command = body["cmd"]
        if command == "getOpenSequence":
            return httpx.Response(
                200,
                json={
                    "seq": "scratch.xsq",
                    "fullseq": "/tmp/scratch.xsq",
                    "framems": "50",
                },
            )
        if command == "getEffectIDs":
            layers = self.effects.get(str(body["model"]), [])
            return httpx.Response(
                200,
                json={"effects": [[str(effect["id"]) for effect in layer] for layer in layers]},
            )
        if command == "getEffectSettings":
            effect = self.effects[str(body["model"])][int(str(body["layer"]))]
            match = next(item for item in effect if str(item["id"]) == str(body["id"]))
            return httpx.Response(
                200, json={key: value for key, value in match.items() if key != "id"}
            )
        if command == "deleteEffect":
            layer = self.effects[str(body["model"])][int(str(body["layer"]))]
            layer[:] = [item for item in layer if str(item["id"]) != str(body["id"])]
            return httpx.Response(200, json={"msg": "Deleted Effect.", "worked": "true"})
        if command == "addEffect":
            self.add_count += 1
            if self.fail_add_number == self.add_count:
                return httpx.Response(503, json={"msg": "injected failure"})
            model = str(body["target"])
            layer_number = int(str(body["layer"]))
            layers = self.effects.setdefault(model, [])
            while len(layers) <= layer_number:
                layers.append([])
            layers[layer_number].append(
                {
                    "id": self.next_id,
                    "name": body["effect"],
                    "settings": body["settings"],
                    "palette": body["palette"],
                    "startTime": body["startTime"],
                    "endTime": body["endTime"],
                }
            )
            self.next_id += 1
            if self.ambiguous_add_number == self.add_count:
                raise httpx.ReadError("response lost after apply", request=request)
            return httpx.Response(200, json={"msg": "Added Effects.", "worked": "true"})
        raise AssertionError(f"unexpected command: {body!r}")


def _effect(*, start: int = 0, end: int = 1000, settings: str = "E_SLIDER_DMX1=1") -> LiveEffect:
    return LiveEffect(
        target="Dmx MH1",
        effect="DMX",
        settings=settings,
        palette="",
        start_ms=start,
        end_ms=end,
        section_id="chorus",
    )


@pytest.mark.anyio
async def test_injection_wire_order_and_idempotence() -> None:
    fake = _StatefulXLights()
    ownership = MemoryOwnershipStore()
    effects = (
        _effect(),
        replace(_effect(settings="transition"), layer=TWINKLR_LAYER_BASE + 1),
    )
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=ownership)
        first = await workflow.inject(effects)
        second = await workflow.inject(effects)

    assert first.injected == effects
    assert second.injected == ()
    assert second.unchanged == effects
    assert [request["cmd"] for request in fake.requests] == [
        "getOpenSequence",
        "getEffectIDs",
        "addEffect",
        "addEffect",
        "getOpenSequence",
        "getEffectIDs",
        "getEffectSettings",
        "getEffectSettings",
    ]
    assert [request["layer"] for request in fake.requests if request["cmd"] == "addEffect"] == [
        "99",
        "100",
    ]


@pytest.mark.anyio
async def test_collision_with_user_effects_halts_before_write() -> None:
    fake = _StatefulXLights()
    fake.effects["Dmx MH1"] = [[] for _ in range(100)]
    fake.effects["Dmx MH1"][99].append(
        {
            "id": 7,
            "name": "DMX",
            "settings": "E_SLIDER_DMX1=200",
            "palette": "",
            "startTime": "100",
            "endTime": "900",
        }
    )
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=MemoryOwnershipStore())
        with pytest.raises(InjectionCollisionError, match="Dmx MH1"):
            await workflow.inject((_effect(),))

    assert not any(request["cmd"] in {"addEffect", "deleteEffect"} for request in fake.requests)


@pytest.mark.anyio
async def test_desired_effects_cannot_overlap_on_same_reserved_target_layer() -> None:
    fake = _StatefulXLights()
    first = _effect(start=0, end=700)
    second = _effect(start=500, end=1000, settings="second")
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=MemoryOwnershipStore())
        with pytest.raises(InjectionCollisionError, match="planned effects overlap"):
            await workflow.inject((first, second))

    assert fake.requests == []


@pytest.mark.anyio
async def test_dry_run_issues_no_writes_and_reports_exact_commands() -> None:
    fake = _StatefulXLights()
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=MemoryOwnershipStore())
        result = await workflow.inject((_effect(),), dry_run=True)

    assert result.dry_run
    assert result.commands == (
        {
            "cmd": "addEffect",
            "target": "Dmx MH1",
            "effect": "DMX",
            "settings": "E_SLIDER_DMX1=1",
            "palette": "",
            "layer": "99",
            "startTime": "0",
            "endTime": "1000",
        },
    )
    assert not any(request["cmd"] in {"addEffect", "deleteEffect"} for request in fake.requests)


@pytest.mark.anyio
async def test_regenerate_section_touches_only_that_section() -> None:
    fake = _StatefulXLights()
    ownership = MemoryOwnershipStore()
    intro = LiveEffect(
        target="Dmx MH1",
        effect="DMX",
        settings="intro-old",
        palette="",
        start_ms=0,
        end_ms=1000,
        section_id="intro",
    )
    chorus = _effect(start=1000, end=2000, settings="chorus-old")
    transition = replace(
        chorus,
        settings="transition-old",
        start_ms=1400,
        end_ms=1600,
        layer=TWINKLR_LAYER_BASE + 1,
    )
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=ownership)
        await workflow.inject((intro, chorus, transition))
        fake.requests.clear()
        replacement = _effect(start=1000, end=2000, settings="chorus-new")
        replacement_transition = replace(
            transition,
            settings="transition-new",
        )
        await workflow.regenerate_section("chorus", (replacement, replacement_transition))

    commands = [request["cmd"] for request in fake.requests]
    assert commands == [
        "getOpenSequence",
        "getEffectIDs",
        "getEffectSettings",
        "getEffectSettings",
        "getEffectSettings",
        "deleteEffect",
        "deleteEffect",
        "addEffect",
        "addEffect",
    ]
    assert any(effect["settings"] == "intro-old" for effect in fake.effects["Dmx MH1"][99])
    assert any(effect["settings"] == "chorus-new" for effect in fake.effects["Dmx MH1"][99])
    assert any(effect["settings"] == "transition-new" for effect in fake.effects["Dmx MH1"][100])


@pytest.mark.anyio
async def test_regenerate_empty_section_removes_owned_effects_on_disappearing_target() -> None:
    fake = _StatefulXLights()
    ownership = MemoryOwnershipStore()
    intro = replace(_effect(end=500, settings="intro"), section_id="intro")
    chorus = LiveEffect(
        target="Dmx MH2",
        effect="DMX",
        settings="chorus",
        palette="",
        start_ms=500,
        end_ms=1000,
        section_id="chorus",
    )
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=ownership)
        await workflow.inject((intro, chorus))
        fake.requests.clear()
        await workflow.regenerate_section("chorus", ())

    assert [request["cmd"] for request in fake.requests] == [
        "getOpenSequence",
        "getEffectIDs",
        "getEffectSettings",
        "deleteEffect",
    ]
    assert fake.effects["Dmx MH2"][99] == []
    assert fake.effects["Dmx MH1"][99][0]["settings"] == "intro"


@pytest.mark.anyio
async def test_partial_failure_reports_confirmed_injected_set() -> None:
    fake = _StatefulXLights()
    fake.fail_add_number = 2
    effects = (
        _effect(end=500),
        replace(_effect(start=0, end=500, settings="second"), layer=TWINKLR_LAYER_BASE + 1),
    )
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=MemoryOwnershipStore())
        result = await workflow.inject(effects, raise_on_partial=False)

    assert result.complete is False
    assert result.injected == (effects[0],)
    assert result.failed_command is not None
    assert result.failed_command["settings"] == "second"
    assert result.failed_command["layer"] == "100"
    assert "re-run" in result.recovery.lower()


@pytest.mark.anyio
async def test_ambiguous_add_is_not_replayed_and_idempotent_rerun_recovers() -> None:
    fake = _StatefulXLights()
    fake.ambiguous_add_number = 1
    effect = _effect()
    ownership = MemoryOwnershipStore()
    async with XLightsAutomationClient(transport=fake.transport()) as client:
        workflow = LiveInjectionWorkflow(client, ownership=ownership)
        first = await workflow.inject((effect,), raise_on_partial=False)
        fake.ambiguous_add_number = None
        second = await workflow.inject((effect,))

    assert first.complete is False and first.injected == ()
    assert second.complete and second.unchanged == (effect,)
    assert [request["cmd"] for request in fake.requests].count("addEffect") == 1


def test_json_ownership_manifest_preserves_actual_reserved_layer(tmp_path) -> None:
    store = JsonOwnershipStore(tmp_path / "ownership.json")
    sequence = Path("/tmp/scratch.xsq")
    effect = replace(_effect(), layer=TWINKLR_LAYER_BASE + 1)

    store.save(sequence, (effect,))

    assert store.load(sequence) == (effect,)
