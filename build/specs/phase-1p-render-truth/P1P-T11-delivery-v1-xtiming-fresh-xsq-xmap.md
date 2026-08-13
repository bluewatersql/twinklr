# P1P-T11 — Delivery v1: `.xtiming` + fresh `.xsq` + `.xmap`

Phase: 1P (Render Truth) · Lane: D (delivery) · Executor: opus · Verifier: opus · Depends on: P1P-T6

> ## ⚖ OWNER-DECISION-BEARING TASK
>
> This is the one task in Phase 1P whose merge the owner reviews directly. **What the
> owner reviews:**
>
> 1. **Retiring `--xsq` as a required CLI input.** Today `--xsq` is required and every
>    shipped run parses, regenerates, and silently damages the user's own show file. This
>    task removes that input. It is a user-facing product decision, not just a code
>    change — the review states plainly: *"the contract is not 'delete an unused branch';
>    it is **removing a required, always-exercised input from the CLI**, which is a
>    user-facing product decision."*
> 2. **Making the fixture config the CLI's real input**, which kills the hardcoded
>    `fixture_count=4`, `min_pass_score=7.0`, and the hardcoded display graph — changing
>    the shape of every existing invocation.
> 3. **What Twinklr now hands the user**: an `.xtiming` file, a fresh minimal `.xsq`, and
>    an `.xmap` mapping hint — to be imported into xLights rather than opened as the
>    user's sequence.
>
> Do not merge without owner sign-off on all three.

## Objective

Ship something a user can actually receive. Today the moving-heads path requires the
user's own `.xsq`, rewrites it, and destroys parts of it on every run — while the
generate-fresh branch that would avoid all of that has never executed and is self-fatal.
This task delivers three artifacts instead: `.xtiming` (timing tracks alone, mapping-free),
a fresh minimal `.xsq` (effects, no user document involved), and an `.xmap` mapping hint —
and retires the template-merge input by construction.

## Evidence & background

Findings: **CF-5** = **P5-F4** + **P5-F5** + **V-contract**; **ST-8**; **P7-M1** + **P7-F8**;
plus **M6b** from `reviews/modernization.md`.

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### 1. The template branch is the only branch that has ever run (V-contract, Correction 1). Verbatim:

> The first draft called the template parse "a single *optional* call site".
> It is not optional: `cli/main.py:341` declares
> `run.add_argument("--xsq", required=True, help="Path to input .xsq template")`. Every
> shipped run therefore takes the `if template_xsq and Path(template_xsq).exists()` branch
> at `xsq_export.py:53-56`. The generate-fresh `else` branch (`:62-74`) **has never
> executed in production** — and it could not survive if it did: it sets `media_file=""`
> (`:68`), while `XSQParser` treats a missing or empty `mediaFile` as a *fatal* parse error
> (`parser.py:168-170`). Twinklr's only from-nothing moving-heads emitter produces a file
> its own parser rejects.
>
> Two consequences. First, **P5-F5's seven losses are unconditional today**, not
> conditional on a user opting into a template — every run parses the user's `.xsq`,
> regenerates it, and drops that content. Second, the contract is not "delete an unused
> branch"; it is **removing a required, always-exercised input from the CLI**, which is a
> user-facing product decision (Stage 8) on top of a small code change.

Re-verified in the current tree: `cli/main.py:341` is
`run.add_argument("--xsq", required=True, help="Path to input .xsq template")`;
`xsq_export.py:53` is `if template_xsq and Path(template_xsq).exists():`; the fresh branch
sets `version="2024.10"` (`:67`) and `media_file=""` (`:68`).

### 2. What is lost every run (P5-F5, verbatim summary of the seven):

> 1. **`<Jukebox>` is regenerated empty**, unconditionally … Any user jukebox state is destroyed.
> 2. **Root children outside the five modeled sections are dropped structurally** …
> 3. **`DisplayElements` per-element state is hardcoded on write**: `visible="1"`,
>    `collapsed="0"` for every element … Collapse state, render-disabled flags, and
>    row ordering are lost …
> 4. **Multi-layer timing tracks are flattened.** … xLights lyric timing tracks are
>    conventionally three layers (phrases / words / phonemes); after a round trip they
>    become one layer containing all three sets of markers, overlapping. This is the most
>    user-visible loss in the list.
> 5. **`SequenceHead` is a 14-field allow-list** …
> 6. **The 1 ms marker heuristic** … lossless in practice but a genuine semantic guess.
> 7. Effect-level *attributes* are the one thing that does survive …

Plus the corruption vectors (P5-F4): wholesale `EffectDB`/`ColorPalettes` replacement
invalidating the user's positional `ref=`/`palette=` indices, and layer-0 interleaving with
no overlap resolution.

### 3. What the contract needs (V-contract, verbatim):

> **What would a minimal valid `.xsq` emission require?** Structurally, nothing new — the
> existing `_build_tree` already emits a self-contained document. Three real gaps:
>
> 1. **A correct, current version stamp** (P5-F17), which requires the V4 empirical test
>    first. This is the only hard dependency.
> 2. **`mediaFile` handling.** The fresh MH path sets `media_file=""` (`xsq_export.py:68`)
>    while the parser treats a missing/empty `mediaFile` as a *fatal* parse error
>    (`parser.py:168-170`). … Under the contract this stops being a latent curiosity and
>    becomes the **first thing that would break**, because the never-executed branch
>    becomes the only branch.
> 3. **A decision about `DisplayElements` content.** Under generate-fresh, Twinklr emits
>    only its own models; xLights' effect-import must then match them by name against the
>    user's layout.
> 4. **Reconciling the two fresh emitters**, which currently disagree on both the version
>    stamp and the timing grid (P5-M3).

And on the parser's survival, verbatim:

> the contract removes the parser **from the export/trust path**, leaving it as an
> analysis-only component … `profiling/profiler.py:13` imports `XSQParser` and `:48`
> instantiates it.

Three export-path callers exist, per the V-contract table: `xsq_export.py:53-56`
(branch deleted), `pipeline/display_stages.py:239-248` (already generate-fresh,
unchanged), and `reporting/evaluation/rerender.py:131` (**needs the same treatment; easy
to miss**).

### 4. `.xtiming` is the smallest real deliverable (ST-8 / M6b). Verbatim (M6b):

> **Timing tracks import standalone as `.xtiming`** — a mapping-free minimum-viable
> deliverable for Twinklr's audio analysis alone.

And (V-contract):

> **`.xtiming`-only** — timing tracks import standalone, with no model mapping at all.
> Given that `timeline.py` is already on the CLI path, correct, and the best-tested file
> in `formats/xlights/` (§5), this is a genuinely small deliverable that would put
> Twinklr's deterministic audio analysis in front of a user without touching any of the
> defects in this review.

Re-verified: `formats/xlights/sequence/timeline.py` builds `"Twinklr Beats"` and
`"Twinklr Bars"` tracks (plus sections, lyrics, phonemes builders); **no `.xtiming`
emitter exists anywhere in the tree** (`grep -rl xtiming packages/ scripts/` → no matches).

### 5. `.xmap` mitigates the mapping friction (M6b). Verbatim:

> **Effect import accepts xLights donor sequences** targeting the currently open
> sequence, carrying effects + timing tracks; models must pre-exist in the view;
> mapping is the friction (mitigated by shipping `.xmap` or using AI/auto mapping).
> UNVERIFIED: whether a bare `.xsq` without `xlights_rgbeffects.xml` imports (docs
> state the requirement only for the zip path) — Stage 4 empirical test.

That unverified item is **P1P-T12's** job, not this task's.

### 6. Version stamp status (M6b, verbatim — this de-risks the "hard dependency" above):

> **Version stamps: documented cutoff is pre-2020 only (warning, not rejection;
> introduced 2026.04)** — "2024.10" is acceptable today; the boundary can ratchet, so
> update stamps anyway (free). UNVERIFIED: treatment of synthetic/unknown stamp values.

### 7. The CLI hardcodes (P7-M1 / P7-F8, CONFIRMED). Verbatim:

> `main.py:208` passes a literal `fixture_count=4`
> into `build_moving_heads_pipeline(...)`, which flows into the planner prompt path
> (`stage.py:145` → `orchestrator.py:75`) — while the user's *actual* fixture config
> is resolved three lines later (`main.py:214-217`, `_resolve_fixture_config_path`)
> and never reconciled against the literal. On the only shipped path, any rig that
> does not have exactly 4 fixtures gets a planner that is told a false count.
> `min_pass_score=7.0` (`main.py:211`) is the same pattern: a second hardcoded
> operative value that silently overrides `job_config.agent.success_threshold`
> (documented in `docs/user-guide.md` as the config field for this, on a 0–100
> scale, while the CLI's literal is on a 0–10 scale — see P7-M2). Net effect: **the
> shipped CLI is correct only for the author's own display and fixture rig**, not a
> general-purpose entry point despite taking `--config`/`--app-config` as if it were.

Re-verified: `cli/main.py:93` and `:208` both contain `fixture_count=4`; `:211` contains
`min_pass_score=7.0`; `build_display_graph()` at `:62-135` hardcodes the 3-group layout.

## Current behavior

- `--xsq` is required; every run parses the user's sequence, regenerates it, and inflicts
  the seven P5-F5 losses plus the two P5-F4 corruption vectors.
- The generate-fresh branch has never run and emits `media_file=""`, which Twinklr's own
  parser rejects as fatal.
- No `.xtiming` emitter exists. No `.xmap` generation exists.
- The CLI tells the planner there are 4 fixtures regardless of the rig, overrides the
  configured success threshold with a 0–10 literal against a 0–100 config scale, and builds
  a hardcoded 3-group display graph.

## Target behavior

1. **`.xtiming` export.** A run emits a standalone `.xtiming` file carrying Twinklr's
   timing tracks (beats, bars, sections; lyrics/phonemes when available). This is the
   mapping-free deliverable and should work even if nothing else does.
2. **Fresh minimal `.xsq`.** The moving-heads export emits a self-contained sequence with
   no user document involved: a current version stamp, a **non-empty `mediaFile`**, and
   only Twinklr's own models in `DisplayElements`.
3. **`.xmap` mapping hints.** A generated `.xmap` maps Twinklr's model names to the user's
   layout to reduce import friction.
4. **`--xsq` retired as a required input** ⚖. The template-merge branch is removed from
   the export path at **all three call sites** — including `rerender.py`. `XSQParser`
   survives for `profiling/` (analysis only).
5. **Fixture config becomes the CLI's input** — `fixture_count`, the success threshold,
   and the display graph all come from configuration. No literal `4`, no literal `7.0`, no
   hardcoded graph.

**Non-goals.** Do not implement `addEffect` HTTP-automation injection (M6b option 3 — a
later phase). Do not un-defer the display pipeline. Do not fix `_ensure_all_display_elements`
beyond deleting it if it becomes dead under the contract (the review says it does). Do not
attempt the xLights empirical validation here — that is P1P-T12.

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/sequencer/moving_heads/xsq_export.py` — the template branch
  (`:53-56`), the fresh branch (`:62-74`) including `version` and `media_file`.
- `packages/twinklr/core/reporting/evaluation/rerender.py` (`:131`) — the third,
  easy-to-miss caller.
- `packages/twinklr/core/formats/xlights/sequence/timeline.py` — source of the timing
  tracks; new `.xtiming` serializer alongside it.
- New: `.xmap` generator (name-mapping hints for the emitted models).
- `packages/twinklr/core/formats/xlights/**` — reconcile the **two fresh emitters**, which
  disagree on version stamp and timing grid (P5-M3); the survivor becomes the product's
  entire output contract.
- `packages/twinklr/cli/main.py` — `--xsq` argument (`:341`), `build_display_graph`
  (`:62-135`), `fixture_count=4` (`:93`, `:208`), `min_pass_score=7.0` (`:211`), and
  `_resolve_fixture_config_path` (`:50`) becoming the real input path.
- `parser.py`'s `_ensure_all_display_elements` (`:348-391`) — delete if dead under the
  contract, per the review.
- `docs/user-guide.md` and any CLI-usage docs — the invocation changes.

Design decisions already made (do not relitigate):
- **Generate-fresh is the target contract**, not "preserve the template better". The
  review: *"it deletes an entire defect class along with the code that produces it, and it
  is the only remedy that makes the P5-F4/P5-F15 seeding work unnecessary rather than
  merely deferred."*
- **Update the version stamp** even though M6b downgraded it from a blocker ("the boundary
  can ratchet … update stamps anyway; it is free").
- **`mediaFile` must be non-empty** — the emitted file must survive Twinklr's own parser.
  P1P-T1's round-trip test already asserts this.
- **`.xtiming` first.** It is the smallest, best-tested, lowest-risk deliverable; if the
  `.xsq` work slips, `.xtiming` should still ship.
- **`XSQParser` is not deleted**, only detached from export (`profiling/profiler.py` keeps
  it).

Sequencing constraints (copied verbatim from `build/plan/00-overview.md`):

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `build/plan/02-phase-1p-render-truth.md`:

> **Lane D (delivery, after T2; touches `formats/`, `cli/`)**: T11 → T12.

> Merge order at phase end: G → R → A → I → D (D rebases on R for exporter touches).

> T11 is ⚖ (user-facing input change) — the spec must include the CLI migration notes
> and is the one task in this phase whose merge the owner reviews directly.

## CLI migration notes (required by the phase plan)

**Before:**
```
twinklr run --audio song.mp3 --xsq my_show.xsq --out artifacts/ \
            --app-config config.json --config job_config.json
```
`--xsq` required; output overwrote/regenerated a copy of `my_show.xsq`; the planner was
told there were 4 fixtures whatever the rig; `success_threshold` from config was silently
overridden by a 7.0 literal on a different scale.

**After:**
```
twinklr run --audio song.mp3 --out artifacts/ \
            --app-config config.json --config job_config.json
```
- `--xsq` is **removed** (or accepted-and-ignored for one release with a deprecation
  warning — the owner picks; recommend hard removal, since accepting-and-ignoring a
  formerly load-bearing flag is its own silent-failure class).
- Outputs: `artifacts/<song>/<name>.xtiming`, `<name>.xsq` (fresh), `<name>.xmap`.
- The user **imports** into their own sequence (xLights: import effects from a donor
  sequence, using the shipped `.xmap`), rather than opening Twinklr's file as their show.
- `fixture_count` now comes from the fixture config; a rig with 8 heads is described
  accurately to the planner for the first time.
- The success threshold now comes from `job_config.agent.success_threshold`. **Scale
  conflict to resolve explicitly:** the CLI literal was 0–10 while the documented config
  field is 0–100 (P7-M2). Pick one scale, state it in code and docs, and validate the
  range. (Note P3-M-A: the threshold is behaviorally inert today — wiring it here does not
  make it operative; that is a P2P concern. Do not claim otherwise in the docs.)
- The display graph is no longer hardcoded; document what replaces it (config-driven, or
  moving-heads-only for now with the display path still deferred).

Docs to update in this change: `docs/user-guide.md` invocation and outputs; any README
quickstart; the `make` targets that pass `--xsq`.

## Acceptance criteria

- [ ] A run produces a `.xtiming` file that contains Twinklr's timing tracks and parses as
      valid XML with the expected track/marker structure.
- [ ] A run produces a fresh `.xsq` with (a) a current version stamp, (b) a **non-empty**
      `mediaFile`, and (c) only Twinklr's own models — and the file **re-parses through
      `XSQParser` without error** (today's fresh branch fails this).
- [ ] A run produces an `.xmap` naming the emitted models.
- [ ] `--xsq` is no longer a required argument; `twinklr run` succeeds with no `.xsq`
      input.
- [ ] **All three** export-path callers no longer take a user template:
      `xsq_export.py`, `pipeline/display_stages.py` (already fresh — verify unchanged), and
      `reporting/evaluation/rerender.py`.
- [ ] `XSQParser` still has its `profiling/profiler.py` consumer (not deleted).
- [ ] The two fresh emitters are reconciled: one version stamp, one timing grid. A test
      asserts both emitters (or the single survivor) agree.
- [ ] `grep` shows no `fixture_count=4`, no `min_pass_score=7.0`, and no hardcoded display
      graph in `cli/main.py`.
- [ ] An 8-head rig (P1P-T2's `rig_8head`) run end-to-end reports 8 fixtures to the planner
      — asserted at the prompt-context boundary, not just at the config layer.
- [ ] The success-threshold scale is unified, documented, and range-validated.
- [ ] `docs/user-guide.md` describes the new invocation and outputs; no doc still instructs
      `--xsq`.
- [ ] `make validate` check-only equivalents pass; golden suite regenerated with reviewed
      diffs.

**Golden-diff expectation (BEFORE/AFTER):**

```
BEFORE:
  Golden .xsq output derives from a parsed template document: it carries the
  template's head fields, its DisplayElements (all visible="1" collapsed="0"),
  an emptied <Jukebox/>, and Twinklr's effects appended into the existing
  EffectDB.

AFTER:
  - The emitted .xsq is self-contained: head with a current version stamp and a
    NON-EMPTY mediaFile; DisplayElements contains ONLY Twinklr's models.
    This is a whole-file diff and is expected.
  - NEW artifacts appear in the golden tree: <name>.xtiming and <name>.xmap.
  - The .xtiming markers equal the "Twinklr Bars"/"Twinklr Beats" marker values
    already in the .xsq — a test asserts equality, so the two deliverables
    cannot drift.
  - Effect PAYLOADS (E_SLIDER_DMX values, E_VALUECURVE_DMX strings) are
    UNCHANGED from the post-Lane-R goldens. Any payload movement here means the
    rebase onto Lane R went wrong or this task strayed into T3/T5/T6 scope.
```

## Tests

| Test | Behavior pinned |
|---|---|
| `test_xtiming_export_structure` | `.xtiming` is well-formed and carries the expected tracks |
| `test_xtiming_markers_match_xsq_timing_tracks` | The two deliverables cannot drift apart |
| `test_fresh_xsq_reparses` | The self-fatal `media_file=""` defect cannot return |
| `test_fresh_xsq_has_current_version_stamp` | P5-F17 |
| `test_fresh_xsq_contains_only_twinklr_models` | Generate-fresh contract |
| `test_xmap_names_emitted_models` | Mapping hints correspond to what was emitted |
| `test_run_without_xsq_argument` | ⚖ the CLI change |
| `test_rerender_uses_fresh_path` | The third caller is not missed |
| `test_profiler_still_uses_parser` | Parser detached from export, not deleted |
| `test_fresh_emitters_agree_on_stamp_and_grid` | P5-M3 |
| `test_planner_receives_real_fixture_count[rig_8head]` | P7-M1 |
| `test_success_threshold_from_config_single_scale` | P7-M1's second half |
| Golden suite (P1P-T1) | Reviewed BEFORE/AFTER diff as specified above |

**Test budget:** no paid API calls in automated tests — the planner-context assertion uses
a fake provider. Whether xLights actually imports these artifacts is **LOCAL-ONLY** and is
P1P-T12's job.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/formats -v
uv run pytest tests/unit/sequencer/moving_heads -v
uv run pytest tests/golden -v

# defect-specific checks the verifier runs
grep -n "fixture_count=4\|min_pass_score=7.0" packages/twinklr/cli/main.py     # expect: no match
grep -rn "template_xsq" packages/                                              # expect: no export-path consumer
grep -rn "XSQParser" packages/ | grep -v profiling                             # expect: parser only in analysis paths/tests
uv run twinklr run --help                                                      # --xsq absent

# LOCAL-ONLY (P1P-T12 owns this; not run in CI):
# import the emitted .xsq/.xtiming into xLights 2026.15
```

## Effort & risk

**Effort: L.** Three new output formats, a contract change across three call sites, an
emitter reconciliation, and a CLI surface change with docs.

**Main risk (⚖): the new deliverables may not import cleanly into xLights**, and the
project would have retired a working-if-damaging path for one that does not land. The
review's residual-risk note is explicit that whether a bare `.xsq` imports without
`xlights_rgbeffects.xml` is **unverified**. Mitigation: `.xtiming` ships as an independent
deliverable that imports standalone with no mapping (M6b), so there is a floor;
**P1P-T12 empirically validates the `.xsq` path and is a hard gate on calling this task
done for the show file.** If T12 finds the bare `.xsq` does not import, the fallback is
the zip path with `rgbeffects.xml` or `addEffect` injection — record the outcome rather
than reverting the contract.

**Second risk: retiring `--xsq` breaks the owner's existing workflow** without a
transition. Mitigation: the migration notes above; the owner decides between hard removal
and a deprecation release.

**Third risk: the rebase onto Lane R.** Lane D rebases on R for exporter touches, and
P1P-T6 changes the same emit path. Mitigation: keep this task's exporter diff to document
structure and head fields, never to channel-value resolution; regenerate goldens once,
after the rebase, and confirm effect payloads are unchanged (see the golden-diff
expectation).
