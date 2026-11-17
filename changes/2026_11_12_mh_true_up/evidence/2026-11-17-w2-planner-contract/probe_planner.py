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
a `ChoreographyPlan`, and passes what production runs after the provider returns: the
normaliser (`bind_lyric_moment_cues`), the production validator
(`create_validator_function`) and the advisory check (`unanswered_high_cues`). It also fails,
and says why, when the plan leaves a song section unplanned or gives a placeholder
reasoning or strategy, and prints a table of each section's song intent and each lyric
cue's answer. The dry run exits non-zero unless the schema would be sent enforced.

Offline (no request): `--replay FILE` runs that same post-provider path on the `response`
of a saved `--out` file, e.g. the 2026-11-17 probe 2 response.
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
from twinklr.core.agents.audio.profile.models import (  # noqa: E402
    PlannerHints as SectionHintsModel,
)
from twinklr.core.agents.audio.profile.models import SectionObjectives  # noqa: E402
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
    MIN_REASONING_CHARACTERS,
    create_validator_function,
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
from twinklr.core.sequencer.vocabulary.energy import EnergyTarget  # noqa: E402

# The synthetic song comes from the unit tests' builders. They are loaded at run time so
# the type checker does not pull the test modules into the package's strict check.
_builders = importlib.import_module("tests.unit.agents.sequencer.moving_heads.test_orchestrator")
create_test_audio_profile = _builders.create_test_audio_profile
create_test_macro_plan = _builders.create_test_macro_plan


MODEL = "claude-opus-5-5"
"""The model the 2026-11-12 schema probe measured."""


def synthetic_context() -> MovingHeadPlanningContext:
    """A synthetic 90 s, 120 BPM song with lyric moment cues and a macro plan.

    The unit tests' builders give its shape; its identity, objectives, mood and macro
    targets are written like a real song's, so the request does not read as a test
    fixture (the 2026-11-17 live response planned one section with placeholder
    reasoning for the fixture-named "Test Song"; whether the fixture wording invited it
    is a hypothesis this framing removes)."""
    profile = create_test_audio_profile()
    profile = profile.model_copy(
        update={
            "song_identity": profile.song_identity.model_copy(
                update={"title": "Lanterns on Juniper Lane", "artist": "The Hollow Pines"}
            ),
            "planner_hints": SectionHintsModel(
                section_objectives=[
                    SectionObjectives(
                        section_id="intro",
                        objectives=["Open softly; let the heads wake up over the piano."],
                    ),
                    SectionObjectives(
                        section_id="verse_1",
                        objectives=["Keep the verse restrained so the chorus can lift."],
                    ),
                    SectionObjectives(
                        section_id="chorus_1",
                        objectives=["The song's peak: full voices on 'light it up'."],
                    ),
                    SectionObjectives(
                        section_id="outro",
                        objectives=["Wind down to a single held chord and fade."],
                    ),
                ],
                avoid_patterns=["Strobing through the quiet intro"],
                emphasize_groups=[],
            ),
        }
    )
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
    lyrics = LyricContextModel(
        has_lyrics=True,
        vocal_coverage_pct=0.6,
        mood_arc="wistful → joyful → peaceful",
        moment_cues=cues,
    )
    templates = load_template_catalog()
    stage = MovingHeadStage(fixture_count=4, available_templates=templates)
    return MovingHeadPlanningContext(
        audio_profile=profile,
        lyric_context=lyrics,
        fixtures=FixtureContext(count=4, groups=[]),
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120.0, total_bars=45),
        available_templates=templates,
        macro_plan=_macro_plan(profile),
        template_descriptions=stage._build_template_descriptions(templates),
    )


def _macro_plan(profile):
    """The tests' macro plan with an energy arc and notes a real macro plan would carry."""
    plan = create_test_macro_plan(profile)
    targets = {
        "intro": (
            EnergyTarget.LOW,
            "Hold back; the heads are a soft glow under the opening piano.",
        ),
        "verse_1": (EnergyTarget.MED, "A gentle groove; leave room for the chorus."),
        "chorus_1": (EnergyTarget.PEAK, "The song's peak; the heads lead the lift on the hook."),
        "outro": (EnergyTarget.RELEASE, "Let the energy settle into a calm, warm close."),
    }
    sections = [
        section.model_copy(
            update={
                "energy_target": targets[section.section.section_id][0],
                "notes": targets[section.section.section_id][1],
            }
        )
        for section in plan.sections
    ]
    return plan.model_copy(update={"sections": sections})


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


def post_provider(
    context: MovingHeadPlanningContext, content: object, failures: list[str]
) -> ChoreographyPlan | None:
    """What production runs on a planner response, in its order (`AsyncAgentRunner`
    validation, then `IterationController`: normaliser, validator, advisory), plus the
    probe's own song-coverage checks; appends each failure and returns the plan."""
    try:
        plan = ChoreographyPlan.model_validate(content)
    except ValidationError as error:
        failures.append(f"the response does not validate: {error}")
        return None
    try:
        normalised = bind_lyric_moment_cues(
            plan, context.lyric_context, context.beat_grid, context.sections
        )
    except ValueError as error:
        failures.append(f"the normaliser rejected the plan: {error}")
        return None
    validator_errors = create_validator_function(context)(normalised)
    advisories = unanswered_high_cues(normalised, context.lyric_context, context.sections)

    song = context.for_prompt()["song_structure"]["sections"]
    planned = {section.section_id: section for section in normalised.sections}
    cues = context.lyric_context.moment_cues if context.lyric_context else []
    print()
    print(f"{'section':10} {'song bars':10} {'plan bars':10} song intent set")
    for entry in song:
        section = planned.get(entry["section_id"])
        bars = f"{entry['start_bar']}-{entry['end_bar']}"
        if section is None:
            print(f"{entry['section_id']:10} {bars:10} {'-':10} NOT PLANNED")
            continue
        print(
            f"{entry['section_id']:10} {bars:10} {section.start_bar}-{section.end_bar:<7} "
            f"{', '.join(section.set_intent_fields()) or '(none)'}"
        )
        print(f"{'':10} parts: {[part.template_id for part in section.parts]}")
        print(f"{'':10} events: {[event.describe() for event in section.events]}")
        print(f"{'':10} reasoning: {section.reasoning!r}")
    for section_id in planned.keys() - {entry["section_id"] for entry in song}:
        print(f"{section_id:10} {'-':10} not a song section")
    print()
    print(f"{'cue':14} {'emphasis':8} {'section':10} answer")
    for cue in cues:
        section = planned.get(cue.section_id)
        answers = [
            event.describe()
            for event in (section.events if section else [])
            if event.moment_cue_id == cue.cue_id
        ]
        answer = (
            "; ".join(answers)
            if answers
            else ("section not planned" if section is None else "no event")
        )
        print(f"{cue.cue_id:14} {cue.emphasis:8} {cue.section_id:10} {answer}")
    print()
    print("overall_strategy", repr(normalised.overall_strategy))
    print("repair_count", len(normalised.repairs))
    for repair in normalised.repairs:
        print("repair", repair.describe())
    print("unanswered_high_cues", advisories)
    print("validator_errors", validator_errors)

    unplanned = [entry["section_id"] for entry in song if entry["section_id"] not in planned]
    if unplanned:
        failures.append(f"song section(s) not planned: {', '.join(unplanned)}")
    placeholders = [
        name
        for name, text in [
            ("overall_strategy", normalised.overall_strategy),
            *((f"{s.section_id}.reasoning", s.reasoning) for s in normalised.sections),
        ]
        if len(text.strip()) < MIN_REASONING_CHARACTERS or len(text.split()) < 4
    ]
    if placeholders:
        failures.append(f"placeholder text in: {', '.join(placeholders)}")
    if validator_errors:
        failures.append(
            f"{len(validator_errors)} production validator error(s): "
            + " | ".join(validator_errors)
        )
    if advisories:
        failures.append(f"{len(advisories)} HIGH lyric cue(s) unanswered")
    return normalised


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--live", action="store_true", help="send the one paid request")
    parser.add_argument("--out", type=Path, help="write the response and plan here (JSON)")
    parser.add_argument(
        "--replay", type=Path, help="run the post-provider path on a saved --out file's response"
    )
    args = parser.parse_args()

    context = synthetic_context()
    messages = planner_messages(context)
    spec = get_planner_spec()
    describe_schema()
    if args.replay is not None:
        saved = json.loads(args.replay.read_text(encoding="utf-8"))
        print("replay", args.replay, "(no request sent)")
        failures: list[str] = []
        post_provider(context, saved["response"], failures)
        for failure in failures:
            print("PROBE FAILED:", failure)
        return 1 if failures else 0
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
    normalised = post_provider(context, response.content, failures)
    if normalised is not None and args.out is not None:
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
