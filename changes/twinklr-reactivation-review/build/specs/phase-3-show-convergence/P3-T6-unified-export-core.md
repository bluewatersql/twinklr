# P3-T6 — Unified export core

Phase: 3 (Show Convergence / M3) · Lane: X (export unification) · Executor: opus ·
Verifier: opus · Depends on: P3-T2

## Objective

Twinklr has two independent `.xsq` writers that disagree about everything they share:
one deduplicates EffectDB entries and one does not, one declares a 20 ms frame grid
and quantizes to it while the other declares 50 ms and quantizes not at all, and they
stamp two different xLights versions. After this task there is **one** export core —
the display writer's dedup registries and emitter, seeded from any pre-existing
`EffectDB`/palette list — used by both renderers and by both delivery paths (file
write and live injection), with one stamp policy and one grid policy.

## Evidence & background

Findings: **P5-F15** (MEDIUM, "the harvest is not drop-in" — verifier-strengthened),
**P5-F4** (HIGH latent, two corruption vectors — the seeding fix), **P5-M3** (LOW-MED,
the two fresh emitters disagree on `sequenceTiming` and the MH path quantizes not at
all), **P5-M4** (LOW, palette index 0 emitted as an absent attribute), **P5-F17**
(version stamps), **CC-6** (duplication debt class). Detail:
`.../reviews/phases/display-rendering-and-xlights-io.md` §10 and §4; corrections in
`.../reviews/verification.md` §"Phase 5".

### The seeding requirement — non-negotiable, and it is the F4 fix

From `verification.md` §"Phase 5":

> F15: harvest is not drop-in — the registry must be SEEDED from the parsed template's
> EffectDB (which is precisely the F4 fix); sequence as one change.

From the phase doc's P5-F15 (verifier correction applied in place):

> **The harvest is not drop-in** (verifier correction; the first draft's "~2 hours"
> understated it). `EffectDBRegistry` as written starts empty and hands out indices
> from its own zero base (`export/effectdb_registry.py:36-44`). Dropping it into the
> moving-heads path — which *always* parses a user template (V-contract, Correction 1)
> — would re-index against a non-empty existing `EffectDB` and produce exactly the
> corruption described in P5-F4 vector 1. **The registry must first be seeded from the
> parsed template's `EffectDB`, which is precisely the P5-F4 fix.** Sequence them as
> one change: seed, then share. ~half a day for both together, and do not land the
> dedup first.

The corruption being avoided, from P5-F4 vector 1:

> `_sync_effectdb` assigns `sequence.effect_db = EffectDB(entries=registry.
> get_entries())` (`writer.py:406-408`) and `_sync_palettes` assigns
> `sequence.color_palettes = [...]` (`writer.py:423`). Both **replace**, not merge. In
> xLights, `<Effect ref="N">` and `palette="N"` are positional indices into exactly
> these two lists. Any effect already present keeps its old index and now resolves to a
> Twinklr entry — silent, total corruption of the user's existing effects, not merely
> loss.

And vector 2 (verifier addition), which the unified core must also close:

> `_write_group` calls `sequence.ensure_element(element_name)` (`writer.py:176`) and
> then places every event through `sequence.add_effect(..., layer_index=compact_idx)`
> (`writer.py:256`), where compaction starts at 0. `add_effect` **appends** to the
> existing layer's effect list (`models/xsq.py:296-313`). If that element already
> carries the user's own effects on layer 0, Twinklr's effects are appended into the
> same layer, interleaved in list order, with **no overlap resolution whatsoever** …
> **Fix:** seed both registries from the parsed sequence's existing `EffectDB` and
> `ColorPalettes` before writing, and place Twinklr effects on layers above the highest
> occupied one.

Verified at baseline: `display/export/effectdb_registry.py:27-44` —
`__init__(self, *, reserve_zero: bool = True)` appends `""` at index 0 and hands out
`len(self._entries)` thereafter, with no seeding entry point.
`display/palette/registry.py:25-46` — same shape, **and does not reserve index 0**.
`display/export/writer.py:121-122` constructs both fresh per `write()`;
`_sync_effectdb` / `_sync_palettes` (`:393-423`) assign wholesale.
`moving_heads/export/xsq_adapter.py:191,322` — `xsq.append_effectdb(settings_str)` once
per segment, no dedup at all.

### The stamp/grid values to unify (verified constants)

| Path | Version stamp | `sequenceTiming` | Quantization actually applied |
|---|---|---|---|
| Moving heads, fresh | `2024.10` (`moving_heads/xsq_export.py:67`) | `"50 ms"` (`:72`) | **none** |
| Display, fresh | `2024.01` (`pipeline/display_stages.py:243`) | `"20 ms"` (`:246`) | 20 ms snap in `TimingResolver` (`timing_resolver.py:164-190`) |

From P5-M3:

> The deeper asymmetry is what each path then *does* with it. The display path snaps
> every time value to a 20 ms grid …, consistent with its declared timing. **The
> moving-heads path applies no quantization at all** — segment boundaries flow to
> `Effect.start_time_ms`/`end_time_ms` as computed, while the head declares a 50 ms
> grid. Effects therefore land off-grid relative to the file's own declaration on the
> only shipped path.

From P5-F17, on the stamp specifically (severity lowered on newer evidence, but the
unification still required):

> Stage 6 follow-up research finds xLights' documented version cutoff is pre-2020 only
> and warns rather than rejects, so neither constant would block a load today. What
> keeps this open: the constants become live the moment the generate-fresh contract
> lands (making the stamp the product's whole compatibility story) …

And from V-contract's requirements list: "**Reconciling the two fresh emitters**, which
currently disagree on both the version stamp and the timing grid (P5-M3). Whichever
survives becomes the product's entire output contract, so the disagreement must be
resolved deliberately rather than by whichever caller happens to win."

### The palette index-0 asymmetry (P5-M4)

> `XSQExporter._build_effect` writes the palette attribute only when it is truthy and
> not `"0"` (`exporter.py:309-311`). `PaletteDBRegistry` does **not** reserve index 0
> (`display/palette/registry.py:26,43-44` — unlike `EffectDBRegistry`, which does), so
> the first registered palette is index 0 and is assigned as `palette="0"`
> (`writer.py:245,252`). Every effect using the sequence's most common palette therefore
> emits **no `palette` attribute at all**. … The asymmetry between the two registries
> suggests the reservation convention was applied to one and forgotten on the other.

### What is being harvested, and why

From the phase review §12:

> **The one thing that should not be deferred:** the display package's export half —
> `XSQWriter`, `EffectDBRegistry`, `PaletteDBRegistry`, `build_palette_string`, and the
> fresh-sequence emitter — is the reference implementation for the very contract Stage
> 2 recommends for the *shipped* path.

Registered as a strength: ST-5, "Display writer dedup registries + trace sidecar
(harvest target)".

### Interaction with P1P-T11 (read this before starting)

P1P-T11 ("Delivery v1") retires the `--xsq` template-merge input and implements fresh
minimal `.xsq` emission. If it has landed, the *primary* seeding scenario (a user
template parsed on every run) is gone — but seeding is still required, because:

- `reporting/evaluation/rerender.py:131` passes `template_xsq=xsq_path` (the review
  names it as an easy-to-miss third export caller);
- `DisplayRenderStage` accepts an externally supplied `sequence` from context/extras,
  and `DisplayRenderer.render`'s contract is "XSequence to write effects into"
  (`renderer.py:149-151`);
- live injection (D2/P2P-T12) writes into a sequence that already exists in a running
  xLights.

So: **seed unconditionally**. A seeded registry over an empty `EffectDB` is a no-op; an
unseeded registry over a populated one is silent corruption.

## Current behavior

- Two writers, quantified by the review: `XsqAdapter` (413 lines) +
  `DmxSettingsBuilder` (329) versus `XSQWriter` (431) + `SettingsStringBuilder` (194) +
  `EffectDBRegistry` (74) + `PaletteDBRegistry` (62). Genuinely shared: the `XSequence`
  model and `XSQExporter` (~740 lines).
- MH: no EffectDB dedup — N segments produce N entries even when identical.
- Display: dedup and layer placement starting at compacted index 0. P3-T5 pulled
  unconditional EffectDB/palette seeding and positional preservation forward as the
  narrow prerequisite for safe combined append; the general shared export core,
  arbitrary-document merge/layer policy, MH dedup, trace/injection unification, and
  common grid/stamp policy remain this task.
- Two version stamps, two declared grids, one path that ignores its own declaration.
- Palette index 0 emitted as an absent attribute.

## Target behavior

1. **One export core.** A single module owns: EffectDB registration/dedup, palette
   registration/dedup, layer placement, effect emission, and the trace sidecar. Both
   `XSQWriter` (display) and the moving-heads export path route through it. The
   settings-string *builders* stay separate (DMX-channel output and buffer-effect
   output really are different problems — the review says so); the **registry, layer,
   emission, and trace** halves are shared.
2. **Seeded, always (P3-T5 prerequisite already landed).** The core is constructed with the target `XSequence`'s existing
   `EffectDB` entries and `ColorPalettes` pre-loaded, so any index it hands out is
   unique across old and new content and no pre-existing `ref=`/`palette=` reference is
   invalidated. `_sync_*` merges rather than replaces (or, equivalently, the registry's
   `get_entries()` is a superset that preserves existing order and indices).
3. **No layer-0 interleaving.** Twinklr effects are placed on layers **above the
   highest occupied layer** of the target element. Where the element is untouched, this
   degenerates to today's behavior.
4. **One stamp policy.** A single constant/config value for the version stamp, used by
   every fresh-sequence emission path. The chosen value is recorded with its rationale;
   when a template/target sequence supplies its own version, that is preserved verbatim
   (today's behavior, `parser.py:164-166` → `exporter.py:132`).
5. **One grid policy.** A single declared `sequenceTiming` and a single quantization
   implementation applied by **both** renderers, so the file's declaration and its
   contents agree. Recommended value: **20 ms**, matching the display path's existing
   `TimingResolver` behavior and xLights' common default — but the value is a
   deliberate decision recorded with the stamp decision, not a coin flip. The MH path
   gains quantization it does not have today; the resulting golden diff is expected and
   must be shown.
6. **Palette index 0 resolved.** Either `PaletteDBRegistry` reserves index 0 the way
   `EffectDBRegistry` does, or the exporter stops treating `"0"` as absent. Pick one,
   apply it consistently, and record which — the review flags this as an unanswered
   asymmetry, and the empirical answer comes from the LOCAL-ONLY xLights check below.
7. **Both delivery paths share it.** File export and live injection (P2P-T12's
   `addEffect` client) build their payloads from the same core, so an injected effect
   and an exported effect are byte-for-byte the same settings string with the same
   dedup and the same quantization.
8. **Trace sidecar extended to moving heads.** The review names the trace sidecar as
   the phase's best observability artifact and recommends "Preserve, and extend to the
   moving-heads path" (§9.2). With one emission core, MH effects gain trace entries for
   free — do it.

**Non-goals**

- Do **not** merge `DmxSettingsBuilder` and `SettingsStringBuilder` into one settings
  builder.
- Do **not** implement settings-string escaping/validation (P5-F6/F7) — adjacent,
  separately scoped; but do not make it harder to add later.
- Do **not** change the parser's allow-list or attempt preserve-unknown round-tripping
  (P5-F5 / V-contract are P1P-T11's territory).
- Do **not** delete `XSQParser` (it has a real consumer: `profiling/profiler.py:13,48`).
- Do **not** change composition or DMX semantics — only where and how effects are
  registered, quantized, placed, and emitted.

## Implementation approach

Files expected to change:

- `packages/twinklr/core/sequencer/display/export/effectdb_registry.py` — seeding
  constructor / `seed_from(...)`.
- `packages/twinklr/core/sequencer/display/palette/registry.py` — seeding + the index-0
  decision.
- `packages/twinklr/core/sequencer/display/export/writer.py` — merge-not-replace sync;
  layer placement above the highest occupied layer; route through the shared core.
- `packages/twinklr/core/sequencer/moving_heads/xsq_export.py` and
  `moving_heads/export/xsq_adapter.py` — replace `append_effectdb`-per-segment with the
  shared registry; adopt quantization; adopt trace entries.
- `packages/twinklr/core/formats/xlights/sequence/{exporter,models/xsq}.py` — the stamp
  constant; palette attribute policy; `add_effect` layer semantics if the placement fix
  lands there.
- `packages/twinklr/core/pipeline/display_stages.py` — fresh-sequence construction uses
  the shared stamp/grid.

Design decisions already made — do not relitigate:

- **Seed before share. Do not land the dedup first.** This is the verifier's explicit
  sequencing instruction and the difference between a size regression and silent
  corruption of a user's show file.
- The display writer is the reference implementation being harvested; the MH path
  adopts it, not vice versa.
- The `XSequence` model and `XSQExporter` stay shared as they already are.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> A lane's tasks land as one PR-style merge per task (small, reviewable diffs).

> Cross-lane file conflicts are called out in the task tables; when unavoidable, the
> later lane rebases.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: "**Lane X (export unification)**: T6
(formats + both writers) — after T2." T6 shares `writer.py` with P3-T2 and shares
`xsq_export.py`/`exporter.py` with P1P-T11 — rebase on both.

## Acceptance criteria

1. **Seeding.** Writing into an `XSequence` that already contains K EffectDB entries
   and M palettes yields a sequence where: the first K entries and first M palettes are
   unchanged and in their original positions; every pre-existing `<Effect ref="n">` and
   `palette="n"` still resolves to the same string it did before; Twinklr's entries
   occupy indices ≥ K / ≥ M. **This test must fail on today's code.**
2. **Layer placement.** Writing into an element that already has effects on layers 0–2
   places Twinklr effects on layer ≥ 3; no pre-existing layer's effect list is modified.
3. **Dedup on the MH path.** N identical segments produce **one** EffectDB entry, not
   N. Assert on entry count for a fixture with known-duplicate settings strings.
4. **One stamp.** `grep -rn '"2024\.' packages/` finds the version stamp in exactly one
   place. Both fresh emitters produce the same stamp.
5. **One grid, honoured.** Both fresh emitters declare the same `sequenceTiming`, and
   every emitted `start_time_ms`/`end_time_ms` on **both** paths is a multiple of the
   declared grid.
6. **Palette index 0.** Whichever policy is chosen, a fixture whose most common palette
   is the first registered one produces effects that reference it unambiguously —
   assert the emitted attribute (present with the right value, or absent-by-a-reserved-
   index-0 convention), and state the choice in the test docstring.
7. **Trace on both paths.** MH-emitted effects carry trace entries with the same fields
   display's do (`event_id / placement_id / section_id / lane / group_id / template_id
   / element / layer / start / end`, as available for the MH domain).
8. **Injection parity.** The payload the injection client would send for a given effect
   is byte-identical to that effect's settings string in the exported file (assert on
   the built payload; no running xLights needed).

Golden-diff expectations (**required, both paths**):

- MH golden: **expected to change** — this is the one place in Phase 3 where MH output
  legitimately differs. The diff must show exactly: (a) fewer EffectDB entries
  (dedup), (b) start/end times snapped to the declared grid, (c) the unified version
  stamp and `sequenceTiming`, (d) new trace-sidecar content. Any other MH difference —
  changed DMX values, changed effect count, changed element/layer assignment — is a
  defect and blocks merge.
- Display golden: expected to change only in the stamp (if it moves off `2024.01`) and
  in palette-attribute emission (if the index-0 policy changes). Effect timing must be
  unchanged — display already quantized to 20 ms.
- Combined golden (from P3-T5, if merged first): updated accordingly with the same
  itemized justification.

## Tests

TDD — write the seeding tests first; they are the ones that fail today.

1. `tests/unit/sequencer/display/export/test_registry_seeding.py::
   test_effectdb_seeded_preserves_existing_indices` — acceptance #1.
2. `…::test_palette_registry_seeded_preserves_existing_indices`.
3. `…::test_seeding_empty_sequence_is_noop` — regression guard for the fresh path.
4. `tests/unit/sequencer/display/export/test_writer_layer_placement.py::
   test_effects_placed_above_highest_occupied_layer` — acceptance #2 (P5-F4 vector 2).
5. `tests/unit/sequencer/moving_heads/test_export_dedup.py::
   test_identical_segments_dedup_to_one_entry` — acceptance #3.
6. `tests/unit/formats/xlights/test_export_contract.py::test_single_version_stamp` and
   `…::test_single_timing_grid` and `…::test_all_effect_times_on_grid` — acceptances
   #4/#5. **Note**: `formats/xlights/sequence/` has exactly one direct test today
   (`test_timeline.py`); parser, exporter, and the `xsq.py` models have none. This file
   is a deliberate, overdue addition.
7. `tests/unit/formats/xlights/test_palette_index_zero.py` — acceptance #6.
8. `tests/unit/sequencer/moving_heads/test_export_trace.py` — acceptance #7.
9. `tests/unit/sequencer/test_injection_payload_parity.py` — acceptance #8 (skip if
   P2P-T12 has not landed; then this becomes a follow-up note in the PR body).
10. Round-trip regression: the parse→export round-trip test introduced by P1P-T1 must
    still pass, and a new case covering "write into a populated sequence, re-parse,
    verify pre-existing effects still resolve" is added here.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/display/export/ -v
uv run pytest tests/unit/sequencer/moving_heads/ -v
uv run pytest tests/unit/formats/xlights/ -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline
uv run pytest tests/golden -v   # MH golden diff reviewed item-by-item, see above
```

LOCAL-ONLY (xLights GUI, 2026.15 — these answer questions the repo cannot):

- **Palette index 0**: open an exported file whose effects use the first-registered
  palette and confirm xLights applies that palette (or falls back). This single check
  settles P5-M4.
- **Quantization**: follow the V4 protocol — "save from xLights and diff the saved file
  against the generated one" — and record whether xLights rewrote any effect times.
  That diff settles P5-M3.
- **Seeding**: export into a real user template that already contains effects, open it,
  and confirm the pre-existing effects are unchanged. This is the empirical proof of
  the F4 fix.

**Test budget: $0 — this task makes no API calls of any kind.**

## Effort & risk

**Size: L.** The review costed seeding + sharing at "~half a day for both together",
but that excluded the stamp/grid unification, the trace extension, injection parity,
and the first real test coverage for `formats/xlights/sequence/`.

**Main risk: landing the dedup before the seeding.** The verifier's instruction is
explicit — "do not land the dedup first" — because dedup on an unseeded registry over a
populated `EffectDB` is *silent, total corruption of the user's existing effects*.
*Mitigation*: the seeding tests are written first and must be green before any dedup
code is written; the executor is instructed to sequence commits accordingly, and the
verifier checks commit order, not just the final diff.

**Secondary risk: an MH golden diff that hides a real regression.** This is the one
task allowed to change MH output, which makes it the easiest place to smuggle one in.
*Mitigation*: the acceptance criteria enumerate the four permitted diff categories and
declare everything else a blocker; the verifier reviews the MH golden diff item by
item.

**Third risk: the grid change moves real effect boundaries.** MH segment times are
currently unquantized; snapping to 20 ms shifts them by up to 10 ms. That is intended
(the file's own declaration demands it) but it is a behavior change on the mature path.
*Mitigation*: the LOCAL-ONLY save-and-diff check tells us what xLights would have done
anyway; if xLights rewrites times regardless, our snapping is strictly closer to truth.

## Owner-approved amendment and author handoff — 2026-08-26

The owner authorized this task for **offline implementation and independent verification
only** and replaced the stale recommendations above with this binding package:

1. Effects use one 20 ms grid with positive-duration preservation; timing tracks and
   sequence duration remain source-exact.
2. Fresh output retains the `2026.15` version stamp.
3. Palette index zero is emitted explicitly; populated palette indices never shift.
4. EffectDB index zero remains reserved on fresh output and identical non-empty settings
   deduplicate without moving seeded entries.
5. Export remains fresh-only and rejects mutation through an `XSequence` parsed from a
   user document.
6. Physical file layers start above every occupied layer; renderer logical layers remain
   unchanged for blend semantics.
7. One deep renderer-neutral emission module lives under
   `formats/xlights/sequence`; display and moving heads remain settings adapters.
8. File output uses positional references, while the same resolved request supplies the
   live payload at reserved layers 99+; this task adds no live command or call.
9. Trace schema `twinklr-xsq-trace.v2` carries display and moving-head provenance, and
   standalone `run` gains the trace sidecar.
10. The task remains $0/offline-only; palette application and xLights save/rewrite
    behavior remain pending local empirical acceptance.

The follow-up audit made two refinements binding before broad implementation:

- a grouped moving-head trace records a deterministic ordered list of every contributing
  `fixture_id` / `segment_id` / `step_id`, plus the emitted group target;
- nearest-20 ms half-up endpoint snapping and one-grid positive-duration repair are
  accepted only after the complete renderer batch is prevalidated by target/logical
  layer. A quantization-created overlap fails before mutation; effects are never silently
  reordered or merged.

### Frozen remediation candidate

The candidate is isolated on `codex/p3t6-unified-export` from base `e1ed146`. The initial
RED was the absent public `formats.xlights.sequence.emission` seam. Vertical GREEN then
covered seeded registries, deduplication, occupied-layer offset, file/live topology,
explicit palette zero, trace-v2, adjacent/sub-grid/transition timing, grouped MH source
provenance, fresh-only rejection, and standalone trace delivery.

Formal first review rejected that snapshot. Six review discriminators were then captured
RED: non-20 ms heads and a fresh timing override were accepted; a seeded nonempty
EffectDB index zero shifted; writer failure mutated the sequence before batch validation;
group ordering selected a different representative; and mixed section/template
provenance grouped silently. Remediation makes the 20 ms head sole, fails closed on
nonempty index zero, removes trace-v1 display types, keeps display sequence mutation
behind complete batch validation, and gives grouped MH settings/label/trace one
deterministic representative with ordered typed sources and shared-provenance rejection.
The approved queue/flush emission interface did not require redesign; removing eager
display element creation closed the atomicity defect.

Implementation routes both `XSQWriter` and `XsqAdapter` through `EmissionSession`; the
DMX and display settings builders remain separate. `live_effects_from_segments` consumes
the same resolved settings/times/live-layer provenance without issuing a request. The
combined golden adds four real MH provenance rows and retains its eight display rows.
The display golden changes only from `50 ms` to `20 ms` plus explicit `palette="0"`.

The remediated offline/code candidate subsequently received independent standards,
specification, and adversarial approval and was integrated at `c9620db`. Empirical
xLights GUI acceptance remains open, and P3-T7+ remains unauthorized.

Current author evidence, exact manifest, digest, and review status are volatile execution
truth owned by the campaign [HANDOFF](../../plan/HANDOFF.md). This specification retains
only the accepted contract and stable remediation notes.
