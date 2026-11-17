# mypy: ignore-errors
# One-off evidence script: it builds test-style models with their defaults; the package's
# strict type check does not apply to it.
"""Probe the song-intent planner contract on Claude with one schema-enforced request.

Builds the real rendered moving-head planner prompt pack for a synthetic song (the unit
tests' four-section audio profile, three synthetic lyric moment cues, the tests' macro
plan, the family template catalog) and sends it as ONE
`AnthropicProvider.generate_json_async` call with the `ChoreographyPlan` response model,
so Claude compiles and enforces the schema. No owner media, layout or show is read.

Default: a dry run. It builds the exact Messages request the provider would send and
prints its size and the schema statistics; it calls nothing.

    uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w2-planner-contract/probe_planner.py

Paid (owner-authorized, minimum only; needs ANTHROPIC_API_KEY): add `--live`. It sends one
request with the production planner's reasoning effort and token budget, SDK retries off,
and prints the response's usage, the plan's song intent per section, the repair count and
each repair; with `--out FILE` it also writes the raw response and the normalised plan.
It exits non-zero unless the response was provider-enforced (`json_schema`), validates as
a `ChoreographyPlan`, and has no validator errors (the dry run: unless the schema would be
sent enforced).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from pathlib import Path
import sys
import time

from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue  # noqa: E402
from twinklr.core.agents.prompts import PromptPackLoader  # noqa: E402
from twinklr.core.agents.providers.anthropic import (  # noqa: E402
    AnthropicProvider,
    claude_json_schema,
    claude_schema_size,
)
from twinklr.core.agents.providers.errors import LLMProviderError  # noqa: E402
from twinklr.core.agents.schema_utils import (  # noqa: E402
    get_json_schema_example,
    response_schema_hash,
    strict_json_schema,
    strict_schema_stats,
)
from twinklr.core.agents.sequencer.moving_heads.context import (  # noqa: E402
    FixtureContext,
    MovingHeadPlanningContext,
)
from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (  # noqa: E402
    HeuristicValidator,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan  # noqa: E402
from twinklr.core.agents.sequencer.moving_heads.moment_cues import (  # noqa: E402
    bind_lyric_moment_cues,
    unanswered_high_cues,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator import (  # noqa: E402
    build_planner_variables,
)
from twinklr.core.agents.sequencer.moving_heads.specs import get_planner_spec  # noqa: E402
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage  # noqa: E402
from twinklr.core.agents.taxonomy_utils import inject_taxonomy  # noqa: E402
from twinklr.core.sequencer.moving_heads.templates.data_loader import (  # noqa: E402
    load_template_catalog,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid  # noqa: E402

# The synthetic song comes from the unit tests' builders. They are loaded at run time so
# the type checker does not pull the test modules into the package's strict check.
_builders = importlib.import_module("tests.unit.agents.sequencer.moving_heads.test_orchestrator")
create_test_audio_profile = _builders.create_test_audio_profile
create_test_macro_plan = _builders.create_test_macro_plan


MODEL = "claude-opus-5-5"
"""The model the 2026-11-12 schema probe measured."""


def synthetic_context() -> MovingHeadPlanningContext:
    """A synthetic 90 s, 120 BPM song with lyric moment cues and a macro plan."""
    profile = create_test_audio_profile()
    cues = [
        MomentCue(
            cue_id="verse-home",
            timestamp_ms=30_250,
            section_id="verse_1",
            emphasis="MED",
            text="find the way back home",
            visual_hint="A warm colour change as the line resolves.",
        ),
        MomentCue(
            cue_id="chorus-light",
            timestamp_ms=45_100,
            section_id="chorus_1",
            emphasis="HIGH",
            text="light it up",
            visual_hint="A bright hit on the downbeat.",
        ),
        MomentCue(
            cue_id="chorus-stars",
            timestamp_ms=60_400,
            section_id="chorus_1",
            emphasis="LOW",
            text="under the stars",
            visual_hint="A starry texture.",
        ),
    ]
    lyrics = LyricContextModel(has_lyrics=True, vocal_coverage_pct=0.6, moment_cues=cues)
    templates = load_template_catalog()
    stage = MovingHeadStage(fixture_count=4, available_templates=templates)
    return MovingHeadPlanningContext(
        audio_profile=profile,
        lyric_context=lyrics,
        fixtures=FixtureContext(count=4, groups=[]),
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=45),
        available_templates=templates,
        macro_plan=create_test_macro_plan(profile),
        template_descriptions=stage._build_template_descriptions(templates),
    )


def planner_messages(context: MovingHeadPlanningContext) -> list[dict[str, str]]:
    """The planner's first-iteration messages, rendered as `AsyncAgentRunner` renders
    them: developer, system, user."""
    spec = get_planner_spec()
    variables = {
        **spec.default_variables,
        **build_planner_variables(context),
        "learning_context": "",
        "response_schema": get_json_schema_example(spec.response_model),
    }
    loader = PromptPackLoader(base_path=REPO / "packages" / "twinklr" / "core")
    prompts = loader.load_and_render(spec.prompt_pack, inject_taxonomy(variables))
    return [
        {"role": role, "content": prompts[role]}
        for role in ("developer", "system", "user")
        if role in prompts
    ]


def describe_schema() -> None:
    schema = claude_json_schema(ChoreographyPlan)
    stats = strict_schema_stats(strict_json_schema(ChoreographyPlan))
    print("schema_sha256", response_schema_hash(ChoreographyPlan))
    print("claude_schema_size", claude_schema_size(schema))
    print("openai_strict_stats", stats)
    print("claude_schema_bytes", len(json.dumps(schema)))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--live", action="store_true", help="send the one paid request")
    parser.add_argument("--out", type=Path, help="write the response and plan here (JSON)")
    args = parser.parse_args()

    context = synthetic_context()
    messages = planner_messages(context)
    spec = get_planner_spec()
    describe_schema()
    for message in messages:
        print(f"message {message['role']:9} chars={len(message['content'])}")

    # The production planner's effort and token budget, so the probe measures what a run
    # sends; only the model is Claude's.
    request_kwargs = {
        "response_model": ChoreographyPlan,
        "reasoning_effort": spec.reasoning_effort,
        "max_tokens": spec.max_tokens,
        "allow_json_object_fallback": False,
    }
    provider = AnthropicProvider(api_key=None if args.live else "dry-run-not-sent")
    # One request only: no SDK retry may send a second, paid one.
    provider._sync_client = provider._sync_client.with_options(max_retries=0)
    provider._async_client = provider._async_client.with_options(max_retries=0)
    request = provider._build_request(messages, MODEL, None, dict(request_kwargs))
    params = request.params
    enforced = "format" in params.get("output_config", {})
    print("model", MODEL, "effort", spec.reasoning_effort, "max_tokens", params["max_tokens"])
    print("schema_enforced", enforced)
    print("request_bytes", len(json.dumps(params)))
    if not args.live:
        print("dry run: no request sent (add --live to send the one paid request)")
        return 0 if enforced else 1

    print("utc_start", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    started = time.time()
    try:
        response = await provider.generate_json_async(
            messages=messages, model=MODEL, **request_kwargs
        )
    except LLMProviderError as error:
        print("utc_end", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        print("PROBE FAILED: the provider refused the request:", error)
        return 1
    print("utc_end", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    mode = response.metadata.structured_output_mode
    print(
        f"seconds={time.time() - started:.1f} mode={mode} effort={spec.reasoning_effort} "
        f"finish={response.metadata.finish_reason} usage={response.metadata.token_usage}"
    )
    failures: list[str] = []
    if mode != "json_schema":
        failures.append(f"the response was not provider-enforced (mode {mode})")
    try:
        plan = ChoreographyPlan.model_validate(response.content)
    except ValidationError as error:
        failures.append(f"the response does not validate: {error}")
        plan = None
    if plan is not None:
        normalised = bind_lyric_moment_cues(
            plan, context.lyric_context, context.beat_grid, context.sections
        )
        validation = HeuristicValidator.from_context(context).validate(normalised)
        for section in normalised.sections:
            print(
                f"section {section.section_id}: parts={[p.template_id for p in section.parts]} "
                f"set={list(section.set_intent_fields())} "
                f"events={[event.describe() for event in section.events]}"
            )
        print("repair_count", len(normalised.repairs))
        for repair in normalised.repairs:
            print("repair", repair.describe())
        print(
            "unanswered_high_cues",
            unanswered_high_cues(normalised, context.lyric_context, context.sections),
        )
        print("validator_errors", validation.errors)
        if validation.errors:
            failures.append(f"{len(validation.errors)} validator error(s)")
        if args.out is not None:
            args.out.write_text(
                json.dumps(
                    {
                        "model": MODEL,
                        "effort": spec.reasoning_effort,
                        "response": response.content,
                        "plan": normalised.model_dump(mode="json"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print("wrote", args.out)
    for failure in failures:
        print("PROBE FAILED:", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
