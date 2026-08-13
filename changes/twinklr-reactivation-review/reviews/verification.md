# Verification Record

_Maps major conclusions to authoring evidence, adversarial status, runtime evidence,
limitations, and remaining risk. Verifiers are never the phase author. Updated as
phases complete. Baseline `aa8d325`._

## Stage 4 runtime baseline — RESULTS (2026-08-13)

Environment: uv-managed Python 3.12.13, `uv sync --extra dev --all-packages` clean
(first attempt failed on network — scipy timeout + DNS loss — classified ENVIRONMENTAL
and retried successfully with `UV_HTTP_TIMEOUT=180`). All commands check-only; post-run
`git status` confirms zero source mutation. Logs in session scratchpad
(`format-check.log`, `ruff-check.log`, `mypy.log`, `pytest.log`).

**Headline: `main` cannot pass its own `make validate` gate from a clean checkout —
broken in four independent ways.**

| Check | Command | Result | Classification |
|---|---|---|---|
| Format | `uv run ruff format --check .` | exit 1 — **13 files would be reformatted** (1178 clean) | BASELINE |
| Lint | `uv run ruff check .` | exit 1 — **150 errors** (8 safe-fixable) | BASELINE |
| Types | `uv run mypy .` | exit 1 — **4 errors** in `recipe_builder/admission.py` (`RecipeCandidate` missing `target_recipe_id`/`proposed_metadata_patch` — attr-defined), 666 files checked | BASELINE — and in the exact subsystem the last real code commit (`d9c6ae1`, 2026-04-01) touched |
| Tests | `uv run pytest tests/ -v` | exit 1 — **120 failed, 4040 passed, 15 skipped** in 2m42s | see breakdown |

**Test-failure classification (all 120 accounted for):**

- **60 — tests for nonexistent `scripts/build/*` tools** (`generate_effect_templates`,
  `upgrade_template_layers`, `backfill_template_metadata`, `align_templates`,
  `audit_template_structure`, `build_coverage_gap`): `FileNotFoundError` on the script
  path. BASELINE, never-passing on this tree. Extends the phase-7-verified class
  "automation authored for entry points that never existed" — now including 60 tests.
- **52 — missing gitignored `data/templates/index.json`** (display composition 50,
  `recipe_builder/test_pipeline` 1, `agents/test_taxonomy_utils` 1). BASELINE
  structural defect: the unit suite depends on corpus-generated local data that no
  clean checkout can have. Confirms at test level the phase-5/6 finding that the repo
  carries no display templates.
- **8 — NLTK resource not downloaded** (`averaged_perceptron_tagger_eng` LookupError
  in g2p/phoneme tests). ENVIRONMENTAL (one-time network download) — but "unit tests
  require a live NLTK download" is itself a finding (offline-hostile test dep).

**The known-test-failures memory is REFUTED in both directions**
(`memories/learnings/known-test-failures.md`): all four listed tests PASS at baseline
(`test_learning_context_formatting`, three `test_execute_step_*`), while 120 other
tests fail. The memory must be replaced at closeout with this verified record.

**P1-F23 CLOSED — CONFIRMED, worse than suspected**: `uv build` exits successfully for
both packages but **both wheels are empty** (dist-info only, zero Python code; core
wheel = 4 files, cli wheel = 5). The setup.py `find_packages(where="../..")` shims
find nothing from the build sandbox. Packaging is nonfunctional end-to-end: `make
build` targets wrong directories AND a corrected invocation yields undistributable
artifacts. Worse, the build **pollutes the source tree**: it materialized a full
nested copy of the codebase at `packages/twinklr/twinklr/` plus three stray
`*.egg-info` directories (the setup.py `package_dir="../.."` misresolution in
action). Only the uv-workspace editable install path works. (All artifacts created by
this test were deleted; `git status` verified clean.)

Runtime items still open: xLights empirical tests (bare-.xsq import; 2024.10 stamp on
2026.15; shutter-closed output check from P4's V1-extension), `json_object`-on-gpt-5.6
probe (needs API key). `make validate` itself was NOT run — it would mutate 13 files
via format; check-only equivalents provide the baseline evidence without mutation, per
the review-only boundary.

## Phase 1 — foundation-and-orchestration (verifier: opus critic, non-author)

Overall: unusually accurate. **24 ACCEPTED, 8 REVISED, 0 REJECTED**, 2 confidence
upgrades to CONFIRMED (P1-F12 four retry layers; P1-F20 ruff split — verifier ran
`uvx ruff --show-settings` out-of-repo: core resolves to the weak 7-family config,
tests/CLI to the strict root config; Stage 4 no longer needs this), 4 MISSED added.

Key changes:
- **P1-F27 token-delta race: MEDIUM→MEDIUM-HIGH, scope correction REVERSED** — the
  shipped path IS affected: `profile` and `lyrics` share a wave under `asyncio.gather`
  over one shared provider, so per-stage token attribution is unreliable on the only
  production path. Blocks Stage 2's instrument-then-decide experiment (which needs
  per-arm cost/tokens). The author's "display-only" scoping was wrong.
- **P1-F1 (AcoustID/MB 100% failure): ACCEPTED, HIGH held**, mechanism reproduced
  empirically against httpx 0.28.1. Refinements: not fully silent (WARNING log +
  bundle warning); MusicBrainz is currently unreachable (only called with AcoustID
  results), so fixing AcoustID alone exposes the identical MB bug — **fix both in one
  change**. Also a 4th instance of the P7-M2 dead-docs class (user-guide tells users
  to enable it).
- P1-F3 (.env) is a duplicate of P7-F1 with a CONTRADICTING remedy — consolidated:
  one finding, MEDIUM, remedy deferred to the pydantic-settings decision.
- P1-F10: cancellation is **inert**, not coarse (cancel_token never assigned in
  production; executor check is dead code) — moves to the implement-or-delete bucket.
- P1-F15: worse than stated — config reaches ~2 of ~6 shipped agent invocations
  (`temperature` etc. unwired even for plan_agent; MH planner model is a Python
  default). Third independent confirmation of the judge-model fact — count ONCE.
- P1-F29: headline false — FSCache IS covered end-to-end (in tests/unit/io/
  test_sync_adapter.py) but coverage lives in the wrong package under a
  slated-for-deletion class and omits every failure mode. P1-F31 (delete sync
  adapter) must be sequenced AFTER migrating those tests.
- P1-F17: mutation sub-claim wrong; real defect is env vars read exactly once per
  process with no invalidation.
- P1-S1 narrowed (atomic vs durable: no fsync); P1-S2 narrowed (sanitizer passes
  `..`; containment in RealFileSystem.join is the SOLE traversal defence and is not a
  protocol requirement — unexercised by tests).

Missed findings adopted: **P1-M1** (wave failure discards completed siblings'
results — profile failure drops lyrics' finished LLM work, unrecoverable due to
P1-F4); **P1-M2** (both documented PipelineContext constructor examples raise
TypeError); **P1-M3** (cache root is CWD-relative — compounds P1-F4); **P1-M4**
(PARALLEL literally never used; CONDITIONAL set redundantly once).

Hygiene: systematic pyproject line-cite offsets; core/logging is 647 lines; 9+2
metric/state keys; ERA/T20 family corrections. Verifier concurs with NOTHING-CRITICAL
for this phase.

## Phase 2 — deterministic-audio-analysis (verifier: opus code-reviewer, non-author)

Overall: strong on dead code/schema drift; wrong or overstated on 3 of 5 priority
items; missed 4+ defects as serious as anything it found, including live DSP bugs.
**17 ACCEPTED, 5 REVISED, 1 REJECTED, 14 MISSED added (3 HIGH).**

Key changes:
- P2-F1/F2/F3 merged into one MED-HIGH compound ("the validation layer is
  decorative") — do not triple-count.
- **P2-F13 REVERSED in scope**: the MusicBrainz concurrency violation is UNREACHABLE
  today (gather gated on AcoustID candidates, which are always empty due to P1-F1;
  both flags default False). Latent, not live — BUT Stage 8 sequencing constraint:
  fixing P1-F1 without landing a rate limiter in the same change makes the violation
  live.
- P2-F14 (WhisperX no vocal gate): narrowed (whisperx defaults off; vocal_presence_pct
  IS surfaced to the lyrics agent — nothing acts on it); remedy blocked by MISSED-2
  (the vocal detector itself is misaligned).
- P2-F17 REJECTED → INFO (mechanism assumed, not read: hand-rolled correlation with
  epsilon returns 0.0 deterministically on silence; no NaN path; salvage = weak test).
- P2-F24 (test realism) revised to the defensible form: real ground-truth assertions
  exist (~15, incl. a reference-loop Foote check) but **no tempo value, beat position,
  or key label is ever asserted against a known correct value anywhere in the repo**.
- P2-F6: the DEAD tempo-changes implementation is the package's exported public API
  (rhythm/__init__ imports from beats) — severity up to MEDIUM.
- P2-F8: Section model and production dicts have diverged (extra fields, invalid
  labels) — "wire it in" is not a small fix; disposition revised.
- P2-F10 evidence corrected: 2 drift sites/4 broken reads, plus stronger live-code
  evidence — analyzer emits beat_confidence as float on success and [] as list in
  _minimal_features under the same schema version.

Missed findings adopted (selection): **P2-M1 (HIGH)** analyzer parallelization passes
metadata=None into the first lyrics pass; LRCLib/Genius gated on artist/title are
structurally skipped; with WhisperX on, the retry never fires → authoritative
providers never consulted, ASR outranks synced lyrics (inverts the pipeline's declared
order); WhisperX-off cost: lyrics resolved twice per analyze. **P2-M2 (HIGH)**
spectral/vocals.py reconstructs hop_length by inverting rounded timestamps (512→529 at
44.1kHz) → vocal-detector evidence drifts ~6-8s out of alignment over a 4-min track,
~3% of song truncated, invisible in output — live on every run; also the module
P2-F14's remedy depends on. **P2-M3 (HIGH)** independent confirmation of P1-F1
(metadata clients TypeError on first parser line; phase 2's §3.6 must be reconciled —
phase 1 is right). **P2-M4 (MED-HIGH)** builds merged after energy-sort violates the
merge's time-order assumption → builds silently vanish, output not time-ordered.
**P2-M5/M6/M7 (MEDIUM)** trim-offset guard misses rms_for_energy (leading-silence
tracks shift all section energies; fade-out offset applied twice); spectral_flatness
computed on wrong hop → misaligned parallel arrays (masked by conftest pinning
hop=512); builds/drops hardcodes 4 beats/bar despite detected time signature (33% off
in 3/4). **P2-M8 (MEDIUM)** HPSS except-Exception fallback silently collapses
harmonic_ratio to 0.5 everywhere (no log, no status; only fingerprint is a constant
hpss_perc_ratio curve). **P2-M9..M14**: mislabeled beat_confidence semantics; leaked
httpx pools (never aclosed, placeholder base URLs); dead enablement surface (env keys
read but enable_* flags never flipped — user-guide no-op class); fabricated meta
values (discrimination hardcoded 0.5, real computation commented out); more dead
structure code; dead gradient_percentile preset field. SUSPECTED (unproven): MFCC fed
linear-frequency dB STFT rather than log-mel.

Hygiene: cite corrections (hints.py 187 lines; beats ranges; conftest 327 lines;
exact triplication ranges); §3.4 rewrite required; conftest's sample_song_features
fixture encodes the phantom pre-refactor schema and must be corrected with P2-F4.
Confirmed clean: §2 contracts, cache cost characterization, Foote correctness, §9
preserve list (now with three documented precompute exceptions), no in-place mutation
of shared arrays (exhaustively checked).

## Phase 3 — llm-agents-and-planning (verifier: opus critic, non-author)

**22 ACCEPTED, 12 REVISED, 12 MISSED added (4 in-scope material).** The two most
load-bearing claims are AIRTIGHT: F5 lyrics-blindness (three independent locks:
extra="forbid" model, model-object passing, the phantom fields exist in exactly 4 .j2
lines and no Python — the Lyric Context block renders one line: "Has Lyrics: Yes") and
F13 few-shot-never-delivered (both bugs confirmed; worse: the call logs assert
delivery that never happened).

Key revisions:
- **F12: 20 dead solicited fields, not 33** (9 have real readers incl.
  MacroPlan.asset_requirements — which F17 itself cites; contradiction resolved in
  F12's favor of deletion). Cause: sweep missed whole-model model_dump() prompt dumps.
- **F24 RAISED to MED-HIGH, "does not currently fire" DELETED**: profile+lyrics share
  a gather wave over one memoized provider — every per-stage token figure on the
  shipped path is already wrong (independently confirms P1-F27). Stage 2's cost
  instrumentation is blocked until fixed; fix requires threading the LLMResponse out.
- **F23 CLI-gate claim REJECTED**: the CLI only checks OPENAI_API_KEY is non-empty,
  never selects provider — an anthropic config.json runs end-to-end. Anthropic's
  latent bugs (incl. M-I: [-4:] windowing produces assistant-first message lists the
  API rejects on turn 3) are latent-reachable, not dead.
- F28 split: unreachable-LOC hygiene (LOW) + absent cost controls as a HIGH
  reactivation gate; the stated re-bill mechanism rejected (resize makes validation
  tautological) — the real re-bill risk is the non-atomic, error-swallowing catalog
  (M-L).
- F18: isprintable() mechanism INVERTED in text (it rejects \n; sanitize.py re-admits
  it) — conclusion stands; severity re-anchored on shipped hops 1-2.
- F7 extended: the entire judge_context_builder hook is dead (no caller passes it) and
  its signature cannot receive prior feedback — remedy larger than wiring.

Missed findings adopted: **P3-M-A (HIGH)** success_threshold documented+fully threaded
but inert — JudgeVerdict.enforce_status_matches_score hardcodes 7.0/5.0 and the
controller compares status only; new dead-config member, and it qualifies F36's KEEP
(the "strength" is the mechanism that kills the knob). Ablation arms varying judge
strictness would compare identical configs. **P3-M-B (MED-HIGH)** documented
max_iterations=0 ("skip judge") passes AgentOrchestrationConfig (ge=0) then CRASHES
IterationConfig (ge=1) — actively failing documented value. **P3-M-C (MEDIUM)** "every
model call goes through AsyncAgentRunner" is false repo-wide (recipe_builder
generation + FE normalization/llm_review call directly) — reword to shipped-path-only;
qualifies the §9 one-chokepoint claim. **P3-M-D (HIGH)** ONESHOT schema-repair never
shows the model its failing output — every judge + profile/lyrics/corrector repair
attempt is a blind full-cost resample (answers §5's open question: repair feedback
structurally cannot work on ONESHOT). **P3-M-E (HIGH)** failed LLM calls produce no
log record and retain full prompts in memory. **M-F/G/H (MEDIUM)** SDK×manual retry
amplification (≤9 requests/call); unparseable JSON gets zero retries while schema
violations get 5, and it kills the pipeline (the commonest json_object failure is the
one treated as unrecoverable); conversation store never evicted. **M-J/K/L (HIGH,
assets, reactivation-gated)** gather-without-return_exceptions discards paid siblings;
cross-song reuse-key collisions; catalog sole-record-of-paid-work written non-atomic
with parse errors swallowed.

Hygiene: §5 counts (88 test files, two conftests exist), §4.3 dead-member list
corrected (planner_agent doesn't exist), F12↔F17 resolution, line-drift fixes, §2
qualification. Path-prefix pre-emption noted (assets/=agents/assets/, correct as
written). Confirmed clean: 19 findings verbatim incl. F1 CRITICAL prose-only
MacroPlan.

## Cache-fingerprint addendum (phase 3 verifier, gates modernization M1)

**Model ID: IN the key for all five LLM stages** (each orchestrator's get_cache_key
includes model/planner_model+judge_model — cites: profile/lyrics orchestrators :85-86,
macro :133-134, MH :243-244, group :137-138). **Prompt-pack content/version: in NONE.**
Premise correction: `compute_fingerprint` has ZERO callers (another dead helper);
execute_step builds keys directly (execution.py:113-119) from each stage's
cache_key_fn.

Consequences: **M1 retarget SAFE** (clean miss, regenerates). **Prompt edits UNSAFE**
once cross-run caching works: identical fingerprint serves plans from the old prompt —
directly masking the recommended prompt fixes (F5 lyric wiring, F14
recommended_sections). Only invalidation lever is the hand-maintained `cache_version`
literal ("1" everywhere; a lone "4" at holistic_stage.py:138 shows someone hand-bumped
once). pack.yaml's pack_version is inert and inverted — the signal must be built, not
read. Interlock for Stage 8: **fixing the session-ID cache defeat (P1-F4) makes the
stale-prompt hazard live the same day — land prompt-content hashing in the same
change.** Also: temperature in profile/lyrics keys but not planner keys;
min_pass_score is in planner keys yet behaviorally inert (M-A) — a threshold change
forces full uncached re-plans that cannot differ (experiment confounder).

## Phase 4 — moving-heads-rendering (verifier: opus code-reviewer, non-author)

**16 ACCEPTED, 11 REVISED, 0 outright REJECTED (2 F20 sub-rows rejected), 8 MISSED
added.** Every exact-behavior claim re-derived independently (own AST pass over all 37
templates, own arithmetic). **Both CRITICALs and the V-categorical REFUTES verdict are
exactly right and safe for Stage 8.**

Key changes:
- **F1 (CRITICAL, held)**: overwrite unconditional, no surviving path — but NOT
  untested: `tests/integration/test_handler_categorical_params.py` pins the defect
  (passes intensity as both argument and params key — production never supplies the
  key; one test is literally named `..._currently`). §5's "handlers: 0 test LOC" is
  false; remediation must CHANGE this test. F1a bigger: 10 patterns have exactly one
  categorical entry — a naive fix KeyErrors 27 of 29 patterns; fix = guard + data
  fill-in across the movement library.
- **F2 (CRITICAL, held, extended)**: THREE grids, not two — the planner's bar numbers
  come from a nominal-tempo, zero-anchored, FLOORED conversion in phase 3's code
  (`agents/.../context.py:246-271`, quantizes section starts up to ~2s at 120 BPM)
  before the renderer's average-grid and the timing tracks' detected grid diverge.
  Fix site spans phases 3+4 (cross-phase entry added). snap_to_nearest_bar/
  get_bar_start_ms have zero callers REPO-WIDE.
- **F9 RAISED MEDIUM→HIGH**: calibration is arithmetically annihilated (every
  center_offset=0.5 → (c-0.5)*amplitude = 0); worked example shows emitted DMX
  76.5-178.5 against a calibrated [110,145] — mechanical-limit exposure on physical
  fixtures, nothing re-clamps.
- **F4 census corrected** (34/1/2, not 35/1/2): 1-bar sections render nothing for ALL
  37; 1-3-bar for 35/37. **F8 → ~67 outcomes** (7 HOLD/BLACKOUT-dimmer templates are
  preset-invariant); strategic conclusion unchanged. **F7 half-wrong** (dimmer period
  IS rescaled; movement half stands). **F13 → LOW/latent** (amplitude always exactly
  1.0 on live path — zero current effect; keep the F1-interaction note). **F14 →
  INFO** (movement curves fully masked; real flat-tail mechanism is the exporter's
  1.00 anchor). **F12 confidence → HIGH** (attribution corrected; pan≡tilt verified
  to 1e-12 — three patterns trace straight lines).
- **F20: two rows REJECTED** — curves/modifiers.py and providers/native.py ARE
  imported (deleting breaks the build); re-label "unreachable at runtime". All other
  inventory rows exact.
- **F22 scope corrected**: XsqAdapter has 4 integration tests; and
  `scripts/validation/_core/mh_xsq_validation.py` (587 LOC, unit-tested) ALREADY
  parses DMX settings, flags all-zero effects as CRITICAL, and cross-checks
  shutter/color/gobo — **Stage 8 step 1 = wire existing validator into CI + golden
  settings string, not write a validator** (M8). dmx_settings_builder/xsq_export
  still have zero direct tests.
- **V1 reconciled**: emitted-bytes certain (third convention-declaration site added;
  all three honored nowhere). Counter-evidence carried: the only in-repo fixture
  config uses shutter_channel=17 (outside the 1-16 window → console default). HIGH
  with the conditional stated precisely; concrete no-audio Stage 4 test spec provided
  (shutter_channel=6 vs 17, assert emitted E_SLIDER_DMX6 / absent DMX17).
- **V-categorical REFUTES: airtight** — zero vocabulary imports under
  moving_heads/curves/models/resolvers; no dynamic dispatch exists; census 46/253
  reproduced; no Intensity↔IntensityLevel converter anywhere.

Missed adopted: **P4-M1 (HIGH)** Template.defaults never read — all 37 templates'
dimmer_floor_dmx=60 silently dropped, dimmers drive to 0 (4th dead-config member,
only one with output consequence). **P4-M2 (HIGH)** BLACKOUT templates render FULL
BRIGHTNESS under any preset except MODERATE (fallback to SMOOTH params + a unit bug
multiplying a [0,255] int by 255 → clamps to 255) — plan-triggerable inversion on
exactly the templates planners pick for drops; verified numerically. **P4-M3
(MED-HIGH)** the third grid (cross-phase to 3). **P4-M4 (MEDIUM)** tests pin F1.
**P4-M5 (MEDIUM)** end-of-segment full-excursion snap-back in the final 1/64 for most
of the movement library (loop-ready t=1.0 anchor). **P4-M6 (MEDIUM)** frequency
silently changes amplitude — halving frequency DOUBLES physical excursion and parks
fixtures at extremes between steps (inverts SLOW/SMOOTH intent). **P4-M7 (LOW-MED)**
FIGURE8 traces a circle (verified constant radius; geometrically identical to
CIRCLE). **P4-M8 (INFO)** existing validator reuse.

Hygiene: count corrections (34/1/2, 35 single-loop, 26 PULSE, ~67), nine line/name
cites, F21 cross-ref, adapters restatement (generator structurally cannot consume
control_points). Confirmed clean: the 37-template annotation table (AST-reproduced),
F16's entire evidence set (all ten zero-reader config fields), F17/F23 censuses, §6
verdict ("keep the subsystem; retract the 'tested' adjective"), §13 sequencing
(reinforced by M2/M3).

## Phase 6 — corpus-intelligence (verifier: opus code-reviewer, non-author)

**3 ACCEPTED, 4 REVISED, 1 REJECTED, 5 MISSED added.** Factual findings sound; both
framing claims overturned in ways that change Stage 8:

- **P6-F3 checkpoint writer — deleted, not never-built** (git archaeology): the
  original writer (`utils/checkpoint.py` + orchestrator call at b6fdfd2) wrote exactly
  the format eval-report reads, with a committed proof artifact (deleted 2026-01-23);
  replaced by an adapter nothing ever called (deleted 2026-02-01) — an abandoned
  migration that silently dropped a working capability (P7-F4/F5 class). Restoration
  is ~10 lines with a reference artifact — CHEAPER than the phase scoped. TRAP: the
  inner plan schema drifted (historical `templates:[...]` vs today's `template_id` XOR
  `segments`) — historical artifacts are NOT replayable; the restored writer must
  serialize today's model. `JobConfig.checkpoint` (zero readers) named as 4th
  dead-config member in this scope.
- **Determinism headline REJECTED as stated** (four counts): normalization/ is
  LLM-driven (`llm_review.py:32` hardcodes gpt-4o-mini on a raw client — **P6-M1
  MED-HIGH: an LLM call site outside the entire agent framework; any M1 retarget grep
  of the agent layer misses it**); recipe_builder generation is LLM-driven; unseeded
  `random.shuffle` in exemplar selection; random-UUID identity. Narrow the claim to
  the traced miner→synthesizer→classifier path (which IS deterministic).
- **P6-F5 vendor IP: HIGH→MEDIUM** — nothing vendor-derived is redistributed today
  (promotion targets gitignored data/, no index.json tracked, all 37 shipped templates
  hand-authored with zero corpus markers); provenance hooks already exist
  (RecipeProvenance.source, ProfileRecord vendor identity). Reframed as a named Stage
  8 gate: resolve source licenses BEFORE resuming mining or distributing mined
  recipes.
- **P6-F2 remedy REVISED: extract to sibling repo, not freeze in-tree** — inbound
  coupling is exactly 3 files (all display-side, already DEFER); freezing still taxes
  every mypy/ruff/pytest run (~2,900 of 4,040 passing tests, 128 test files);
  extraction is Stage 2's SPLIT-OUT arm made concrete.
- Test-investment claim qualified by Stage 4: substantial authored suite that cannot
  fully execute from a clean checkout.

Missed adopted: **P6-M2 (MED-HIGH)** random UUIDs as corpus identity
(`ingestor.py:224` uuid4 for package_id while computing zip_sha256 on the same lines;
profile_id = uuid-based PK) — re-profiling the same archive creates new primary keys;
INSERT OR REPLACE cannot dedupe; corpus accumulates duplicates. The concrete mechanism
behind "premise unvalidatable"; content hashes are computed and discarded at every
site. **P6-M3 (MEDIUM)** the repo-wide mypy gate is cleared by renaming ONE reused
loop variable in admission.py (:72/:105 RecipeCandidate rebound at :113 to
MetadataEnrichmentCandidate; runtime correct — Stage 4's mypy line is NOT a live
crash). **P6-M4** active_learning exports nothing (`__all__=[]`). **P6-M5 (CLEAN)**
zip/XML ingestion genuinely safe (zip-slip guarded, defusedxml, nested-archive cycle
protection) — recorded so Stage 8 doesn't re-litigate.

Hygiene: feature_store paths need bootstrap/ and backends/ subpackage prefixes
throughout; 128 test files not ~129 (evaluation 6 not 7); unresolved Q3 now resolved
(yes, LLM calls); active_learning "zero callers" → zero non-test callers. Verifier's
residual gaps disclosed (transaction-site sweep partial; two delegated agents killed
by session limits — all key verdicts are first-hand reads).

## Phase 5 — display-rendering-and-xlights-io (verifier: opus critic, non-author)

**11 ACCEPTED, 4 REVISED, 0 REJECTED, 6 MISSED added.** F1 (sub-beat floor) and F2
(SEQUENCED renders continuous light; one-line fix identified) re-derived and exact.

Key changes:
- **V1 STRENGTHENED, phase-4/5 conflict resolved in phase 4's favor**: the "needs
  hardware evidence" caveat was false — the repo itself declares the convention
  (`config/fixtures/dmx.py:16-17` ShutterMap.closed=0/open=255; `:94-95`
  shutter_default=255 "usually open"; `libraries/shutter.py:54-55`), all with ZERO
  production readers. The exporter forces to 0 the exact channel the repo's own
  config defaults to 255. Stage 4 now only confirms physical fixtures, not intent.
- **V-contract REVISED on two factual errors**: (1) `--xsq` is REQUIRED
  (`cli/main.py:341`) — the template branch runs on EVERY shipped run; the
  generate-fresh branch has never executed in production (and its own output —
  media_file="" — is fatal to its own parser). P5-F5's seven losses are unconditional
  today. The 1-2 day code estimate stands but the DECISION removes a required,
  always-exercised input. (2) `profiling/` DOES use XSQParser (profiler.py:13,48) —
  the parser cannot be deleted under the contract, only detached from export. Third
  export caller: reporting/evaluation/rerender.py:131.
- **F3 HIGH→MEDIUM, mechanism inverted**: in normal ordering the recipe wins and
  RHYTHM/ACCENT lane blend modes are silently DISCARDED (not emitted on BASE layers);
  restated as "lane_plan.blend_mode is structurally incapable of reaching
  RHYTHM/ACCENT output" (allocator keys 0/2/4 vs lanes emitting on 6-16). Fix
  unchanged.
- F1 sharpened: `_ms_to_planning_ref` is not the inverse of `resolve_start_ms` at all
  — constant offset of beat_boundaries[0] plus drift, then floored (every placement
  can shift a full beat).
- F4 extended: second corruption vector — add_effect appends Twinklr effects into the
  user's own layer 0 interleaved with pre-existing effects, no overlap resolution.
- F14: conclusion (low risk) survives on sandbox config alone; the provenance argument
  is FALSE — `ParamValue.expr` IS LLM-authored (recipe_builder generation
  model_validates raw LLM JSON); name the LLM→JSON→simple_eval chain as a real,
  mitigated trust boundary. The security test asserts the opposite of production
  behavior (production swallows the raise).
- F15: harvest is not drop-in — the registry must be SEEDED from the parsed
  template's EffectDB (which is precisely the F4 fix); sequence as one change.
- F10: compat converters have zero production callers (fully dead, delete cheaper);
  third re-export site found.
- F11 upgraded to CONFIRMED via the Stage 4 run (52 failures on missing
  data/templates).
- F12: conclusion held, stated mechanism corrected (harm comes from trimming against
  short surviving nested neighbours, not eclipse-drops).

Missed adopted: **P5-M1 (MED-HIGH)** unrecognized effect type silently renders as flat
`On` (unvalidated LLM-emitted effect_type → registry fallback; warning never reaches
WriteResult/trace) — merge with F8; the concrete "wrong output nobody notices" answer.
**P5-M2 (MEDIUM)** _layer_blend_modes never reset across compose() calls (latent).
**P5-M3 (LOW-MED)** fresh emitters also disagree on sequenceTiming (50ms vs 20ms), and
the MH path applies no quantization at all while display snaps to 20ms — add to Stage
4 golden protocol. **P5-M4 (LOW)** palette index 0 emitted as absent attribute —
golden-diff checklist. **P5-M5 (INFO)** SequenceAnalyzer dead-chain extension.
**P5-M6** flag: F1's fix must account for the intentional section_start_bar=0
convention or it breaks _compose_placement_compiled.

Hygiene: two off-by-ones; all other counts verified (incl. zero TODOs across 18.7k
LOC, no sample .xsq in git history). Confirmed clean: architecture maps, V4 table,
XML-hygiene assessment (defusedxml both paths, no injection even with unescaped
settings), §12 defer-but-harvest recommendation (verifier concurs, subject to
seeding).

## Phase 7 — interfaces-and-engineering (verifier: opus critic, non-author)

Overall: substantively right about *what* is broken; corrected on *why* in three
places. 3 ACCEPTED, 11 REVISED, 1 downgraded to INFO, 4 MISSED findings added.

| ID | Verdict | Severity | Key correction |
|---|---|---|---|
| P7-F1 dotenv illusion | REVISED | HIGH→MEDIUM | CLI failure is loud with remedy printed; the deceptive part is `make env-check`'s "✓ set" after grepping only the file. Prefer deleting the .env option + fixing env-check over adding python-dotenv |
| P7-F2 pipeline_guide dead paths | REVISED | HIGH | "Never existed" true for 6/10 refs; 4 are stale-after-deletion (scripts deleted 2026-02-24, `82aaf38`). Remedy redirected: mark guide as describing the ABANDON-candidate subsystem, don't rewrite toward it |
| P7-F3 make info dead paths | ACCEPTED | MEDIUM | include `make info` + `.PHONY` cleanup (MISSED-4) |
| P7-F4 broken test targets | REVISED | MED-HIGH | Causal story disproved: the four referenced test files **never existed at any path in 148 commits** — automation authored for entry points that never worked (distinct remediation class; flag to Stage 5/8) |
| P7-F5 coverage script | REVISED | LOW-MED | Script DID exist; deleted 2026-01-30 (`c67bbdd`); restorable via `git show c67bbdd^:…` |
| P7-F6 validate mutate-then-test | REVISED | HIGH→MEDIUM | The git-clean guard pattern already exists in the Makefile (`lint-fix-unsafe-apply`) just not on `validate`; `make lint/type-check/test` are CI-safe today — missing piece is only `ruff format --check` |
| P7-F7 integration markers | REVISED | MEDIUM | Real numbers stronger: 14 of 16 files unmarked (not 25-file base); `pytest -m integration` selects 2 files |
| P7-F8 hardcoded display graph | REVISED | MED→MED-HIGH | Merge with MISSED-1: "the shipped CLI is correct only for the author's own display" |
| P7-F9 display not CLI-exposed | REVISED | MEDIUM→INFO | Stage 2 already ruled DEFER — not a defect under that decision |
| P7-F10 marker-less collection | ACCEPTED | LOW | narrower harm than stated |
| P7-F11 scripts README | ACCEPTED | LOW | proportionate |
| P7-F12 utils/video_demo orphan | REVISED | →LOW | orphan confirmed, no reachable harm |
| P7-F13 pyright third config | ACCEPTED | LOW | also narrower in scope (excludes tests/scripts/utils, reportMissingImports none) |
| P7-F14 no LICENSE | ACCEPTED | MEDIUM | duplicate of discovery §7.8/Stage 2 — hand to Stage 8, don't double-count |
| P7-F15 no centralized LLM fake | REVISED | MED-HIGH→MEDIUM | 57 files confirmed; harm inferred not demonstrated; sequence AFTER Stage 2's instrument-then-decide (may harden tests for code slated for deletion) |
| P7-F16 stale context claim | REVISED | LOW→INFO | already cited in discovery §4 |

**Verifier-added findings (adopted):**

- **P7-M1 (MED-HIGH, CONFIRMED)**: `cli/main.py:208` passes literal `fixture_count=4`
  into the planner prompt path (`stage.py:145` → `orchestrator.py:75`) while resolving
  the user's real fixture config three lines later — any non-4-fixture rig gets a
  planner told a false count on the only shipped path. `min_pass_score=7.0` likewise
  hardcoded (`main.py:211`). Merged narrative with P7-F8.
- **P7-M2 (HIGH, CONFIRMED)**: dead-config-class verification (Stage 2 item 5, phases
  1+7): `docs/user-guide.md` documents as live: `token_budget` (:146, no-op),
  `judge_agent.model` (:148, never wired), `channel_defaults.{shutter,color,gobo}`
  (:152-154, zero readers), `checkpoint` (:157, zero readers), a false resume promise
  (:296), `logging.level` (:121, bypassed), and shutter/color/gobo curve claims
  (:245, disproved). **Every one fails silently. The user guide is not a reliable
  behavior description — confirmed as a CLASS.**
- **P7-M3 (MEDIUM)**: `docs/developer-guide.md:348` scripts table has 2 of 5 rows
  pointing at nonexistent files.
- **P7-M4 (LOW)**: `.PHONY` covers ~20 of 39 targets — fold into P7-F3.

**Hygiene corrections the author must apply to the phase file**: counts (39 targets
not 30; 16 integration test files not 25; 11 marker hits across 2 files; 404 test
files / 488 py files), before Stage 5 consumes it.

**Confirmed clean**: CLI structural description, 57-file mock count, LICENSE absence,
pyright config, single Jekyll workflow, scripts triage table, architecture-worth-
preserving list.
