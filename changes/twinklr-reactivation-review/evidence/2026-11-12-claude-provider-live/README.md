---
type: change
status: active
area: engineering
created: 2026-11-12
updated: 2026-11-12
---

# Claude provider — first live requests (2026-11-12)

This records the first live use of the Claude provider (`claude-opus-5-5`). The owner
approved live requests and asked for Claude on 2026-11-11. The successful pipeline run is
recorded in
[`evaluations/2026-11-12-claude-baseline-live-run/`](../../../../evaluations/2026-11-12-claude-baseline-live-run/README.md).

## Attempt 1: profile stage fails on schema compilation

| Field | Value |
|---|---|
| Window (UTC) | 2026-11-12T14:28:04Z – 14:28:45Z |
| Commit | `2be39df` |
| Command | runbook 05 §2 `twinklr run` on `Hey Come Look At My House.mp3`, Claude job config |
| Result | **FAIL**, 1/6 stages. `audio_profile`'s only request got HTTP 400 `The compiled grammar is too large, which would cause performance issues.` (`req_011CgyC6xQUr4xbnb9CMbfHT`). No tokens were generated. |
| Log | [attempt1-console-excerpt.log](attempt1-console-excerpt.log) |

The schema stayed within Anthropic's documented explicit limits (7 union parameters, 0
optional). The rejection comes from the internal grammar-size limit, which the
structured-outputs documentation describes but does not quantify.

## Schema probe: which response schemas Claude compiles

[`probe_schemas.py`](probe_schemas.py) (run with `PYTHONPATH=.` from the repository root
and `ANTHROPIC_API_KEY` set) sends each registered response schema once. Each request used
`effort: low`, `max_tokens: 16` and a one-line prompt. Window: 14:31:03Z – 14:31:30Z.
Log: [schema-probe.log](schema-probe.log).

| Accepted (8) | Rejected with `compiled grammar is too large` (5) |
|---|---|
| asset_prompt_enricher, lyrics, section_judge, holistic_judge, mh_judge, macro_judge, vision_judge, show_vision_judge | audio_profile, group_planner, holistic_corrector, mh_planner, macro_planner |

Each rejection came back in 0.3 s with the same message, so the outcome depends only on the
schema. Every planner schema fails; every judge, lyrics, enricher and vision schema
compiles. Probe spend was 23,188 input and 128 output tokens, about $0.10 at list price.

## Fix and rerun

Commit `f0ae0da` (`fix(providers): resend Claude requests prompt-only when the schema is
too complex`) mirrors the OpenAI strict-rejection fallback.

- On that 400, the provider resends once without `output_config.format`. The prompt pack's
  `response_schema` still carries the schema, and the runner validates and repairs the
  response as it does for any other.
- The rejected schema hash is remembered, so later calls skip the wasted request.
- Response metadata records `structured_output_mode="prompt_schema"` and
  `structured_output_fallback_reason="schema_too_complex"`.
- `AgentSpec.allow_json_object_fallback` (default `True`) now governs this fallback too.

The rerun at `f0ae0da` passed 6/6 stages. Three schemas fell back, every call validated
first time with 0 repairs, and spend was about $0.95; see the evaluation record.

## Open follow-ups

- The planner roles on Claude have no server-side schema guarantee and depend on
  validation and repair. Making the planner schemas compile would need fewer
  unions/nesting or a split into smaller requests. That is a design change for the owner
  to weigh, and this fix does not attempt it.
- On this run, macro iteration 1 used theme tags outside the taxonomy (`bold`, `festive`,
  and others). Heuristic validation caught them and iteration 2 passed. This is prompt
  adherence under prompt-only schemas, and worth watching over more runs.
