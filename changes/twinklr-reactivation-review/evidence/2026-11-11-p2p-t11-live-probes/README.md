---
type: change
status: active
area: engineering
created: 2026-11-11
updated: 2026-11-11
---

# P2P-T11 live probe and strict-mode suite — 2026-11-11

> Raw `*.log` files named here sit beside this README in the owner's checkout but are
> gitignored by the repository's no-logs rule. The tables in this README reproduce their
> results.

Run per [runbook 05 §6.2](../../runbooks/05-phase-2p-and-3-live-evidence.md). Authority:
[P2P-T11 spec](../../build/specs/phase-2p-creative-quality/P2P-T11-structured-outputs.md).

| Field | Value |
|---|---|
| Window (UTC) | 2026-11-11T19:49:58Z – 19:51:31Z |
| Git SHA | `88b855ff34ac8fa89d322c064bec7ce401495cef` (clean tree) |
| Key | public OpenAI; free `/v1/models` check returned 200 and listed `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` |
| Requests | 9 HTTP requests in total: probe 1, strict suite 8. Provider retries and fallback are disabled, so there were no extra requests. |
| Spend | No ledger in this harness. All calls ran at `reasoning_effort=low` with `max_output_tokens` ≤ 4,000, which is well inside the $2.00 T11 cap. Take exact figures from the OpenAI usage dashboard for the window above. |
| Logs | `probe.log`, `strict-suite.log` |

## Probe: does `gpt-5.6-sol` accept `json_object`?

**Accepted.** `test_json_object_probe_on_gpt_5_6_sol` passed (1 request, 3.8 s). The
response was `{"ok": true}` with `structured_output_mode == "json_object"`.

## Strict mode per role (8 requests)

| Role | Result | Notes |
|---|---|---|
| holistic_corrector | PASS | |
| holistic_judge | PASS | |
| moving_head_planner | PASS | |
| moving_head_judge | PASS | The prompt told the model to omit `score`; strict mode kept it. |
| macro_planner | PASS | |
| **lyrics** | **FAIL: real defect** | HTTP 400 `invalid_json_schema`: `LyricContextModel` … `timestamp_range` "array schema missing items". |
| audio_profile | INCONCLUSIVE (harness budget) | `incomplete: max_output_tokens` after 29.6 s. The server accepted the schema and generated output, but the test caps output at 4,000 tokens (the spec sets 50,000). |
| group_planner | INCONCLUSIVE (harness budget) | Same truncation, after 30.7 s. |

### Lyrics defect: root cause and fix

`StoryBeat.timestamp_range: tuple[int, int]` makes Pydantic emit
`{"type":"array","prefixItems":[…],"minItems":2,"maxItems":2}` with no `items`, and
OpenAI strict mode rejects that shape. The offline strict validator did not check array
`items`, so no unit test caught it. The 2026-08 live MH run did not catch it either,
because the lyrics stage was skipped there (condition not met). Any song that reaches
the lyrics agent fails at its first request.

The same offline audit found a second latent strict-schema defect, in the P3-T8 show
judge. In `ShowVisionRubricResponse`, `VisualCriterionScore.score` had a default, so the
schema did not mark it required. `strict_json_schema` therefore raised before any request.
Neither vision judge was in the strict-schema test registry.

Fix (branch `fix/strict-schema-live-findings`):

- The strict normalizer rewrites homogeneous tuples to `items` and keeps
  `minItems`/`maxItems`. It fails loudly on heterogeneous tuples.
- The validator now rejects any array without `items`, and `prefixItems` is listed as
  unsupported.
- `score` is required but nullable.
- Both judge specs are added to the strict-schema registry.
- New tests cover these cases, and they fail on the pre-fix code.

## Follow-up reruns (owner-approved live requests, 2026-11-11)

| Rerun | Git SHA | Requests | Result |
|---|---|---|---|
| lyrics, after the schema fix | `722c58d` | 1 | **PASS** in 3.8 s. The server accepted the tuple-normalized schema and the response validated (log: `lyrics-recheck.log`) |
| group_planner, cap raised to 16,000 (`TWINKLR_LIVE_STRICT_MAX_TOKENS`, `aef9139`) | `aef9139` | 1 | **PASS** in 2.9 s (log: `truncated-roles-rerun.log`) |
| audio_profile, cap raised to 16,000 | `aef9139` | 1 | **FAIL: runaway output.** Truncated again at `max_output_tokens` after 104 s (log: `truncated-roles-rerun.log`) |

Total live requests for T11 so far: 12 (probe 1, suite 8, reruns 3), each at
`reasoning_effort=low`.

**Strict-mode outcome: 7 of 8 roles PASS.** `audio_profile` is the only open role. The
server accepts its schema, but given "smallest plausible object" the model emits more
than 16,000 output tokens. That points to an unbounded array or open-ended string field
in `AudioProfileModel` that the model keeps filling, not to a schema rejection. No
further spend was made on it. Next step: an offline look at `AudioProfileModel`'s
unbounded fields (`maxItems` / `maxLength` coverage). Note that the real audio-profile
agent runs with `max_tokens` 50,000 and a full prompt pack, so this probe overstates the
risk.
