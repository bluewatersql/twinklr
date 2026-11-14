"""The opt-in physical moving-head renderer end to end: plan to delivered `.xsq` (P1.6).

A synthetic two-head rig (16-bit pan/tilt, shutter on channel 17, the second head
inverted) plays the test-only `p1_linear_reveal` template over P0's variable-tempo grid,
moved 15 ms off the frame grid so every musical cue is quantized and the song's last
cue runs past its last whole frame. Everything is in memory or under `tmp_path`: no
audio, provider, owner data or xLights.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise
import json
from pathlib import Path
from typing import Any

import pytest

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from tests.support.mh_physical import (
    BUILTIN_TEMPLATE_COUNT,
    PHYSICAL_INITIAL_STATE,
    SUBSET_TEMPLATE_ID,
    TEMPLATE_ID,
    assert_honest_transactions,
    physical_grid,
    physical_job,
    physical_plan,
    physical_rig,
    physical_test_templates,
)
from twinklr.cli.main import build_run_pipeline
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.caching import derive_session_id
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup, InitialFixtureState
from twinklr.core.config.models import AppConfig, JobConfig, TransitionConfig
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import RenderLock
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.delivery import DeliveryRollbackError
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    PhysicalOutputError,
    encode_fixture_frames,
    frame_times,
)
from twinklr.core.sequencer.moving_heads.pipeline import PhysicalRenderError, RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import load_builtin_templates
from twinklr.core.sequencer.moving_heads.templates.library import REGISTRY
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


@pytest.fixture
def physical_templates() -> Iterator[None]:
    with physical_test_templates():
        yield


def _pipeline(
    output_path: Path | None,
    *,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
    template_id: str = TEMPLATE_ID,
    **kwargs: Any,
) -> RenderingPipeline:
    return RenderingPipeline(
        choreography_plan=physical_plan(template_id),
        beat_grid=physical_grid(),
        fixture_group=rig or physical_rig(),
        job_config=job or physical_job(),
        output_path=output_path,
        media_file="song.wav",
        **kwargs,
    )


def _decoded_frames(xsq_path: Path) -> dict[str, dict[int, dict[int, int]]]:
    """Per model, every frame the written `.xsq`'s constant DMX effects cover."""
    sequence = XSQParser().parse(xsq_path)
    decoded: dict[str, dict[int, dict[int, int]]] = {}
    for element in sequence.element_effects:
        frames = decoded.setdefault(element.element_name, {})
        for layer in element.layers:
            for effect in layer.effects:
                assert effect.effect_type == "DMX" and effect.ref is not None
                settings = sequence.effect_db.get(effect.ref)
                assert settings is not None
                values = {
                    int(key.removeprefix("E_SLIDER_DMX")): int(value)
                    for key, value in (item.split("=", 1) for item in settings.split(","))
                    if key.startswith("E_SLIDER_DMX")
                }
                for time_ms in range(effect.start_time_ms, effect.end_time_ms, EFFECT_GRID_MS):
                    assert time_ms not in frames, f"{element.element_name} doubled at {time_ms}"
                    frames[time_ms] = values
    return decoded


def _word(frame: dict[int, int], coarse: int, fine: int) -> int:
    return frame[coarse] << 8 | frame[fine]


def _cues(segments: list[Any]) -> list[Any]:
    return [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]


def test_physical_sequence_round_trips_through_the_written_xsq(
    tmp_path: Path, physical_templates: None
) -> None:
    """Decoded `.xsq` frames equal the encoded frames: complete, carried, channel 17."""
    output = tmp_path / "show.xsq"
    pipeline = _pipeline(output)
    segments = pipeline.render()

    assert pipeline.artifacts is not None
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "show.audiosections.xtiming",
        "show.xmap",
        "show.xsq",
        "show.xsq.trace.json",
    ]
    rig = physical_rig()
    models = {f.fixture_id: f.xlights_model_name for f in rig.expand_fixtures()}
    encoded: dict[str, dict[int, dict[int, int]]] = {}
    for frame in pipeline.frames:
        encoded.setdefault(models[frame.fixture_id], {})[frame.time_ms] = dict(frame.channels)

    decoded = _decoded_frames(output)
    assert decoded == encoded
    # Full heads in rig order, in the sequence and in the mapping hint.
    assert list(decoded) == ["Dmx MH1", "Dmx MH2"]
    assert pipeline.artifacts.model_names == ("Dmx MH1", "Dmx MH2")

    times = frame_times(int(physical_grid().duration_ms))
    footprint = list(range(1, 19))
    for frames in decoded.values():
        assert sorted(frames) == list(times)
        assert all(sorted(frame) == footprint for frame in frames.values())

    # Each cue reveals on its quantized frame: shutter open (byte 8) on channel 17,
    # full dimmer, pan at the start of its 90° move; outside the cues the head is
    # commanded dark through its closed byte 64 or a zero dimmer.
    cue_frames = {t for t in times if 1020 <= t < 2020 or 2820 <= t < 3600}
    for fixture in rig.expand_fixtures():
        profile = fixture.config.physical_profile
        assert profile is not None
        frames = decoded[fixture.xlights_model_name]
        pan = profile.axes["pan"]
        assert _word(frames[1020], 1, 2) == pan.dmx_word(-45.0)
        assert _word(frames[2820], 1, 2) == pan.dmx_word(-45.0)
        assert {frames[t][17] for t in cue_frames} == {8}
        assert {frames[t][5] for t in cue_frames} == {255}
        for t in sorted(set(times) - cue_frames):
            assert frames[t][17] == 64 or frames[t][5] == 0, (fixture.fixture_id, t)
    # The inverted head's words are the complement of the plain head's.
    assert _word(decoded["Dmx MH2"][1020], 1, 2) == 0xFFFF - _word(decoded["Dmx MH1"][1020], 1, 2)
    # A move across a coarse-byte boundary reconstructs without a carry glitch.
    mh1 = [_word(decoded["Dmx MH1"][t], 1, 2) for t in range(1020, 2020, EFFECT_GRID_MS)]
    assert len({word >> 8 for word in mh1}) > 1
    assert all(later > earlier for earlier, later in pairwise(mh1))

    # The transaction pass is honest about every head's darkness, motion and reveal.
    job = physical_job()
    cues = _cues(segments)
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    result = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(times) * EFFECT_GRID_MS,
    )
    assert list(result.segments) == segments
    for fixture_id, profile in profiles.items():
        assert profile is not None
        assert_honest_transactions(
            result,
            cues,
            profile,
            InitialFixtureState.model_validate(PHYSICAL_INITIAL_STATE),
            fixture_id=fixture_id,
        )


def test_trace_records_identity_cue_timing_and_transactions(
    tmp_path: Path, physical_templates: None
) -> None:
    """The trace persists the render identity and the evidence behind it."""
    output = tmp_path / "show.xsq"
    pipeline = _pipeline(output)
    pipeline.render()
    trace = json.loads(Path(f"{output}.trace.json").read_text(encoding="utf-8"))
    render = trace["render"]

    assert render == pipeline.render_record | {"output": render["output"]}
    assert render["render_fingerprint"] == pipeline.fingerprint()
    assert render["policy"]["mode"] == "physical_v2"
    assert set(render["initial_states"]) == {"MH1", "MH2"}
    assert [f["fixture_id"] for f in render["fixtures"]] == ["MH1", "MH2"]
    assert len({f["profile_sha256"] for f in render["fixtures"]}) == 2
    assert set(render["template_sha256"]) == {TEMPLATE_ID}
    assert len(render["beat_grid_sha256"]) == 64
    assert render["encoder_version"] == "1"
    assert render["frame_grid"] == {
        "frame_ms": 20,
        "frame_count": 181,
        "song_duration_ms": 3615,
        "sequence_end_ms": 3620,
    }
    # The 15 ms lead-in before the first observed beat is inferred, and says so.
    assert [k["provenance"] for k in render["phase_boundaries"]] == ["adjacent_interval"]
    assert render["layout_check"] == "not_performed"
    assert [(d["fixture_id"], d["cue_ms"], d["status"]) for d in render["transactions"]] == [
        ("MH1", 1020, "feasible"),
        ("MH1", 2820, "feasible"),
        ("MH2", 1020, "feasible"),
        ("MH2", 2820, "feasible"),
    ]

    # Requested musical times and the frames they landed on; the last cue's end runs
    # past the song's last whole frame (3600 ms) and is truncated there without error.
    bounds = {
        (c["fixture_id"], c["kind"], c["requested_ms"]): c["actual_ms"]
        for c in render["quantized_cues"]
    }
    for fixture_id in ("MH1", "MH2"):
        assert bounds[(fixture_id, "segment_start", 1015)] == 1020
        assert bounds[(fixture_id, "segment_end", 2015)] == 2020
        assert bounds[(fixture_id, "segment_start", 2815)] == 2820
        assert bounds[(fixture_id, "segment_end", 3615)] == 3600
    assert all(c["kind"] != "cue" for c in render["quantized_cues"])

    # Measured, not bounded: the effect count, exact bytes and serialization time.
    measured = render["output"]
    assert measured["effect_count"] == trace["entry_count"]
    assert measured["xsq_bytes"] == output.stat().st_size
    assert measured["serialization_ms"] >= 0


def test_subset_output_keeps_every_head_in_rig_order(
    tmp_path: Path, physical_templates: None
) -> None:
    """A template targeting only MH2 still emits MH1, parked dark, first."""
    output = tmp_path / "show.xsq"
    pipeline = _pipeline(output, template_id=SUBSET_TEMPLATE_ID)
    pipeline.render()

    decoded = _decoded_frames(output)
    assert list(decoded) == ["Dmx MH1", "Dmx MH2"]
    assert all(frame[17] == 64 or frame[5] == 0 for frame in decoded["Dmx MH1"].values())
    assert decoded["Dmx MH2"][1020][17] == 8


def test_locks_are_honored_in_the_delivered_output(
    tmp_path: Path, physical_templates: None
) -> None:
    """A pan lock inside a cue delivers the cue's own bytes in the locked frames; the same
    lock over a dark reposition the head needs is a conflict that delivers nothing."""
    inside = RenderLock(
        start_ms=1100, end_ms=1300, fixture_ids=("MH1",), channels=(ChannelName.PAN,)
    )
    output = tmp_path / "show.xsq"
    segments = _pipeline(output, locks=(inside,)).render()

    profile = physical_rig().expand_fixtures()[0].config.physical_profile
    assert isinstance(profile, FixtureCapabilities)
    cues = [cue for cue in _cues(segments) if cue.fixture_id == "MH1"]
    alone = {
        frame.time_ms: dict(frame.channels)
        for frame in encode_fixture_frames(cues, profile, frame_times_ms=frame_times(3615))
    }
    delivered = _decoded_frames(output)["Dmx MH1"]
    for time_ms in range(1100, 1300, EFFECT_GRID_MS):
        assert (delivered[time_ms][1], delivered[time_ms][2]) == (
            alone[time_ms][1],
            alone[time_ms][2],
        )
    result = plan_prepositions(
        _cues(segments),
        {f.fixture_id: f.config.physical_profile for f in physical_rig().expand_fixtures()},  # type: ignore[misc]
        initial_states=physical_job().moving_heads.initial_states,
        locks=(inside,),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=3620,
    )
    assert list(result.segments) == segments
    assert_honest_transactions(
        result,
        _cues(segments),
        profile,
        InitialFixtureState.model_validate(PHYSICAL_INITIAL_STATE),
        locks=(inside,),
    )

    in_gap = RenderLock(
        start_ms=2040, end_ms=2100, fixture_ids=("MH1",), channels=(ChannelName.PAN,)
    )
    with pytest.raises(PhysicalRenderError, match="MH1 cue at 2820 ms: lock_conflict"):
        _pipeline(tmp_path / "gap" / "show.xsq", locks=(in_gap,)).render()
    assert not (tmp_path / "gap").exists()


def test_physical_identity_ignores_transitions_and_lock_order(physical_templates: None) -> None:
    """Neither changes a physical frame, so neither changes physical render identity."""
    first = RenderLock(
        start_ms=1100, end_ms=1200, fixture_ids=("MH1",), channels=(ChannelName.PAN,)
    )
    second = RenderLock(
        start_ms=2900,
        end_ms=3000,
        fixture_ids=("MH1", "MH2"),
        channels=(ChannelName.PAN, ChannelName.TILT),
    )
    reordered = second.model_copy(
        update={"fixture_ids": ("MH2", "MH1"), "channels": (ChannelName.TILT, ChannelName.PAN)}
    )
    base = _pipeline(None, locks=(first, second)).fingerprint()

    assert _pipeline(None, locks=(reordered, first)).fingerprint() == base
    no_transitions = physical_job().model_copy(
        update={"transitions": TransitionConfig(enabled=False, default_duration_bars=2.0)}
    )
    assert _pipeline(None, job=no_transitions, locks=(first, second)).fingerprint() == base
    assert _pipeline(None, locks=(first,)).fingerprint() != base


def test_render_only_policy_edit_changes_render_identity_not_plan_identity(
    tmp_path: Path, physical_templates: None
) -> None:
    """Moving a head's start pose re-renders; it neither re-keys the planner's session
    nor changes what the planner is offered."""
    moved = {**PHYSICAL_INITIAL_STATE, "pan_deg": 10.0}
    edited = physical_job(initial_states={"MH1": moved, "MH2": PHYSICAL_INITIAL_STATE})
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"synthetic")
    app = AppConfig(llm_api_key="offline")

    assert _pipeline(None, job=edited).fingerprint() != _pipeline(None).fingerprint()
    assert derive_session_id(audio_path=audio, configs=(app, edited)) == derive_session_id(
        audio_path=audio, configs=(app, physical_job())
    )


def test_failed_publish_restores_the_prior_deliverable(
    tmp_path: Path, physical_templates: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A move that fails part way through publishing (here the `.xsq`, moved last, after
    the trace that differs) puts every file already moved back as it was."""
    output = tmp_path / "show.xsq"
    _pipeline(output).render()
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    original = Path.replace
    failures: list[Path] = []

    def replace_failing_once(self: Path, target: Any) -> Path:
        destination = Path(target)
        if (
            not failures
            and destination.parent == tmp_path
            and self.parent != tmp_path
            and destination.suffix == ".xsq"
        ):
            failures.append(destination)
            raise OSError("injected publish failure")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace_failing_once)
    with pytest.raises(OSError, match="injected publish failure"):
        _pipeline(output, job=physical_job(max_effects=999_999)).render()
    monkeypatch.undo()

    assert failures
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_failed_restore_keeps_the_set_aside_deliverable_and_names_it(
    tmp_path: Path, physical_templates: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If putting an earlier file back also fails, the staging directory holding it is
    kept, never deleted, and the error names where it is."""
    output = tmp_path / "show.xsq"
    _pipeline(output).render()
    prior_trace = Path(f"{output}.trace.json").read_bytes()

    original = Path.replace

    def replace_failing(self: Path, target: Any) -> Path:
        destination = Path(target)
        moving_new_xsq = destination == output and ".replaced" not in self.parts
        restoring_trace = ".replaced" in self.parts and self.name.endswith(".trace.json")
        if moving_new_xsq or restoring_trace:
            raise OSError(f"injected failure moving {self.name}")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace_failing)
    with pytest.raises(DeliveryRollbackError) as raised:
        _pipeline(output, job=physical_job(max_effects=999_999)).render()
    monkeypatch.undo()

    kept = raised.value.kept_dir
    assert str(kept) in str(raised.value)
    assert (kept / f"{output.name}.trace.json").read_bytes() == prior_trace
    assert not Path(f"{output}.trace.json").exists()


def test_step_starting_in_the_last_partial_frame_is_dropped_with_a_record(
    physical_templates: None,
) -> None:
    """A step that starts inside the song's final partial frame has no frame to play; it
    is dropped, recorded in the trace, and the render goes on."""
    grid = physical_grid()
    beats = [beat for beat in grid.beat_boundaries if beat <= 2815.0]
    short = grid.model_copy(
        update={
            "beat_boundaries": beats,
            "eighth_boundaries": BeatGrid._calculate_eighth_boundaries(beats),
            "sixteenth_boundaries": BeatGrid._calculate_sixteenth_boundaries(beats),
            "duration_ms": 2825.0,
        }
    )
    pipeline = RenderingPipeline(
        choreography_plan=physical_plan(),
        beat_grid=short,
        fixture_group=physical_rig(),
        job_config=physical_job(),
        output_path=None,
    )
    pipeline.render()

    assert pipeline.render_record is not None
    dropped = pipeline.render_record["dropped_cues"]
    assert sorted((d["fixture_id"], d["requested_start_ms"]) for d in dropped) == [
        ("MH1", 2815),
        ("MH2", 2815),
    ]
    assert all(d["end_limit_ms"] == 2820 for d in dropped)
    assert {d["cue_ms"] for d in pipeline.render_record["transactions"]} == {1020}


def test_unchecked_models_are_reported(
    physical_templates: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Without a layout the model check cannot run; the render says so, not just the trace."""
    with caplog.at_level("WARNING"):
        _pipeline(None).render()

    assert "xLights model check was not performed" in caplog.text


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        pytest.param(
            {
                "locks": (
                    RenderLock(
                        start_ms=0,
                        end_ms=1000,
                        fixture_ids=("MH2",),
                        channels=(ChannelName.PAN, ChannelName.TILT),
                    ),
                )
            },
            PhysicalRenderError,
            "MH2 cue at 1020 ms: lock_conflict",
            id="transaction-lock-conflict",
        ),
        pytest.param(
            {"job": physical_job(max_effects=1)},
            PhysicalOutputError,
            "max_effects 1",
            id="effect-budget",
        ),
        pytest.param(
            {"job": physical_job(max_xsq_bytes=1000)},
            PhysicalOutputError,
            "max_xsq_bytes 1000",
            id="byte-budget",
        ),
        pytest.param(
            {"template_id": "sweep_lr_fan_hold"},
            PhysicalCompileError,
            "no movement.physical data",
            id="legacy-template",
        ),
        pytest.param(
            {
                "layout_models": [
                    Model(name="Dmx MH1", DisplayAs="DmxMovingHeadAdv", DmxChannelCount="18")
                ]
            },
            PhysicalOutputError,
            "MH2: model 'Dmx MH2' is not in the xLights layout",
            id="model-missing-from-layout",
        ),
    ],
)
def test_failure_delivers_nothing(
    tmp_path: Path,
    physical_templates: None,
    kwargs: dict[str, Any],
    error: type[Exception],
    message: str,
) -> None:
    """A refused compile, transaction, model or budget leaves no file at all."""
    with pytest.raises(error, match=message):
        _pipeline(tmp_path / "show.xsq", **kwargs).render()

    assert list(tmp_path.iterdir()) == []


def _dmx(name: str, **attributes: str) -> Model:
    """An xLights-2026.19-shaped DMX model; an attribute given as "" is left out."""
    merged = {"DisplayAs": "DmxMovingHeadAdv", "DmxChannelCount": "18", **attributes}
    return Model.model_validate(
        {"name": name, **{key: value for key, value in merged.items() if value}}
    )


@pytest.mark.parametrize(
    ("mh2", "message"),
    [
        pytest.param(
            {"DisplayAs": "Single Line", "StringType": "RGB Nodes"},
            "MH2: model 'Dmx MH2' is DisplayAs='Single Line', not DMX",
            id="not-dmx",
        ),
        pytest.param(
            {"StringType": "RGB Nodes"},
            "MH2: model 'Dmx MH2' has StringType='RGB Nodes', not single color",
            id="rgb-nodes",
        ),
        pytest.param(
            {"DmxChannelCount": "17"},
            "MH2: model 'Dmx MH2' has 17 channels by DmxChannelCount; profile "
            "'synthetic_spot' writes channels 1-18",
            id="too-few-channels",
        ),
        pytest.param(
            {"DmxChannelCount": ""},
            "MH2: model 'Dmx MH2' declares no channel count (DmxChannelCount or parm1)",
            id="channel-count-unknown",
        ),
        pytest.param(
            {"DmxChannelCount": "sixteen"},
            "MH2: model 'Dmx MH2' has DmxChannelCount='sixteen', not a channel count",
            id="channel-count-not-a-number",
        ),
        pytest.param(
            {"DmxChannelCount": "", "parm1": "17"},
            "MH2: model 'Dmx MH2' has 17 channels by parm1",
            id="parm1-fallback-too-few",
        ),
        pytest.param(
            {"DmxChannelCount": "17", "parm1": "48"},
            "MH2: model 'Dmx MH2' has 17 channels by DmxChannelCount",
            id="dmx-channel-count-wins-over-parm1",
        ),
    ],
)
def test_layout_check_refuses_a_model_the_mapping_cannot_drive(
    tmp_path: Path, physical_templates: None, mh2: dict[str, str], message: str
) -> None:
    """A model that is not a single-color DMX model wide enough for its profile's whole
    footprint never receives the physical channel mapping."""
    layout = [_dmx("Dmx MH1", StringType="Single Color White"), _dmx("Dmx MH2", **mh2)]
    with pytest.raises(PhysicalOutputError) as raised:
        _pipeline(tmp_path / "show.xsq", layout_models=layout).render()

    assert message in str(raised.value)
    assert raised.value.diagnostic.code == "unsupported_backend_channel"
    assert raised.value.diagnostic.fixture_id == "MH2"
    assert list(tmp_path.iterdir()) == []


def test_layout_check_passes_and_records_the_layout(
    tmp_path: Path, physical_templates: None
) -> None:
    """A layout whose models fit is checked and its content hash recorded, as evidence;
    it is not render identity, because it cannot change a byte. MH1 declares only the
    `parm1` fallback; MH2 declares both, and its `DmxChannelCount` wins over `parm1`."""
    layout = [
        _dmx("Dmx MH1", DmxChannelCount="", parm1="18"),
        _dmx("Dmx MH2", StringType="Single Color White", DmxChannelCount="48", parm1="4"),
    ]
    output = tmp_path / "show.xsq"
    pipeline = _pipeline(output, layout_models=layout, layout_sha256="ab" * 32)
    pipeline.render()

    trace = json.loads(Path(f"{output}.trace.json").read_text(encoding="utf-8"))["render"]
    assert (trace["layout_check"], trace["layout_sha256"]) == ("performed", "ab" * 32)
    assert pipeline.fingerprint() == _pipeline(None).fingerprint()
    plain = tmp_path / "plain" / "show.xsq"
    _pipeline(plain).render()
    assert output.read_bytes() == plain.read_bytes()


def test_a_layout_changes_nothing_in_a_legacy_render(tmp_path: Path) -> None:
    """Legacy renders ignore the layout: the same bytes, trace and identity."""
    rig = build_fixture_group(RIGS["mh4_minimal"])
    layout = [_dmx(f"Dmx MH{index}", DisplayAs="Single Line") for index in range(1, 5)]

    def render(output: Path, **kwargs: Any) -> str:
        pipeline = RenderingPipeline(
            choreography_plan=build_plan(),
            beat_grid=build_beat_grid(),
            fixture_group=rig,
            job_config=JobConfig(),
            output_path=output,
            media_file="song.wav",
            **kwargs,
        )
        pipeline.render()
        return pipeline.fingerprint()

    with_layout = render(tmp_path / "a" / "show.xsq", layout_models=layout, layout_sha256="cd" * 32)
    without = render(tmp_path / "b" / "show.xsq")

    assert with_layout == without
    for name in ("show.xsq", "show.xsq.trace.json", "show.xmap"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_failed_removal_during_rollback_keeps_the_staging_directory(
    tmp_path: Path, physical_templates: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a newly placed file cannot be removed while rolling back, the earlier files
    are still put back, the staging directory is kept and the error names it."""
    output = tmp_path / "show.xsq"
    _pipeline(output).render()
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    original_replace, original_unlink = Path.replace, Path.unlink

    def replace_failing(self: Path, target: Any) -> Path:
        if Path(target) == output and ".replaced" not in self.parts:
            raise OSError("injected failure moving the new .xsq")
        return original_replace(self, target)

    def unlink_failing(self: Path, missing_ok: bool = False) -> None:
        if self == Path(f"{output}.trace.json"):
            raise OSError("injected failure removing the new trace")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "replace", replace_failing)
    monkeypatch.setattr(Path, "unlink", unlink_failing)
    with pytest.raises(DeliveryRollbackError) as raised:
        _pipeline(output, job=physical_job(max_effects=999_999)).render()
    monkeypatch.undo()

    assert raised.value.kept_dir.is_dir()
    assert str(raised.value.kept_dir) in str(raised.value)
    assert "show.xsq.trace.json" in str(raised.value)
    after = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert after == before
    assert raised.value.kept_dir.parent.parent == tmp_path


def test_calibration_change_changes_render_identity_not_plan_identity(
    tmp_path: Path, physical_templates: None
) -> None:
    """Recalibrating one head's pan re-renders it; the planner sees the same rig."""
    base, recalibrated = physical_rig(), physical_rig(mh1_pan_max=250.0)

    assert (
        _pipeline(None, rig=recalibrated).fingerprint() != _pipeline(None, rig=base).fingerprint()
    )

    def planner_inputs(rig: FixtureGroup) -> tuple[Any, ...]:
        pipeline, graph, _ = build_run_pipeline(
            fixture_group=rig,
            job_config=physical_job(),
            available_templates=[TEMPLATE_ID],
            xsq_output_path=tmp_path / "show.xsq",
            fixture_config_path=tmp_path / "fixture_config.json",
        )
        (stage,) = [s.stage for s in pipeline.stages if s.id == "moving_heads"]
        assert isinstance(stage, MovingHeadStage)
        # The planner's cache key reads the rig only through these.
        return stage.fixture_count, stage.fixture_groups, graph.model_dump(mode="json")

    assert planner_inputs(recalibrated) == planner_inputs(base)


def test_test_template_leaves_the_shared_registry_at_its_builtins() -> None:
    """Loading the test template for a test never leaks it into the catalog."""
    load_builtin_templates()
    assert len(REGISTRY.list_all()) == BUILTIN_TEMPLATE_COUNT
    with physical_test_templates():
        assert len(REGISTRY.list_all()) == BUILTIN_TEMPLATE_COUNT + 2
    assert len(REGISTRY.list_all()) == BUILTIN_TEMPLATE_COUNT
    assert TEMPLATE_ID not in {info.template_id for info in REGISTRY.list_all()}


def test_test_template_setup_failure_leaves_the_registry_at_its_builtins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The subset variant failing to register must not leak the template loaded first."""
    load_builtin_templates()
    register = REGISTRY.register_document

    def fail_on_the_variant(document: Any, **kwargs: Any) -> bool:
        if document.template.template_id == SUBSET_TEMPLATE_ID:
            raise ValueError("injected registration failure")
        return register(document, **kwargs)

    monkeypatch.setattr(REGISTRY, "register_document", fail_on_the_variant)
    with pytest.raises(ValueError, match="injected"), physical_test_templates():
        pass
    monkeypatch.undo()
    assert len(REGISTRY.list_all()) == BUILTIN_TEMPLATE_COUNT
