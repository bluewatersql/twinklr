"""`twinklr show` end to end on the legacy renderer, on a layout whose groups are not
named for their zones: the command writes its sequence, trace and evaluation manifest
and exits 0. Recorded planners stand in for every provider-backed stage."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.golden.harness import RIGS, build_fixture_group
import tests.integration.test_combined_show_pipeline as legacy
from twinklr.cli.show_cmd import run_show_pipeline_async
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.definition import PipelineDefinition
from twinklr.core.pipeline.show_wiring import CombinedShowWiring, prepare_combined_show_pipeline
from twinklr.core.reporting.evaluation.show_manifest import load_show_evaluation_manifest
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.utils.formatting import clean_audio_filename


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_show_on_a_layout_with_zone_aliases_writes_its_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    members = ",".join(f"Dmx MH{index}" for index in range(1, 5))
    layout_path = tmp_path / "xlights_rgbeffects.xml"
    layout_path.write_text(
        f"""<xrgb>
  <models>
    <model name="Dmx MH1" DisplayAs="Dmx" />
    <model name="Dmx MH2" DisplayAs="Dmx" />
    <model name="Dmx MH3" DisplayAs="Dmx" />
    <model name="Dmx MH4" DisplayAs="Dmx" />
    <model name="Mega Tree" DisplayAs="Tree 360" parm1="16" parm2="50" />
    <model name="Arch 1" DisplayAs="Arches" parm1="1" parm2="50" />
  </models>
  <modelGroups>
    <modelGroup name="GROUP - MOVING HEADS" models="{members}" />
    <modelGroup name="Yard Arches" models="Arch 1" />
  </modelGroups>
</xrgb>""",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "fixture_config.json"
    fixture_path.write_text(
        build_fixture_group(RIGS["mh4_shutter_in_window"]).model_dump_json(), encoding="utf-8"
    )
    job_path = tmp_path / "job_config.json"
    job_path.write_text(JobConfig().model_dump_json(), encoding="utf-8")
    audio_path = tmp_path / "combined-fixture.wav"
    audio_path.write_bytes(b"synthetic audio")

    def recorded(**kwargs: Any) -> CombinedShowWiring:
        wiring = prepare_combined_show_pipeline(
            **{**kwargs, "available_templates": ["sweep_lr_fan_hold"]}
        )
        assert {entry.choreo_id for entry in wiring.xlights_mapping.entries} > {
            group.id for group in wiring.choreo_graph.groups
        }, "the layout maps a zone alias the graph has no group for"
        mh_id = next(iter(wiring.moving_head_target_ids))
        plan = ChoreographyPlan(
            sections=[
                PlanSection(
                    section_name="drop",
                    start_bar=1,
                    end_bar=2,
                    template_id="sweep_lr_fan_hold",
                    intensity=Intensity.SMOOTH,
                )
            ],
            overall_strategy="fixture",
        )
        stages = {
            "profile": legacy._FixtureStage("profile", object()),
            "lyrics": legacy._FixtureStage("lyrics", object()),
            "macro": legacy._MacroFixtureStage("macro", legacy._macro(mh_id)),
            "groups": legacy._FixtureStage("groups", legacy._section_plan()),
            "holistic": legacy._PassInputStage("holistic"),
            "holistic_corrector": legacy._PassInputStage("holistic_corrector"),
            "moving_heads": legacy._FixtureStage("moving_heads", plan),
        }
        return replace(
            wiring,
            pipeline=PipelineDefinition(
                name=wiring.pipeline.name,
                stages=[
                    replace(stage, stage=stages[stage.id]) if stage.id in stages else stage
                    for stage in wiring.pipeline.stages
                ],
            ),
        )

    bundle = SimpleNamespace(
        features={
            "tempo_bpm": 109.0,
            "beats_s": [0.0, 0.5, 1.1, 1.6, 2.2, 2.7, 3.3, 3.8, 4.4],
            "bars_s": [0.0, 2.2, 4.4],
            "duration_s": 4.4,
            "assumptions": {"beats_per_bar": 4},
        },
        timing=SimpleNamespace(duration_ms=4_400),
        lyrics=None,
        phonemes=None,
        audio_path=str(audio_path),
        metadata=None,
    )
    analyzer = MagicMock()
    analyzer.analyze = AsyncMock(return_value=bundle)
    analyzer.aclose = AsyncMock()
    local = AppConfig(
        llm_provider="ollama", llm_base_url="http://127.0.0.1:11434/v1", llm_api_key=""
    )
    with (
        patch("twinklr.cli.show_cmd.load_app_config", return_value=local),
        patch("twinklr.cli.show_cmd.prepare_combined_show_pipeline", side_effect=recorded),
        patch("twinklr.core.audio.analyzer.AudioAnalyzer", return_value=analyzer),
    ):
        exit_code = await run_show_pipeline_async(
            audio_path=audio_path,
            layout_path=layout_path,
            fixture_config_path=fixture_path,
            output_dir=tmp_path / "out",
            app_config_path=None,
            job_config_path=job_path,
        )

    assert exit_code == 0
    song_name = clean_audio_filename(audio_path.stem)
    xsq_path = tmp_path / "out" / song_name / f"{song_name}_twinklr_show.xsq"
    manifest = load_show_evaluation_manifest(Path(f"{xsq_path}.evaluation.json"))
    assert manifest.capability.cross_part_applicable
