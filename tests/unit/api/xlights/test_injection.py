"""Offline contract tests for the live xLights injection workflow (P2P-T12)."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

import httpx
import pytest

from tests.support.live_xlights import SCRATCH_SEQUENCE, FakeLiveXLights
from tests.support.moving_heads import (
    p1_grid,
    p1_job,
    p1_plan,
    p1_rig,
    p1_templates,
)
from twinklr.core.api.xlights import XLightsAutomationClient, injection
from twinklr.core.api.xlights.errors import XLightsTimeoutError
from twinklr.core.api.xlights.injection import (
    MAX_LIVE_EFFECTS,
    NO_SECTION_ID,
    TWINKLR_LAYER_BASE,
    InjectionCollisionError,
    InjectionError,
    InjectionVolumeError,
    JsonOwnershipStore,
    LiveEffect,
    LiveInjectionWorkflow,
    MemoryOwnershipStore,
    live_effects_from_sequence,
    reconcile_live_layout,
)
from twinklr.core.config.fixtures import DmxMapping, FixtureConfig, FixtureGroup, FixtureInstance
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline


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


# --- Moving-head output (cutover C1.1c) -----------------------------------------------------


def _xsq_effects(path: Path) -> list[tuple[str, int, str, str, str, int, int]]:
    """Every effect of a written `.xsq` in its live form: the model, its file layer moved
    into the reserved namespace, the effect, its EffectDB settings, its palette's
    settings (none when the file defines no palette; the parser reads an absent
    reference as "0") and its times."""
    sequence = XSQParser().parse(path)
    palettes = [palette.settings for palette in sequence.color_palettes]
    effects = []
    for element in sequence.element_effects:
        for layer_index, layer in enumerate(element.layers):
            for effect in layer.effects:
                assert effect.ref is not None
                settings = sequence.effect_db.get(effect.ref)
                assert settings is not None
                effects.append(
                    (
                        element.element_name,
                        TWINKLR_LAYER_BASE + layer_index,
                        effect.effect_type,
                        settings,
                        palettes[int(effect.palette)] if palettes else "",
                        effect.start_time_ms,
                        effect.end_time_ms,
                    )
                )
    return sorted(effects)


def _live_form(
    effects: tuple[LiveEffect, ...],
) -> list[tuple[str, int, str, str, str, int, int]]:
    return sorted(
        (e.target, e.layer, e.effect, e.settings, e.palette, e.start_ms, e.end_ms) for e in effects
    )


def test_live_effects_equal_the_written_xsq_element_by_element(tmp_path: Path) -> None:
    """A render's live effects are the `.xsq`'s effects: the same models, layer,
    DMX settings and frame-aligned times, one for one, and section provenance on each."""
    output = tmp_path / "show.xsq"
    with p1_templates():
        pipeline = RenderingPipeline(
            choreography_plan=p1_plan(),
            beat_grid=p1_grid(),
            fixture_group=p1_rig(),
            job_config=p1_job(),
            output_path=output,
            media_file="song.wav",
        )
        pipeline.render()

    assert pipeline.sequence is not None
    live = live_effects_from_sequence(pipeline.sequence)

    assert _live_form(live) == _xsq_effects(output)
    trace = json.loads(output.with_suffix(".xsq.trace.json").read_text(encoding="utf-8"))
    assert len(live) == trace["render"]["output"]["effect_count"]
    assert {effect.target for effect in live} == {"Dmx MH1", "Dmx MH2"}
    assert {effect.layer for effect in live} == {TWINKLR_LAYER_BASE}
    # Runs inside the section carry it; runs no section's segment covers (the song-end
    # park) carry the reserved provenance instead of an empty id.
    assert {effect.section_id for effect in live} <= {"verse", NO_SECTION_ID}
    assert any(effect.section_id == "verse" for effect in live)


def _runs(
    count: int, *, targets: int = 4, settings: str = "E_SLIDER_DMX1=1"
) -> tuple[LiveEffect, ...]:
    """`count` back-to-back 20 ms DMX runs spread over `targets` models, as a
    render emits them."""
    return tuple(
        LiveEffect(
            target=f"Dmx MH{index % targets + 1}",
            effect="DMX",
            settings=f"{settings},E_SLIDER_DMX2={index % 256}",
            palette="",
            start_ms=(index // targets) * 20,
            end_ms=(index // targets) * 20 + 20,
            section_id="chorus",
        )
        for index in range(count)
    )


@pytest.mark.anyio
async def test_thirty_thousand_effects_inject_reinject_and_replace_in_linear_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The volume of a render (about 30,000 effects on four heads for a
    three-minute song) goes through the per-effect API in one request per effect and
    write, with no quadratic work before or between requests: interval comparisons and
    effect equality tests stay within a small multiple of the effect count."""
    fake = FakeLiveXLights()
    ownership = MemoryOwnershipStore()
    effects = _runs(30_000)
    replacement = _runs(30_000, settings="E_SLIDER_DMX1=2")
    comparisons = Counter[str]()
    overlaps, equals = injection._overlaps, LiveEffect.__eq__

    def counted_overlaps(*args: int) -> bool:
        comparisons["overlaps"] += 1
        return overlaps(*args)

    def counted_equals(self: LiveEffect, other: object) -> bool:
        comparisons["equals"] += 1
        return equals(self, other)

    monkeypatch.setattr(injection, "_overlaps", counted_overlaps)
    monkeypatch.setattr(LiveEffect, "__eq__", counted_equals)

    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    first = await workflow.inject(effects)
    first_requests = Counter(fake.requests)
    fake.requests.clear()
    again = await workflow.inject(effects)
    again_requests = Counter(fake.requests)
    fake.requests.clear()
    replaced = await workflow.inject(replacement)

    assert first_requests == {"getOpenSequence": 1, "getEffectIDs": 4, "addEffect": 30_000}
    assert len(first.injected) == 30_000
    assert again_requests == {
        "getOpenSequence": 1,
        "getEffectIDs": 4,
        "getEffectSettings": 30_000,
    }
    assert len(again.unchanged) == 30_000 and again.injected == again.deleted == ()
    assert Counter(fake.requests) == {
        "getOpenSequence": 1,
        "getEffectIDs": 4,
        "getEffectSettings": 30_000,
        "deleteEffect": 30_000,
        "addEffect": 30_000,
    }
    assert len(replaced.deleted) == len(replaced.injected) == 30_000
    assert fake.placed() == _live_form(replacement)
    assert ownership.load(SCRATCH_SEQUENCE) == tuple(sorted(replacement))
    # Three commands of 30,000 effects: one sweep comparison per adjacent pair of each
    # command's effects, and no list scans. The pairwise overlap check and the
    # list-based manifest this replaced made about 1.35e9 comparisons (43 s).
    assert comparisons["overlaps"] <= 3 * 30_000
    assert comparisons["equals"] <= 3 * 30_000


@pytest.mark.anyio
async def test_more_effects_than_the_live_bound_are_refused_before_any_request() -> None:
    fake = FakeLiveXLights()
    workflow = LiveInjectionWorkflow(fake, ownership=MemoryOwnershipStore())  # type: ignore[arg-type]

    with pytest.raises(InjectionVolumeError, match=f"{MAX_LIVE_EFFECTS + 1} effects"):
        await workflow.inject(_runs(MAX_LIVE_EFFECTS + 1), dry_run=True)

    assert fake.requests == []


@pytest.mark.anyio
async def test_deleting_more_owned_effects_than_the_live_bound_is_refused_before_any_write() -> (
    None
):
    """The bound also holds for the owned effects a command would delete, counted after
    reading what is really in the sequence."""
    fake = FakeLiveXLights()
    ownership = MemoryOwnershipStore()
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    await workflow.inject(_runs(MAX_LIVE_EFFECTS))
    # One more owned effect than a command may delete, placed as an earlier run left it.
    await fake.add_effect(_runs(MAX_LIVE_EFFECTS + 1)[-1].request())
    ownership.save(SCRATCH_SEQUENCE, _runs(MAX_LIVE_EFFECTS + 1))
    fake.requests.clear()

    with pytest.raises(
        InjectionVolumeError, match=f"{MAX_LIVE_EFFECTS + 1} owned effects to delete"
    ):
        await workflow.inject((_effect(start=10**8, end=10**8 + 20),))

    assert "deleteEffect" not in fake.requests and "addEffect" not in fake.requests


@pytest.mark.anyio
async def test_more_recorded_rows_than_any_pre_write_manifest_are_refused_before_reading() -> None:
    """Recorded rows are only a sanity cap, at twice the bound: a manifest saved before a
    killed run's first write (its present effects plus its effects to add) stays below."""
    fake = FakeLiveXLights()
    ownership = MemoryOwnershipStore()
    ownership.save(SCRATCH_SEQUENCE, _runs(2 * MAX_LIVE_EFFECTS + 1))
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]

    with pytest.raises(InjectionVolumeError, match=f"{2 * MAX_LIVE_EFFECTS + 1} owned effects"):
        await workflow.inject(_runs(10))

    assert fake.requests == ["getOpenSequence"]


@pytest.mark.anyio
@pytest.mark.parametrize(("at", "phase"), [(15_000, "delete"), (30_000 + 15_000, "add")])
async def test_a_whole_render_replacement_killed_without_cleanup_converges_at_full_size(
    at: int, phase: str
) -> None:
    """A 30,000-for-30,000 replacement killed with no handler (only the manifest saved
    before its first write survives) is finished by the same command: the user's effects
    are untouched, the manifest matches the sequence, and no never-added row lingers."""
    ownership = MemoryOwnershipStore()
    fake = _Killed(ownership)
    user = {"name": "On", "settings": "U=1", "palette": "", "start_ms": 0, "end_ms": 10**6}
    fake.layers["Dmx MH1"] = [{} for _ in range(TWINKLR_LAYER_BASE)]
    fake.layers["Dmx MH1"][TWINKLR_LAYER_BASE - 1]["user"] = dict(user)
    fake.layers["Prop"] = [{"user": dict(user)}]
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    old, new = _runs(30_000), _runs(30_000, settings="E_SLIDER_DMX1=2")
    await workflow.inject(old)
    fake.at, fake.writes = at, 0

    with pytest.raises(KeyboardInterrupt):
        await workflow.inject(new)
    fake.at = None
    assert fake.survived is not None and len(fake.survived) == 60_000
    survivor = MemoryOwnershipStore()
    survivor.save(SCRATCH_SEQUENCE, fake.survived)
    fake.requests.clear()
    rerun = await LiveInjectionWorkflow(fake, ownership=survivor).inject(new)  # type: ignore[arg-type]

    present = 30_000 - (at - 1) if phase == "delete" else at - 1 - 30_000
    assert Counter(fake.requests) == {
        "getOpenSequence": 1,
        "getEffectIDs": 4,
        "getEffectSettings": present,
        **({"deleteEffect": present, "addEffect": 30_000} if phase == "delete" else {}),
        **({"addEffect": 30_000 - present} if phase == "add" else {}),
    }
    assert rerun.complete
    twinklr = [placed for placed in fake.placed() if placed[0] != "Prop" and placed[1] >= 99]
    assert twinklr == _live_form(new)
    assert fake.layers["Dmx MH1"][TWINKLR_LAYER_BASE - 1]["user"] == user
    assert fake.layers["Prop"][0]["user"] == user
    assert _live_form(survivor.load(SCRATCH_SEQUENCE)) == twinklr


@pytest.mark.anyio
async def test_a_killed_replacement_leaves_no_unplaced_rows_after_the_next_run() -> None:
    """Rows a killed run recorded but never placed are dropped by the next command that
    reads their layer."""
    ownership = MemoryOwnershipStore()
    fake = _Killed(ownership)
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]

    def section(name: str, version: int, start: int) -> tuple[LiveEffect, ...]:
        return tuple(
            replace(
                effect,
                section_id=name,
                start_ms=effect.start_ms + start,
                end_ms=effect.end_ms + start,
            )
            for effect in _runs(8, settings=f"{name}={version}")
        )

    await workflow.inject(section("a", 1, 0) + section("b", 1, 1000))
    fake.at, fake.writes = 8 + 2, 0
    with pytest.raises(KeyboardInterrupt):
        await workflow.inject(section("a", 2, 0) + section("b", 1, 1000))
    fake.at = None
    assert fake.survived is not None
    ownership.save(SCRATCH_SEQUENCE, fake.survived)

    desired = section("a", 2, 0) + section("b", 2, 1000)
    await workflow.inject(desired)

    recorded = ownership.load(SCRATCH_SEQUENCE)
    assert _live_form(recorded) == fake.placed() == _live_form(desired)


class _Interrupted(FakeLiveXLights):
    """Raises `error` instead of applying the `at`-th write (delete or add) it receives."""

    def __init__(self) -> None:
        super().__init__()
        self.at: int | None = None
        self.error: BaseException = KeyboardInterrupt()
        self.writes = 0

    async def _write(self) -> None:
        self.writes += 1
        if self.writes == self.at:
            raise self.error

    async def add_effect(self, request):  # type: ignore[no-untyped-def]
        await self._write()
        return await super().add_effect(request)

    async def delete_effect(self, request):  # type: ignore[no-untyped-def]
        await self._write()
        return await super().delete_effect(request)


class _Killed(_Interrupted):
    """A process killed mid-write: nothing it saves after its first write survives."""

    def __init__(self, ownership: MemoryOwnershipStore) -> None:
        super().__init__()
        self.ownership = ownership
        self.survived: tuple[LiveEffect, ...] | None = None

    async def _write(self) -> None:
        if self.at is not None and self.survived is None:
            self.survived = self.ownership.load(SCRATCH_SEQUENCE)
        await super()._write()


@pytest.mark.anyio
@pytest.mark.parametrize("error", [KeyboardInterrupt(), asyncio.CancelledError()])
@pytest.mark.parametrize(("at", "phase"), [(7, "delete"), (40 + 7, "add")])
async def test_an_interrupted_replacement_records_its_state_and_the_rerun_converges(
    error: BaseException, at: int, phase: str
) -> None:
    """Ctrl-C or task cancellation in the middle of the writes leaves a manifest that
    owns every effect Twinklr may have placed, so running the same command again
    finishes the replacement instead of refusing a "user-owned" collision."""
    fake = _Interrupted()
    ownership = MemoryOwnershipStore()
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    old, new = _runs(40), _runs(40, settings="E_SLIDER_DMX1=2")
    await workflow.inject(old)
    fake.at, fake.error, fake.writes = at, error, 0

    with pytest.raises(type(error)):
        await workflow.inject(new)
    assert fake.placed() not in (_live_form(old), _live_form(new)), phase
    # Exactly the confirmed state: the old effects not yet deleted (the interrupted
    # delete included), or the adds confirmed plus the interrupted one.
    assert len(ownership.load(SCRATCH_SEQUENCE)) == (40 - 6 if phase == "delete" else 6 + 1)
    fake.at = None
    rerun = await workflow.inject(new)

    assert rerun.complete
    assert fake.placed() == _live_form(new)
    assert ownership.load(SCRATCH_SEQUENCE) == tuple(sorted(new))


@pytest.mark.anyio
@pytest.mark.parametrize("at", [7, 40 + 7])
async def test_a_run_killed_without_cleanup_converges_from_the_pre_write_manifest(
    at: int,
) -> None:
    """Even when nothing runs after the kill, the manifest saved before the first write
    already owns every effect the command could place."""
    ownership = MemoryOwnershipStore()
    fake = _Killed(ownership)
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    old, new = _runs(40), _runs(40, settings="E_SLIDER_DMX1=2")
    await workflow.inject(old)
    fake.at, fake.writes = at, 0

    with pytest.raises(KeyboardInterrupt):
        await workflow.inject(new)
    fake.at = None
    assert fake.survived is not None
    survivor = MemoryOwnershipStore()
    survivor.save(SCRATCH_SEQUENCE, fake.survived)
    rerun = await LiveInjectionWorkflow(fake, ownership=survivor).inject(new)  # type: ignore[arg-type]

    assert rerun.complete
    assert fake.placed() == _live_form(new)


@pytest.mark.anyio
async def test_a_partial_failure_after_deletes_records_exactly_what_remains_owned() -> None:
    """A delete confirmed before the failure leaves the manifest; the one that failed
    (it may have been applied) and every not-yet-deleted effect stay owned."""
    fake = _Interrupted()
    ownership = MemoryOwnershipStore()
    workflow = LiveInjectionWorkflow(fake, ownership=ownership)  # type: ignore[arg-type]
    old, new = _runs(3), _runs(3, settings="E_SLIDER_DMX1=2")
    await workflow.inject(old)
    fake.at, fake.error, fake.writes = 2, XLightsTimeoutError("lost"), 0

    result = await workflow.inject(new, raise_on_partial=False)

    assert len(result.deleted) == 1 and result.injected == ()
    assert ownership.load(SCRATCH_SEQUENCE) == tuple(
        sorted(effect for effect in old if effect not in result.deleted)
    )


@pytest.mark.anyio
async def test_touching_effects_are_neither_a_planned_overlap_nor_a_user_collision() -> None:
    """An effect ending exactly where another starts does not overlap it."""
    fake = FakeLiveXLights()
    fake.layers["Dmx MH1"] = [{} for _ in range(TWINKLR_LAYER_BASE + 1)]
    fake.layers["Dmx MH1"][TWINKLR_LAYER_BASE]["user"] = {
        "name": "DMX",
        "settings": "E_SLIDER_DMX1=200",
        "palette": "",
        "start_ms": 1000,
        "end_ms": 1500,
    }
    workflow = LiveInjectionWorkflow(fake, ownership=MemoryOwnershipStore())  # type: ignore[arg-type]

    result = await workflow.inject(
        (_effect(start=0, end=500), _effect(start=500, end=1000, settings="second"))
    )

    assert len(result.injected) == 2
    with pytest.raises(InjectionCollisionError, match="User-owned"):
        await workflow.inject((_effect(start=0, end=500), _effect(start=999, end=1001)))
    with pytest.raises(InjectionCollisionError, match="planned effects overlap"):
        await workflow.inject((_effect(start=0, end=501), _effect(start=500, end=900)))


@pytest.mark.anyio
async def test_injection_into_another_sequence_than_expected_is_refused_before_reading() -> None:
    fake = FakeLiveXLights()
    workflow = LiveInjectionWorkflow(fake, ownership=MemoryOwnershipStore())  # type: ignore[arg-type]

    with pytest.raises(InjectionError, match=r"other\.xsq"):
        await workflow.inject((_effect(),), expected_sequence=Path("/tmp/other.xsq"))

    assert fake.requests == ["getOpenSequence"]
