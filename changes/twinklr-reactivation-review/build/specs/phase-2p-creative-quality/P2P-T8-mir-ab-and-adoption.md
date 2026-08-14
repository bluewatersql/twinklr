# P2P-T8 — MIR A/B + adoption (D10)

Phase: 2P (Creative Quality, Measured) · Lane: M (analysis substrate, parallel) · Executor: opus · Verifier: opus · Depends on: P1P-T4, P1P-T8

⚖ **Owner-decision-bearing.** The owner reviews the A/B verdict and the adoption
decision. The decision is made by the pre-committed numeric gate in §"Adoption gate",
not by judgment after the numbers are seen. **Record the decision either way** — a
"keep the current DSP" outcome is a result, not a failure.

## Objective

Integrate `beat-this` (beats + downbeats) and All-In-One (structure labels) behind the
existing `BeatGrid` interface, A/B them against the current DSP on golden fixtures
using criteria fixed **before** any measurement, and adopt or reject per that gate.
Whatever wins, one model-derived rhythmic/structural truth then feeds every grid
consumer — completing at the source what P1P-T4 completed at the consumer level.

## Evidence & background

Finding: **D10 (new) — MIR modernization**, research-verified, accessed 2026-08-13.
Also **CF-2** (three misaligned grids), **P2 §7** (the DSP that stays), **CC-7**
(zero ground-truth assertions).
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D10,
§2.3, §5, §6; `.../reviews/verification.md` "Phase 2", "Phase 4" (P4-F2/M3);
`.../reviews/phases/moving-heads-rendering.md` P4-F2.

### D10 quoted (versions, licences and the honest gaps are load-bearing)

> - **Beats+downbeats: adopt `beat-this`** (CPJKU; PyPI 1.1.0 2026-04-14, MIT code+
>   weights, deps just `torch>=2`+torchaudio+einops, ~78 MB, no madmom; GTZAN beat F1
>   89.1 / downbeat F1 78.3). Decisive context: **librosa has no downbeat tracker at
>   all** — Twinklr's custom phase-voting competes against nothing maintained
>   (madmom: no release since 2018, git-install only). Known trade-off: slightly
>   lower continuity metrics (CMLt/AMLt) than DBN post-processing; the optional
>   `--dbn` flag reintroduces madmom — skip it.
> - **Structure labels (verse/chorus): All-In-One** — beats+downbeats+tempo+labeled
>   segments in one pass. Canonical `allin1` is install-broken on modern stacks
>   (madmom + NATTEN torch-ceiling); on Apple Silicon use **`all-in-one-mlx`**
>   (PyPI 1.0.6, 2026-08-12, MIT, no torch/madmom/NATTEN, claims 12.6× on M4;
>   single-maintainer risk) or the `all-in-one-fix` fork from git (torch ≤2.7 —
>   conflicts with our pin; UNVERIFIED PyPI presence).
> - **Keep custom**: energy/multiscale, builds/drops (post-fix), tension, timeline —
>   no model equivalent exists and the verified DSP is sound.
> - **Adoption gate (honest)**: A/B on golden fixtures against the current BeatGrid
>   before switchover — the repo's own test gap (no tempo/beat ground-truth
>   assertions anywhere) gets fixed by this A/B's fixture set. Python 3.13 support
>   for beat-this is UNVERIFIED (no upper bound declared, no CI claim).
> - **Payoff beyond accuracy**: one model-derived rhythmic/structural truth feeds
>   planner numbering, renderer placement, and timing tracks — dissolving CF-2's
>   three-grid class instead of reconciling it.

### UNVERIFIED items — carry them, do not quietly resolve them

These are the review's own words. The executor must treat each as an open question to
be answered empirically in this task, and must record the answer:

1. **`beat-this` on Python 3.13: UNVERIFIED** — "no upper bound declared, no CI
   claim". The repo is on Python 3.12.13 today (Stage 4 baseline), and the 3.12→3.13
   move belongs to Phase 4 (D7/M3). So this task runs on 3.12; the 3.13 question is
   *recorded as still open* and handed to Phase 4, not answered here by assumption.
2. **`all-in-one-mlx` is single-maintainer** (PyPI 1.0.6, 2026-08-12) — an accepted,
   named risk. Mitigation per §5: "the A/B gate means we never depend on a model we
   haven't verified against our own fixtures."
3. **`all-in-one-fix` fork: UNVERIFIED PyPI presence**, and it declares torch ≤2.7
   which "conflicts with our pin". Do not adopt it on the strength of this spec; if
   the mlx path fails on the owner's machine, report rather than substituting.
4. **torchaudio**: `beat-this` "still declares it" while torchaudio is in maintenance
   wind-down (D7). Note the dependency; do not build anything new on torchaudio APIs.

### What must NOT change

> **Keep custom**: energy/multiscale, builds/drops (post-fix), tension, timeline — no
> model equivalent exists and the verified DSP is sound.

And from §6 (non-goals): "no MIR/model adoption without the fixture A/B".

### Relationship to P1P-T4 (quoted verbatim from the plan)

> - CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both
>   halves (P1P-T4).

and from the Phase 1P task table:

> NOTE: P2P-T8 (MIR adoption) upgrades the grid's SOURCE; this task fixes the
> CONSUMERS.

So P1P-T4 has already made every consumer read one grid. This task changes what
produces that grid. If P1P-T4 has not merged, **stop** — swapping the source under
three disagreeing consumers reproduces CF-2 with new numbers.

## Current behavior

- Beats, downbeats and structure come from Twinklr's own DSP. `BeatGrid`
  (`sequencer/timing/beat_grid.py`) is constructed via `from_resolver`,
  `from_tempo`, or `from_song_features`, and exposes `beat_boundaries`,
  `bar_boundaries`, `ms_per_bar`, `ms_per_beat`, `snap_to_nearest_bar/beat`.
- The repo has **no tempo, beat-position, or key ground-truth assertion anywhere**
  (P2-F24, verifier-revised form): "real ground-truth assertions exist (~15, incl. a
  reference-loop Foote check) but **no tempo value, beat position, or key label is
  ever asserted against a known correct value anywhere in the repo**." P1P-T8 adds the
  first ones (click-track tempo/beats, known key); this task builds the fixture set
  out.
- Downbeat detection is custom phase-voting; librosa offers no alternative.

## Target behavior

1. **A `BeatGrid` source abstraction.** Beat/downbeat/structure production sits behind
   an interface with at least three implementations: `dsp` (current), `beat_this`,
   and `allinone` (structure labels; on Apple Silicon via `all-in-one-mlx`). Selection
   is configuration. `BeatGrid` itself — the consumed artifact — does not change
   shape; that is the whole point of putting the swap behind it.
2. **A golden fixture set with ground truth.** Songs (or click tracks / annotated
   excerpts) with known beat times, downbeat times, and section boundaries, tracked in
   the repo or referenced deterministically. This fixture set is the durable
   deliverable even if adoption is rejected — it closes CC-7's ground-truth gap for
   rhythm.
3. **An A/B harness** that runs each source over the fixture set and reports the
   metrics in the gate below, deterministically and re-runnably.
4. **The adoption decision, executed and recorded**, per the gate. Adopted or not,
   write a decision record into `memories/decisions/` with the numbers, the fixture
   set, the versions tested, and the open UNVERIFIED items.
5. **Custom analysis preserved**: energy/multiscale, builds/drops, tension, timeline
   remain Twinklr's regardless of outcome.
6. **Optional extras, not core dependencies.** Same rule as P2P-T7: `beat-this` and
   `all-in-one-mlx` are optional extras; the default suite installs and passes without
   them.

## Adoption gate — pre-committed numeric criteria

**These numbers are fixed by this spec before any measurement. Do not adjust them
after seeing results.** Plan note, verbatim:

> - T8's A/B criteria must be numeric and pre-committed (beat F1 / downbeat F1 /
>   section-boundary tolerance on the fixture set) — no post-hoc judgment.

Metrics (standard MIR definitions; state the tolerance in the harness output):

| Metric | Definition | Tolerance |
|---|---|---|
| **Beat F1** | F-measure of detected vs annotated beat times | ±70 ms matching window |
| **Downbeat F1** | F-measure of detected vs annotated downbeat times | ±70 ms matching window |
| **Section-boundary hit rate** | fraction of annotated section boundaries matched by a detected boundary | ±0.5 s (report ±3 s as a secondary, looser figure) |

Adoption rules, evaluated on the **mean across the fixture set**:

- **Adopt `beat-this` for beats+downbeats** if it beats the current DSP by
  **≥ 0.05 absolute on downbeat F1** *and* is **no worse than 0.02 absolute on beat
  F1**. Rationale: downbeats are where the DSP competes against nothing maintained,
  and downbeat truth is what the bar-numbered plan contract rests on.
- **Reject** (keep the DSP) if `beat-this` is worse on beat F1 by > 0.02, or fails to
  clear the downbeat margin. Record the numbers; the proposal already absorbs this
  outcome ("beat-this A/B losing to the current BeatGrid on our fixtures (keep DSP,
  revisit later — absorbed)").
- **Adopt All-In-One for section labels** if section-boundary hit rate at ±0.5 s
  improves by **≥ 0.10 absolute** over the current structure detector. Otherwise keep
  the custom structure path.
- **Independent decisions.** Beats/downbeats and structure are adopted or rejected
  separately; a win on one does not carry the other.
- **Regression guard, absolute**: no adopted source may reduce beat F1 below the
  current DSP's measured value by more than 0.02, on any single fixture, without an
  explicit owner override recorded in the decision record.
- **Determinism requirement**: an adopted source must produce identical output across
  two runs on the same input. A non-deterministic source is rejected regardless of
  accuracy — CC-8 records determinism violations in "deterministic" layers as an
  existing defect class, and the render path's reproducibility depends on the grid.

Publication figures for context only, not gate inputs: `beat-this` reports GTZAN beat
F1 89.1 / downbeat F1 78.3. **Our fixtures decide, not GTZAN.**

### Non-goals

- The stems stage (**P2P-T7**, lands first in the same lane).
- The `--dbn` flag: explicitly skipped — "the optional `--dbn` flag reintroduces
  madmom — skip it."
- madmom or canonical `allin1` (install-broken on modern stacks).
- Replacing energy/builds/tension/timeline analysis.
- Python 3.13 migration (Phase 4).

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/sequencer/timing/beat_grid.py` — the consumed artifact;
  `from_song_features` / `from_resolver` are the seams where a source plugs in.
  **Do not change `BeatGrid`'s public shape.**
- `packages/twinklr/core/audio/rhythm/` and `structure/` — current DSP producers;
  they become the `dsp` implementation of the new source interface.
- New: the source interface, the two model-backed implementations, the A/B harness,
  and the fixture set + annotations.
- `pyproject.toml` optional extras for `beat-this` and `all-in-one-mlx`.
- `memories/decisions/` — the decision record (per `AGENTS.md`'s memory protocol:
  record provenance and date in frontmatter, link related context/change documents,
  update `memories/INDEX.md`).

Sequencing constraints copied verbatim from the plan:

> - CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both
>   halves (P1P-T4).
> - T8's A/B criteria must be numeric and pre-committed (beat F1 / downbeat F1 /
>   section-boundary tolerance on the fixture set) — no post-hoc judgment.
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.

Lane order: T7 → T8, merging before T13.

## Acceptance criteria

1. A source abstraction exists with `dsp`, `beat_this` and `allinone`
   implementations, selectable by configuration, with `BeatGrid`'s public shape
   unchanged.
2. A golden fixture set with annotated beats, downbeats and section boundaries exists
   and is tracked (or deterministically fetchable), with at least enough material to
   make the mean meaningful — **minimum 5 songs/excerpts spanning at least: one
   steady 4/4 pop track, one non-4/4 or tempo-varying track, one sparse/ambient
   track**.
3. The A/B harness reports beat F1, downbeat F1 and section-boundary hit rate per
   fixture and as a mean, at the stated tolerances, re-runnably and deterministically.
4. The gate is applied **as written**; the decision (adopt/reject, per component) is
   recorded in `memories/decisions/` with the numbers, versions, fixture list and the
   open UNVERIFIED items (beat-this on Python 3.13; `all-in-one-mlx` single
   maintainer; `all-in-one-fix` PyPI presence; torchaudio wind-down).
5. If adopted: every grid consumer reads the new source through `BeatGrid` with no
   consumer-side change (P1P-T4 already unified them), and the golden render suite
   either passes unchanged or its diffs are explained as grid-truth improvements
   with BEFORE/AFTER evidence per changed fixture.
6. If rejected: the custom DSP stays, the fixture set and harness remain in the tree
   as the permanent regression guard, and the decision record says why.
7. The determinism requirement is tested (two runs, identical output) for any adopted
   source.
8. Optional extras: `uv sync` without them succeeds and the full suite passes.
9. `make validate` check-only forms pass.

## Tests

1. `test_beat_f1_on_click_track` — a synthetic click track with exactly known beat
   times; the `dsp` source must score near 1.0. Ground-truth assertion, the class the
   repo has none of.
2. `test_downbeat_f1_on_annotated_fixture`.
3. `test_section_boundary_hit_rate_on_annotated_fixture`.
4. `test_ab_harness_is_deterministic` — two runs, identical metric output.
5. `test_beat_grid_shape_unchanged` — the public interface of `BeatGrid` is pinned so
   a source swap cannot alter it.
6. `test_source_selection_from_config`.
7. **LOCAL-ONLY** `test_model_sources_run` — `beat-this` and `all-in-one-mlx` execute
   on one fixture on Apple Silicon; excluded from CI (model weights, ~78 MB download).
8. Golden render suite (criterion 5).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/audio tests/unit/sequencer -k "beat or grid or structure" -q
uv run pytest -m "not local_only" -q
uv sync --extra dev --all-packages          # must succeed WITHOUT the mir extras
```

LOCAL-ONLY (Apple Silicon, mir extras installed):

```bash
uv sync --extra mir
uv run pytest -m local_only -k "mir or beat_this or allinone" -q
uv run <ab-harness-entrypoint> --report     # produces the gate table
```

No paid API calls.

## Effort & risk

**L.** Main risk: fixture annotation quality. A gate is only as good as its ground
truth, and hand-annotating downbeats is error-prone. Mitigation: include at least one
synthetic click track where the answer is exact by construction (it validates the
metric implementation itself), and cross-check hand annotations by listening before
they become the gate. Second risk: dependency conflict — `beat-this` declares
torchaudio, which is winding down, and `all-in-one-fix` declares torch ≤2.7 against
our pin. Mitigation: optional extras, `all-in-one-mlx` (no torch) as the structure
path, and a hard rule that this task does not move the torch pin — if it cannot
resolve, report and hand to Phase 4. Third risk: adopting on GTZAN reputation rather
than our fixtures — mitigated by the gate being pre-committed here, in writing,
before any number exists.

## Routed note from P1P-T8 (2026-08-13) — measured baseline behavior

P1P-T8 gave the repository its first ground-truth assertions
(`tests/unit/audio/test_ground_truth.py`). Three properties of the *current* librosa
detectors were measured against a synthetic 120 BPM click track (sr=22050, exact by
construction). They are baseline behavior, not defects P1P-T8 fixed, and they are the
numbers any A/B here must beat — or must consciously accept.

1. **Tempo is quantized by the tempogram's integer lag grid.** At the app's default
   `hop_length=512` a true 120.0 BPM click reports **117.4538 BPM**. A 0.5s beat period
   is 43.07 frames at that hop; only integer lags are reachable, so the two candidates
   are 60·(22050/512)/22 = 117.45 and /21 = 123.05. **±2 BPM of truth is unreachable at
   hop 512** — the error is not the detector mis-hearing the beat, it is the grid. At
   `hop_length=441` the same period is exactly 25 frames and the answer is 120.0000.
   `test_detected_tempo_matches_click_track_120bpm` therefore runs at 441, and
   `test_detected_tempo_at_default_hop_is_frame_quantized` pins the hop-512 value.
   *Consequence for this task:* any tempo-accuracy comparison run at hop 512 is
   measuring the frame grid as much as the estimator. Fix the hop, or report tempo
   error in frames rather than BPM, before declaring a winner.

2. **Beat positions carry a systematic one-frame lag.** At hop 441 all 19 detected
   beats are **+0.0200s late — exactly one hop, uniformly**, from the onset-envelope
   rise. The assertion `max(errors) <= hop_s` therefore passes with **approximately
   zero margin**: it reads as "beats align within one hop" but the real content is
   "every beat is one frame late, none is two". A candidate detector that removes this
   bias will look no better under a one-hop tolerance — compare *signed mean* offset,
   not absolute error, or the A/B will score a genuine improvement as a tie.

3. **The t=0 click is never detected** (19 of 20). There is no onset rise in front of
   the first click. Any recall metric computed over a fixture whose first event sits at
   t=0 starts at 95% for structural reasons; either pad the fixture or exclude the
   first event from the metric.

Key detection was also pinned (`c_major_tonal_audio` → C major, confidence 0.72–0.93)
and needed no allowance. Fixtures are synthesised in-process: no network, no audio
files. Reuse them rather than re-deriving — the click track this note measures is
`tests/unit/audio/conftest.py::click_track_120bpm`, which is also the "synthetic click
track where the answer is exact by construction" that this spec's risk section requires.

> Verifier addendum (2026-08-13): the +1-frame bias above is a property of the
> *current* onset-envelope pipeline, not of the fixture. After any detector swap
> (beat_this, allinone), re-measure the signed mean offset rather than assuming the
> bias persists or was fixed — the method routes forward; the number is
> baseline-specific.

## Implementation handoff (2026-08-14)

**Status:** implemented; the fixed gate rejected both model candidates because a
complete five-fixture result could not be produced offline under the repository's
declared dependency constraints. The default remains `dsp`. Independent verifier and
owner review remain required; this executor does not self-approve.

### Pre-committed gate applied

The implementation encodes the gate from this specification without changing it:

- adopt `beat_this` rhythm only when the complete five-fixture candidate mean is
  deterministic, downbeat F1 improves by at least `0.05`, mean beat F1 is no worse
  than `-0.02` relative to DSP, and no individual fixture's beat F1 is worse than
  `-0.02` relative to its matching DSP fixture;
- adopt `allinone` structure only when the complete five-fixture candidate mean is
  deterministic, strict (`±0.5 s`) section-boundary hit rate improves by at least
  `0.10`; the loose (`±3.0 s`) rate is reported but is not an adoption rule;
- before either decision, DSP and candidate results must each contain exactly the
  five unique fixture IDs from the loaded committed manifest; `fixture_count` alone
  is not sufficient;
- a missing fixture result, optional dependency, or model weight is an incomplete
  candidate result and therefore a rejection. Unavailable/unmeasured metric means
  serialize as `null`, never as fabricated numeric zero scores.

### Measured committed-fixture baseline

The deterministic harness ran the DSP source twice over the five committed synthetic
fixtures. All values below are direct harness output; no model-candidate metric was
available and none is represented as zero.

| Fixture | Beat F1 (`±70 ms`) | Downbeat F1 (`±70 ms`) | Section hit (`±0.5 s`) | Section hit (`±3.0 s`) | Signed beat offset |
|---|---:|---:|---:|---:|---:|
| `steady_4_4_pop` | 1.000000 | 1.000000 | 0.000000 | 0.333333 | +0.019206 s |
| `waltz_3_4` | 1.000000 | 0.666667 | 0.000000 | 0.333333 | +0.020363 s |
| `tempo_change_4_4` | 0.655172 | 0.476190 | 0.000000 | 0.333333 | -0.021409 s |
| `sparse_ambient` | 1.000000 | 0.666667 | 0.000000 | 0.000000 | +0.020021 s |
| `syncopated_4_4` | 1.000000 | 1.000000 | 0.000000 | 0.333333 | +0.019639 s |
| **Mean** | **0.931034** | **0.761905** | **0.000000** | **0.266667** | — |

Harness output was written only to the local temporary path
`/tmp/twinklr-p2p-t8-final-report.json`; generated reports are intentionally not
tracked. The fixture manifest, synthesis instructions, annotations, metric code, and
gate are tracked and offline-deterministic.

### Adoption decision and dependency limitations

- **Rhythm: reject `beat_this`; retain DSP.** The official `beat-this==1.1.0`
  dependency resolves in the optional `mir`/`mir-beats` extra on this Darwin arm64,
  Python 3.12.13 environment. No final checkpoint was already present, however. An
  initial upstream download attempt showed a multi-hour ETA and was stopped without
  leaving a partial cache file; no candidate inference result was claimed. The
  adapter now refuses implicit network downloads and reports the explicit checkpoint
  argument, `TWINKLR_BEAT_THIS_CHECKPOINT`, and expected torch-cache location. Python
  3.13 inference remains UNVERIFIED and is still routed to Phase 4. `beat-this`
  continues to declare `torchaudio`; Twinklr added no torchaudio API usage.
- **Structure: reject `allinone`; retain DSP.** Official `all-in-one-mlx==1.0.6`
  metadata declares `librosa>=0.11.0`, while the repository deliberately pins
  `librosa>=0.10.2,<0.11.0`. Adding it to the workspace extra would require the
  forbidden core-dependency widening, so it was not declared. The source adapter is
  available for an isolated compatible Apple-Silicon environment and otherwise
  raises an actionable incompatibility message. No weights were locally available,
  so no structure-candidate metric was claimed. The single-maintainer risk remains
  open. `all-in-one-fix` PyPI presence remains UNVERIFIED and its torch ceiling was
  not substituted around the gate.

The authoritative decision record is
`memories/decisions/keep-dsp-after-mir-ab.md`. This outcome satisfies the reject path:
the current DSP stays while the fixture set, harness, source seams, provenance, and
cache isolation remain as permanent regression infrastructure.

### Runtime result

`AudioAnalyzer` selects rhythm and structure sources from configuration. One selected
rhythm result supplies `tempo_bpm`, `beats_s`, `bars_s`, and time signature; one
selected structure result supplies the final sections. Existing BeatGrid consumers
are unchanged and its public shape is pinned by test. Custom energy/multiscale,
builds/drops, tension, and timeline analysis remain in place and consume the selected
rhythm truth. Results include source/version provenance.

The under-ten-second path applies the same no-fallback rule. It returns minimal DSP
features with truthful `dsp` source/version provenance when DSP is selected. If
`beat_this` or `allinone` is explicitly selected, that adapter is invoked; an
unavailable dependency or checkpoint fails loudly rather than being bypassed by the
minimal-feature return.

The audio-features cache schema is version 5. Its identity now includes both selected
source names and adapter versions; an actual DSP-versus-`beat_this` cache miss is
covered by test.

### Exact changed-file manifest

Added:

- `packages/twinklr/core/audio/mir/__init__.py`
- `packages/twinklr/core/audio/mir/benchmark.py`
- `packages/twinklr/core/audio/mir/fixtures.py`
- `packages/twinklr/core/audio/mir/metrics.py`
- `packages/twinklr/core/audio/mir/sources.py`
- `tests/fixtures/mir/manifest.json`
- `tests/unit/audio/mir/__init__.py`
- `tests/unit/audio/mir/test_analyzer_integration.py`
- `tests/unit/audio/mir/test_benchmark.py`
- `tests/unit/audio/mir/test_fixtures.py`
- `tests/unit/audio/mir/test_metrics.py`
- `tests/unit/audio/mir/test_model_sources_local.py`
- `tests/unit/audio/mir/test_sources.py`
- `memories/decisions/keep-dsp-after-mir-ab.md`

Modified:

- `packages/twinklr/core/audio/analyzer.py`
- `packages/twinklr/core/audio/cache_adapter.py`
- `packages/twinklr/core/config/__init__.py`
- `packages/twinklr/core/config/models.py`
- `packages/twinklr/core/pyproject.toml`
- `pyproject.toml`
- `uv.lock`
- `tests/unit/audio/test_cache_adapter.py`
- `context/current-state.md`
- `context/architecture/pipeline.md`
- `docs/user-guide.md`
- `memories/INDEX.md`
- this specification

### Red to green evidence

1. Before the implementation existed, the focused new suite failed during collection
   with four missing-module/API errors (`twinklr.core.audio.mir` modules and the cache
   fingerprint).
2. The first implementation pass made the isolated MIR/cache suite green: `19 passed`.
3. The deliberately added analyzer integration test then failed because the analyzer
   had no source-selection seam. Wiring source selection and authoritative-result
   propagation made it green.
4. The first broad run exposed the core-package direct-`print` guard as its sole
   failure (`5071 passed`, one failure). Replacing it with the permitted stdout writer
   made the logging-focused suite and broad suite green.
5. The first independent verifier rejected five contracts. The remediation tests
   produced `13 failed, 9 passed`: the official BeatThis tuple was decoded backward;
   the gate had no manifest-identity argument; `None` means failed model validation;
   and the DSP, BeatThis, and All-In-One short-audio cases exposed the early bypass.
   Correcting all five produced `25 passed` in the focused source/gate/analyzer suite.
   The BeatThis regression now uses the official `Audio2Beats`-shaped
   `(beats, downbeats)` return, the gate derives its fixture means and worst-fixture
   beat delta from exact unique matching manifest IDs, unavailable means are `null`,
   and short audio honors explicit selections without fallback.

### Verification evidence

- initial `uv sync`, then `uv sync --extra dev --all-packages`: succeeded;
- `uv sync --extra dev --extra mir --all-packages`: succeeded with
  `beat-this==1.1.0`; restoring the default no-MIR environment succeeded and removed
  the ten optional model packages;
- focused MIR/cache/BeatGrid: `93 passed, 1 skipped`;
- all audio tests: `808 passed`;
- audio/sequencer beat-grid-structure focus: `233 passed, 1579 deselected`;
- golden render suite: `73 passed, 8 skipped`;
- local-only model command in the MIR environment: `1 skipped, 5108 deselected`
  because the required local checkpoint was absent;
- broad offline suite: `5072 passed, 25 skipped, 12 deselected`;
- Ruff format/check: `1321 files already formatted`, all checks passed;
- mypy: success on `713` source files;
- `make check-all` equivalent full gate: `5072 passed, 37 skipped`, 87% coverage,
  all quality checks passed.

Post-verifier remediation was revalidated independently from the earlier author run:

- corrected source/gate/short-audio focus: `25 passed`;
- all audio tests: `823 passed, 1 skipped`;
- audio/sequencer beat-grid-structure focus: `235 passed, 1587 deselected`;
- golden render suite: `73 passed, 8 skipped`;
- remediated offline harness: five deterministic DSP fixture rows, unavailable
  candidate means serialized as `null`, separate `reject` decisions for rhythm and
  structure;
- Ruff format/check: `1321 files already formatted`, all checks passed;
- mypy: success on `713` source files;
- broad non-local suite: `5082 passed, 25 skipped, 12 deselected`;
- final `make check-all`: `5082 passed, 37 skipped`, 87% coverage, all quality checks
  passed.

`make validate` itself was attempted and correctly stopped at the repository's P0
clean-worktree guard because this handoff necessarily contains uncommitted changes.
The task expressly forbids git commands and self-commit, so the executor did not
stash, commit, or bypass that guard. `make check-all` ran the formatter, linter,
type-checker, and full coverage suite that follow the guard, and passed. No live or
paid API call was made, no commit was created, and independent verification remains
pending.
