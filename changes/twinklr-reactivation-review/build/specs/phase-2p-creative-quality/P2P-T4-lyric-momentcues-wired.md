# P2P-T4 — Lyric MomentCues wired

Phase: 2P (Creative Quality, Measured) · Lane: S (schema/channel, serial) · Executor: opus · Verifier: opus · Depends on: P2P-T1

## Objective

Connect the one genuinely irreplaceable thing the LLM layer produces — lyric-moment
interpretation — to the light. Define `MomentCue` on the lyrics model, render real
fields (not phantom ones) into the moving-head planner prompt, thread cues through
schema-v2 into renderable events, and fix the two independent bugs that mean **no
prompt pack in this repository has ever delivered a few-shot example to a model**.

## Evidence & background

Findings: **CF-4** (shipped planner is lyric-blind), **P3-F5** (airtight),
**P3-F13** (few-shot never delivered; both bugs confirmed).
Sources: `changes/twinklr-reactivation-review/reviews/phases/llm-agents-and-planning.md`
§4.3, §10 (P3-F5, P3-F13), §12; `.../reviews/verification.md` "Phase 3".

### The three lyrics-blindness locks (quoted; verifier rated this airtight)

From `verification.md` "Phase 3":

> **F5** lyrics-blindness (three independent locks: `extra="forbid"` model,
> model-object passing, the phantom fields exist in exactly 4 `.j2` lines and no
> Python — the Lyric Context block renders one line: "Has Lyrics: Yes")

From the phase review §12:

> **P3-F5** (planner blind to lyrics) — three independent locks: the `extra="forbid"`
> model, model-object passing, and the phantom field names appearing in exactly four
> `.j2` lines and no Python. The Lyric Context block renders exactly one line:
> "Has Lyrics: Yes".

And the mechanism from P3-F5 itself:

> `moving_heads/prompts/planner/user.j2:106-113` reads
> `lyric_context.narrative_arc` and `lyric_context.key_moments[*].{section_id,
> description}`. `LyricContextModel` has neither (`lyrics/models.py:191` is
> `mood_arc`; `:212` is `key_phrases`). Grep-verified: both names occur only at those
> four `.j2` lines, nowhere in Python. The `is defined and` guards make the blocks
> render as nothing. `orchestrator.py:86` does pass a populated model. **The shipped
> moving-head planner is blind to lyric narrative context.** This must be fixed
> before Stage 2's resolving experiment, or the LLM arm is measured with a severed
> wire.

**Re-verified in this tree (2026-08-13):** `narrative_arc` and `key_moments` appear
at exactly four lines, all in
`packages/twinklr/core/agents/sequencer/moving_heads/prompts/planner/user.j2`
(:106, :107, :109, :111), and nowhere in Python. `LyricContextModel`
(`agents/audio/lyrics/models.py:170`) declares `model_config =
ConfigDict(extra="forbid")` at `:177`, `mood_arc` at `:191`, `story_beats` at `:207`,
`key_phrases` at `:212`. The guard pattern is `{% if lyric_context.narrative_arc is
defined and lyric_context.narrative_arc %}` — `StrictUndefined` does not fire on
`is defined`, so the block silently renders nothing.

Why all three locks matter for the fix: (1) `extra="forbid"` means you cannot simply
stuff `narrative_arc` into the model at runtime — it must be a declared field or the
model rejects it; (2) the orchestrator passes the **model object**, not a dict, so
Jinja attribute access resolves against real fields only; (3) the phantom names exist
only in templates, so no Python-side rename can fix it — the templates must change or
the model must gain those exact fields. Pick one direction and apply it consistently;
this spec's target is **rename the templates to the real fields, and add `MomentCue`
as a new real field**, not to rename the model to match a template typo.

### The two few-shot bugs (quoted)

From P3-F13:

> Two independent causes: `loader.py:86,201` looks only for `examples.jsonl`, so
> `audio_profile/prompts/audio_profile/examples/example_{1,2}.json` are never opened
> despite being listed in that pack's `pack.yaml`; and `async_runner.py:452-457`
> rebuilds the conversational request from `user_messages[-1]` only, dropping the
> example turns appended at `:221-222`. The only two packs with an `examples.jsonl`
> (`macro_planner/planner`, `group_planner/planner`) are both CONVERSATIONAL. The
> `group_planner` examples were verified schema-correct against
> `SectionCoordinationPlan` — real authoring effort that has never shipped.

And the verifier's amplification (§12):

> **P3-F13** (few-shot never delivered) — both bugs confirmed, and worse than the
> author stated: the LLM call logs assert a delivery that never happened.

Net effect, stated in §4.1: "**no prompt pack in this repository delivers few-shot
examples at runtime**".

**Re-verified in this tree:** `prompts/loader.py:86` and `:201` both hardcode
`examples_path = pack_dir / "examples.jsonl"`; `async_runner._call_conversational_async`
builds `user_messages = [m for m in messages if m["role"] == "user"]` and then
`user_message = user_messages[-1]["content"]`, passing only that single string to
`generate_json_with_conversation_async` — every example turn appended by
`_build_messages` is discarded.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- The shipped MH planner's Lyric Context block renders exactly one line:
  `**Has Lyrics**: Yes`. Nothing else about the lyrics reaches it.
- The lyrics agent produces `key_phrases[*].{text, timestamp_ms, emphasis,
  visual_hint}` and `story_beats[*]`, which reach the macro planner's prompt and the
  renderer not at all.
- No agent in the repository receives few-shot examples. The `group_planner` pack's
  34-message `examples.jsonl` (verified schema-correct) has never influenced a token,
  and the LLM call logs record a delivery that did not happen.
- `audio_profile/pack.yaml` lists `examples/example_1.json` and `example_2.json`,
  which the loader never opens (it looks only for `examples.jsonl`). `pack.yaml`
  itself is inert (P3-F15: the string `pack.yaml` appears in zero `.py` files).

## Target behavior

### 1. `MomentCue` on the lyrics model

Add a `MomentCue` model and a `moment_cues: list[MomentCue] | None` field to
`LyricContextModel`, derived from (or alongside) the existing `key_phrases` /
`story_beats`. Each cue carries at minimum: a stable `cue_id` (referenced by
`PlanSection` v2 per P2P-T1), a timestamp in ms, a section reference, an intensity
or emphasis, and the short text/visual hint. Constraints:

- `LyricContextModel` is `extra="forbid"` — the field must be declared, not injected.
- The model is a **response model**, so it inherits P2P-T1's strict-mode rules: all
  fields required (`X | null`, no defaults), `additionalProperties:false`, within the
  ceilings. Design `MomentCue` to those rules from the start.
- Cue timestamps are musical facts, not free-floating ms: they resolve against the
  BeatGrid (the one grid, per P1P-T4) at render time. Store ms; resolve at use.

### 2. Real fields in the MH planner prompt

Replace the four phantom lines with renders of fields that exist: `mood_arc`,
`key_phrases`, `story_beats`, and the new `moment_cues`. Remove `narrative_arc` and
`key_moments` from the tree entirely so the names cannot be resurrected by
copy-paste. Keep the `is defined` guards only where a field is genuinely optional —
prefer explicit `{% if lyric_context %}` over per-field `is defined`, since
`is defined` is precisely what made this defect silent.

### 3. Cues thread into schema-v2 events

`PlanSection` v2's MomentCue references (defined in P2P-T1) resolve to renderable
events: the planner names cue ids, and the renderer (P2P-T2's resolution layer)
places accent/shutter/color events at the cue's grid-resolved time. A referenced cue
id that does not exist is a validation error, not a silent drop — the whole point of
this task is that silent drops are how this defect survived.

### 4. Few-shot delivery fixed — both bugs

- **Loader**: accept the `examples/` directory form (`example_*.json`) in addition to
  `examples.jsonl`. Both discovery paths exist in `loader.py` (`:86` and `:201`) —
  fix both, they are separate code paths.
- **Conversational drop**: `_call_conversational_async` must deliver the example
  turns, not just `user_messages[-1]`. The provider's conversational surface takes a
  single `user_message` + `conversation_id`; delivering examples requires either
  seeding the conversation with the example turns before the real user message, or
  folding them into the first user message / system prompt. Choose one, document why,
  and make the choice observable in the call log.
- **Logging honesty**: the call logs currently "assert a delivery that never
  happened". After the fix, the logged example count must be the count actually sent.
  If a pack's examples are dropped for any reason, the log says so.

### Non-goals

- Making `pack.yaml` enforced (P3-F15 is a separate REMOVE-or-enforce decision; do
  not quietly build a pack.yaml reader here).
- Rewriting the lyrics agent's own prompt or its resolution order (SF-2 / P1P-T7).
- Sanitizing the lyric injection path (P3-F18 / CC-9) — real, shipped, and owned
  elsewhere. Note in the handoff that this task *increases* the amount of
  third-party lyric text reaching the planner prompt, which raises the priority of
  that fix.
- Display-side lyric wiring.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/agents/audio/lyrics/models.py` — `LyricContextModel`,
  `KeyPhrase`, `StoryBeat`; new `MomentCue`.
- `packages/twinklr/core/agents/audio/lyrics/prompts/lyrics/*.j2` — solicit cues.
- `packages/twinklr/core/agents/sequencer/moving_heads/prompts/planner/user.j2` —
  the four phantom lines (:106-113 region).
- `packages/twinklr/core/agents/sequencer/moving_heads/orchestrator.py` — passes the
  populated `LyricContextModel` today (`:86`); confirm it still does.
- `packages/twinklr/core/agents/prompts/loader.py` — `:86` and `:201` examples
  discovery.
- `packages/twinklr/core/agents/async_runner.py` —
  `_build_messages` (example turns appended) and `_call_conversational_async`
  (`user_messages[-1]`), plus `_build_logging_context` for the honest example count.
- `packages/twinklr/core/agents/sequencer/moving_heads/models.py` — the cue-reference
  field added by P2P-T1; this task adds the referential-integrity validation.

Sequencing constraints copied verbatim from the plan:

> - T1 and T9 both touch `agents/shared`+schemas: T1 lands first; T9 rebases.
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing (the tree will drift
>   as phases land) — specs cite symbol + file, with line numbers as hints only.

This task also depends on P2P-T1 for the cue-reference shape. If T1's reference shape
changed during review, rebase on it rather than defining a parallel one.

Cache interlock (fingerprint addendum): once P1P-T9 lands prompt-content hashing,
these prompt edits invalidate correctly. Before that, an unchanged fingerprint would
serve plans generated from the *old* prompt — the addendum names this defect
specifically as "directly masking the recommended prompt fixes (F5 lyric wiring,
F14 recommended_sections)". Verify P1P-T9 is merged; if not, hand-bump the affected
`cache_version` literals and say so in the handoff.

## Acceptance criteria

1. `narrative_arc` and `key_moments` do not appear anywhere in the repository.
2. The MH planner prompt, rendered against a fully populated `LyricContextModel`,
   contains the mood arc, key phrases, and moment cues — verified by asserting on the
   **rendered output**, not on the template source.
3. `MomentCue` exists on `LyricContextModel`, satisfies P2P-T1's strict-mode rules,
   and survives `model_validate_json` round-trip.
4. A `PlanSection` referencing an unknown `cue_id` fails validation with a clear
   message; a valid reference resolves to a grid-anchored event.
5. Few-shot examples are delivered: for a CONVERSATIONAL pack with examples, the
   provider receives them (asserted against a fake provider that records what it was
   handed), and the logged example count equals the delivered count.
6. The `audio_profile` pack's `examples/example_{1,2}.json` are loaded by the loader
   (or the files are deleted if the pack's examples are judged obsolete — decide
   explicitly; leaving them unloaded on disk recreates the defect).
7. **Golden-diff BEFORE/AFTER**: with lyrics absent, emitted settings strings are
   byte-identical to the P2P-T2 baseline. With a fixture plan carrying one MomentCue
   reference, the AFTER artifact contains an event at the cue's grid-resolved
   timestamp that BEFORE does not.
8. `make validate` check-only forms pass.

## Tests

TDD — failing first:

1. **`test_mh_planner_prompt_renders_lyric_context`** — the test P3-F34 says would
   have caught this class: render the pack against a fully populated context and
   assert the output contains the mood arc text and a cue's text. Extend the shared
   render-every-pack test introduced in P2P-T1.
2. `test_no_phantom_lyric_fields_in_tree` — a repo-level grep test asserting
   `narrative_arc`/`key_moments` are absent. Cheap, and it pins the exact regression.
3. `test_moment_cue_reference_integrity` — unknown cue id rejected; known cue id
   resolves.
4. `test_conversational_examples_are_delivered` — fake provider records the messages
   it received; assert the example turns are present. This is the assertion that
   would have caught P3-F13's second bug.
5. `test_loader_discovers_example_directory_form` — a pack with
   `examples/example_1.json` yields loaded examples.
6. `test_call_log_example_count_matches_delivery` — the honesty check.
7. Golden render tests for criterion 7.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/agents -q
uv run pytest -k "lyric or example or prompt_render" -q
uv run pytest -k golden -q
grep -rn "narrative_arc\|key_moments" packages/ tests/ ; test $? -eq 1   # must find nothing
```

No paid API calls. A single LOCAL-ONLY live-LLM smoke run (one song, one planner
call) is permitted to confirm the planner's output references cues — budget: **one
song, ≤10 LLM calls**. Not required for merge.

## Effort & risk

**M.** Main risk: the conversational few-shot fix. The provider's conversation
surface takes one user message, so "deliver the examples" is a design choice with a
cost — seeding a conversation costs turns and tokens; folding examples into the
system prompt changes caching behavior. Mitigation: choose the cheapest correct
option, document it in the runner docstring, and pin it with the fake-provider test
so a future refactor cannot silently re-drop them. Second risk: re-landing the same
defect class in a new place — every new prompt field must be covered by the
rendered-output test, not just by the template diff.

## Implementation handoff — 2026-08-14 (pending independent verification)

### Implemented contract

- `MomentCue` is a strict response-compatible lyrics model. Lyrics validation rejects
  timestamps outside the song duration, unknown section ids, timestamps outside the
  cue's canonical section window, and populated cues when `has_lyrics` is false.
- Moving-head plans join lyric cues to the audio profile by unique
  `SongSectionRef.section_id`; repeatable display names remain presentation data. A
  legacy display-name reference is canonicalized only when it identifies exactly one
  section. Repeated names are rejected rather than guessed.
- A plan normalizer runs after every planner response, including revisions, and before
  heuristic validation or judging. It canonicalizes section ids, validates each
  referenced cue against its authoritative song-section interval, and then binds
  shutter/gobo cue events to the nearest authoritative `BeatGrid` position. Equal
  distance ties select the earlier beat. Invalid endpoint input is rejected before
  snapping, so clamping cannot legitimize it.
- The moving-head planner prompt renders real lyrics fields (`mood_arc`,
  `story_beats`, `key_phrases`, and `moment_cues`). The fictional
  `narrative_arc`/`key_moments` fields were removed. Prompt-content and response-schema
  identities already participate in the cache fingerprint. In addition, the lyrics
  and moving-head pipeline stages explicitly bump their cache versions from 1 to 2:
  v1 lyrics artifacts bypassed the new duration/section checks on identity extraction,
  and v1 moving-head artifacts bypassed section canonicalization and BeatGrid binding
  on cached extraction. A same-fingerprint v1 artifact is therefore a cache miss under
  the T4 stages rather than being legitimized by model-only deserialization.
- Prompt loading supports both `examples.jsonl` and the declared
  `examples/example_*.json` directory form. Conversational agents fold the example
  turns into the delivered request in order, and call logging records the count that
  was actually delivered. `pack.yaml` remains deliberately inert per the non-goal.

### Privacy and prompt-injection residual

This task deliberately increases the amount of raw third-party lyric material sent to
the moving-head planner: lyric text, story-beat descriptions, key phrases, cue text,
and visual hints now cross that LLM boundary. No lyric sanitization, delimiter
escaping, or instruction/data isolation was added here. Malicious lyrics can therefore
inject prompt-like text or imitate the prompt's delimiters. That residual is the
existing **P3-F18 / CC-9** trust-boundary finding; this wider live data path raises its
priority for the owning Phase 3 security work. It is not silently treated as resolved
by T4.

### Owner-gated evidence still pending

No paid provider call was made. The optional LOCAL-ONLY lyric-aware planner smoke run
remains owner-gated and is not merge evidence. Independent verification is still
required; this author handoff is not approval.
