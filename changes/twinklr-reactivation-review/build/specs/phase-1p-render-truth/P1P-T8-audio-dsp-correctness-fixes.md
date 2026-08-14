# P1P-T8 — Audio DSP correctness fixes

Phase: 1P (Render Truth) · Lane: A (audio truth, parallel to R) · Executor: opus · Verifier: opus · Depends on: P0-T4, P1P-T7

## Objective

Repair the live correctness defects in the deterministic DSP core — the layer the product
principle calls "deterministic code handles precision" — and give the repository its first
ground-truth assertions, so "the analysis is accurate" stops being an untested claim. The
review's KEEP verdict on this subsystem was explicitly conditional on these fixes.

## Evidence & background

Findings: **SF-1** = **P2-M2 / M4 / M5 / M6 / M7**, plus **P2-M8**, **P2-F1** (the merged
validator compound), **P2-F24** (ground truth), **P2-F2/F3** (folded into F1).

The phase's own conditional verdict, verbatim from
`reviews/phases/deterministic-audio-analysis.md` §6:

> **KEEP the architecture; these three specific, live correctness bugs must be fixed before
> the DSP core's output can be trusted at the precision the product's "deterministic code
> handles precision" principle implies.**

Line numbers are hints from baseline `aa8d325`. Re-verify before editing.

### 1. Vocal-detector hop-length reconstruction (P2-M2, HIGH, live every run). Verbatim:

> `spectral/vocals.py` reconstructs `hop_length` by inverting rounded (`round(...,3)`)
> timestamps rather than receiving the real value — at the app's default
> `sr=44100`/`hop_length=512`, this recovers `529` instead of `512`, misaligning the vocal
> detector's RMS computation by ~6-8 seconds over a 4-minute track (≈3% of a song),
> silently, on every run; live, not an edge case; also blocks P2-F14's remedy.
>
> Evidence: `spectral/vocals.py:43-46`; `spectral/basic.py:43` (`as_float_list(times_s, 3)`,
> source of the rounding); `analyzer.py:574` (call site passing the rounded array).
>
> Fix: pass the real `hop_length` through explicitly instead of reconstructing it from
> rounded times.

Re-verified in the current tree, `spectral/vocals.py`:
`hop_length = int(sr * (times_s[1] - times_s[0])) if len(times_s) > 1 else 512`.

### 2. Builds merge violates time order (P2-M4, MED-HIGH). Verbatim:

> `energy/builds_drops.py` sorts the builds list by `energy_gain` descending (line 284)
> **before** the adjacent-build merge loop (287-304), which assumes list order is
> chronological (`gap = build["start_s"] - last["end_s"]`) — once sorted by energy, that
> assumption breaks, causing incorrect merges and a returned `builds` list not guaranteed to
> be time-ordered.
>
> Fix: sort only for the "keep most significant" selection step, or re-sort by `start_s`
> before the merge loop.

### 3. Trim-offset guard misses `rms_for_energy` (P2-M5, MEDIUM). Verbatim:

> `structure/sections.py`'s trim-offset reuse guard (`_pass_precomputed = start_offset_s ==
> 0.0`, line 290) correctly gates chroma/onset/STFT/HPSS reuse but **not** `rms_for_energy`,
> which is passed unconditionally (lines 323, 340) despite being computed on the original
> (untrimmed) timeline while boundaries/beats are on the trimmed (work) timeline — any track
> with leading silence gets every section's energy read from the wrong offset.
>
> Fix: offset-correct `rms_for_energy` before passing it into work-timeline-indexed
> functions, or include it in the `_pass_precomputed` guard.

The phase plan adds: *"fade-out offset applied twice"* — the same offset bug on the tail.

### 4. `spectral_flatness` hop mismatch (P2-M6, MEDIUM). Verbatim:

> `spectral/basic.py`'s `spectral_flatness` computation omits `hop_length=hop_length`
> (unlike the three sibling calls in the same function), so it runs at librosa's default hop
> rather than the job's configured hop — invisible under default config (both happen to be
> 512) but silently misaligns against `times_s` and every other spectral array under any
> non-default `hop_length` job config.
>
> Evidence: `spectral/basic.py:27-38` (contrast with sibling calls);
> `tests/unit/audio/conftest.py` pins `hop_length=512` throughout, masking the bug in tests.

### 5. Hardcoded 4 beats per bar (P2-M7, MEDIUM). Verbatim:

> `energy/builds_drops.py` hardcodes 4 beats per bar (`bar_duration_s = 60.0 / tempo_bpm *
> 4`) for build/drop window sizing, ignoring the time signature already detected upstream —
> a track in 3/4 gets windows sized ~33% too long.
>
> Evidence: `energy/builds_drops.py:88`; `analyzer.py:503-506` (time signature already
> available and discarded for this purpose).

Re-verified: `energy/builds_drops.py:88` is
`bar_duration_s = 60.0 / tempo_bpm * 4  # 4 beats per bar`, consumed at `:94`, `:117`
(`search_window_s = bar_duration_s * 2`) and `:177`.

### 6. HPSS silent collapse (P2-M8, MEDIUM). Verbatim:

> `harmonic/hpss.py`'s `compute_hpss` silently collapses to returning the same array for both
> harmonic and percussive components on any exception, with no log line and no status flag —
> downstream `harmonic_ratio` calculations (e.g. vocal detection) then compute a constant
> `~0.5` across the whole track with no visible signal that HPSS failed.
>
> Evidence: `harmonic/hpss.py:18-24`; `spectral/vocals.py:59`
> (`harmonic_ratio = rms_h / (rms_h + rms_p + 1e-9)`, collapses when `y_harm == y_perc`).

### 7. The decorative validator (P2-F1, MED-HIGH, merged from F1+F2+F3). Verbatim:

> `validate_features` (`validation/validator.py:23-50`) checks: unusual tempo, too-few
> beats, low key confidence, irregular beat spacing, no sections, low downbeat
> confidence. Checks 1, 2, 4, 5 correctly match the current schema. Check 3 reads
> `result["key"]["confidence"]` (`validator.py:31`) — but `analyzer.py` never writes a
> top-level `"key"` key on the normal (≥10s) path; key data lives at
> `features["harmonic"]["key"]` (`analyzer.py:684`). `result.get("key", {})` therefore
> always returns `{}`, `key_conf` defaults to `0`, and `0 < 0.3` is always true — the
> "Low key detection confidence: 0.00" warning fires on **every single production
> run** regardless of actual key-detection quality. Check 6 reads
> `result["rhythm"]["downbeat_meta"]["phase_confidence"]` (`validator.py:48`) —
> `analyzer.py` discards `phase_confidence` entirely when building `features["rhythm"]`
> (`analyzer.py:666-669` …); the check's chained `.get(...)` calls silently fall through to
> a hardcoded default `1.0`, so `1.0 < 0.4` never fires — permanently dead. And regardless of
> whether checks 3/6 are fixed, the entire return value is only ever logged at DEBUG
> (`analyzer.py:696-698`) and never reaches `SongBundle.warnings` or any caller …
> **Sequence matters: fix the schema-alignment of checks 3/6 and the discard together, not
> independently.**

The phase plan's framing: *"retire-or-wire the decorative validator (results currently
discarded at DEBUG with one spurious warning every run)"*.

### 8. No ground-truth assertions (P2-F24, HIGH, revised to the defensible form). Verbatim:

> **The defensible, narrower claim stands**: **no test anywhere in the repository asserts a
> detected tempo value, beat position, or key label against a known-correct reference
> value** … `click_track_120bpm`'s known 120 BPM (`tests/unit/audio/conftest.py:16-111`) is
> used by only two files (`test_hpss.py`, `test_bands.py`) for weak, non-tempo assertions
> ("percussive energy > 0"); no rhythm test (`test_beats.py`/`test_tempo.py`) uses it at
> all, and `tests/integration/audio/test_pipeline.py`'s explicit `beat_freq = 2.0` (120 BPM)
> synthetic WAV is never checked against detected tempo — only `tempo_bpm > 0`.
>
> Disposition: FIX (add explicit tempo/beat/key ground-truth assertions using the fixtures
> that already exist — this is a test-writing task, not new tooling).

## Current behavior

- Vocal detection runs its RMS at hop 529 instead of 512 (at default `sr`), drifting ~6–8 s
  over a 4-minute track and truncating ~3% of the song, invisibly, on every run.
- Builds are energy-sorted before a merge loop that assumes chronological order, so builds
  can be mis-merged or silently dropped, and the returned list is not time-ordered.
- Section energies are read from the untrimmed timeline on any track with leading silence.
- `spectral_flatness` is computed at librosa's default hop, masked by the test suite pinning
  512.
- Build/drop windows assume 4 beats per bar regardless of the detected time signature.
- HPSS failure collapses `harmonic_ratio` to a constant ~0.5 with no log and no flag.
- `validate_features` emits "Low key detection confidence: 0.00" on every run, can never
  fire its downbeat check, and its entire result is logged at DEBUG and discarded.
- No test asserts a detected tempo, beat position, or key against a known value.

## Target behavior

1. `spectral/vocals.py` receives the real `hop_length` as a parameter; no reconstruction
   from rounded timestamps anywhere in the module.
2. Build merging operates on a chronologically-ordered list; the "keep most significant"
   selection is a separate step; the returned list is time-ordered.
3. `rms_for_energy` is offset-corrected (or gated) so section energies are read on the same
   timeline as the boundaries, and the fade-out offset is applied exactly once.
4. `spectral_flatness` uses the configured `hop_length`, like its three siblings.
5. `beats_per_bar` from the detected time signature is threaded into build/drop window
   sizing; the hardcoded `* 4` is gone.
6. HPSS fallback logs a warning and sets a status flag that reaches the bundle, so a
   constant `harmonic_ratio` is distinguishable from genuinely balanced content.
7. `validate_features` reads the current schema for checks 3 and 6 **and** its result
   reaches the caller (`SongBundle.warnings` or an equivalent surfaced channel) — both
   halves in the same change — **or** the validator is deleted outright. No third state.
8. The repository's first ground-truth assertions exist: detected tempo on the existing
   120 BPM click-track fixture, detected beat positions on the same, and a key label on a
   constructed tonal fixture.

**Non-goals.** Do not model `SongBundle.features` (P2-F10 — a Stage-2-dependent
MODERNIZE). Do not rewrite or delete the orphaned `genre/classifier.py`,
`context/{hints,unified_map}.py` (P2-F4). Do not add vocal-presence gating of WhisperX
(P2-F14) — it is unblocked by this task but is not part of it. Do not chase the SUSPECTED
MFCC mel-scale question (P2-M13-adjacent) beyond recording a result if the cheap check is
free. Do not fix the `httpx` pool leak (P2-M10) or the `enable_*` env-binding gap
(P2-M11).

## Implementation approach

Files/symbols to touch:
- `packages/twinklr/core/audio/spectral/vocals.py` — the hop reconstruction; its signature
  gains `hop_length`.
- `packages/twinklr/core/audio/analyzer.py` — the vocals call site (`:574`), the
  `features["rhythm"]` assembly (`:666-669`), the validator call/discard (`:696-698`), the
  time-signature availability (`:503-506`).
- `packages/twinklr/core/audio/spectral/basic.py` — the `spectral_flatness` call (`:36-38`).
- `packages/twinklr/core/audio/energy/builds_drops.py` — the sort/merge order (`:284`,
  `:287-304`) and `bar_duration_s` (`:88`).
- `packages/twinklr/core/audio/structure/sections.py` — `_pass_precomputed` (`:290`) and the
  `rms_for_energy` pass-through (`:323`, `:340`).
- `packages/twinklr/core/audio/harmonic/hpss.py` — the except-Exception fallback (`:18-24`).
- `packages/twinklr/core/audio/validation/validator.py` — checks 3 (`:31`) and 6 (`:48`).
- `tests/unit/audio/conftest.py` — the `hop_length=512` pinning that masks P2-M6 must be
  parameterized for at least one non-default case; `click_track_120bpm` (`:16-111`) gains
  real consumers.

Design decisions already made (do not relitigate):
- **P2-F1 is one change, not three** — schema alignment and the discard land together, per
  the review's explicit sequencing note. "Retire" is an acceptable outcome; "fix the checks
  but keep discarding" is not.
- **Pass real parameters instead of reconstructing them.** The vocals fix is a signature
  change, not a smarter inversion of the rounding.
- **HPSS failure is observable**, not silently degraded — this is the CC-3
  silent-degradation class the review names.
- **Ground-truth assertions use the fixtures that already exist.** No new tooling, no
  recorded real audio, no network.

Sequencing constraints (copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`):

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases land)
> — specs cite symbol + file, with line numbers as hints only.

From `changes/twinklr-reactivation-review/build/plan/02-phase-1p-render-truth.md`:

> **Lane A (audio truth, parallel to R — files in `core/audio/` + `api/`)**: T7 → T8.

And the review's own within-phase sequencing constraint (P2 §11), verbatim:

> **Sequencing dependency within this phase**: P2-F14's WhisperX vocal-gating fix
> should not land before P2-M2's vocal-detector alignment fix — gating on
> misaligned evidence would be a false sense of correctness.

## Acceptance criteria

- [ ] `spectral/vocals.py` contains no expression deriving `hop_length` from `times_s`;
      `hop_length` is a parameter. A test asserts the detector's frame times match the
      analyzer's `times_s` to within one frame over a ≥3-minute synthetic signal (today:
      ~6–8 s of drift).
- [ ] A test constructs builds whose energy order differs from their time order and
      asserts (a) no build is dropped by the merge and (b) the returned list is sorted by
      `start_s`.
- [ ] A test with ≥5 s of leading silence asserts section energies match those computed on
      the trimmed timeline (today: read from the wrong offset), and that the fade-out
      offset is applied once.
- [ ] With `hop_length != 512`, `spectral_flatness` has the same length as `times_s` and
      the other spectral arrays. The conftest no longer pins 512 for every test.
- [ ] With a detected 3/4 time signature, build/drop window sizes are 3/4 of the 4/4 value;
      `grep` shows no `* 4  # 4 beats per bar` in `builds_drops.py`.
- [ ] A forced HPSS failure produces a WARNING log and a status flag visible on the bundle;
      a test asserts both.
- [ ] `validate_features` check 3 reads `features["harmonic"]["key"]` and check 6 reads a
      key that exists; a test asserts the "Low key detection confidence: 0.00" warning does
      **not** fire on a well-formed feature dict (today: fires every run). The validator's
      result reaches a caller-visible surface — asserted by a test — or the validator and
      its tests are deleted.
- [ ] **First ground-truth assertions exist and pass:**
      - detected tempo on `click_track_120bpm` is within ±2 BPM of 120 (or ±2 BPM of an
        octave-corrected 60/240, with the octave handling asserted explicitly rather than
        by loosening the tolerance);
      - detected beat positions on the same fixture align to the known click positions
        within one hop;
      - a constructed tonal fixture yields the expected key label.
- [ ] `make validate` check-only equivalents pass; no pre-existing test is loosened to
      accommodate a fix (any test change is a correction, and each is called out in the
      handoff).

## Tests

TDD: write the vocal-alignment test and the tempo ground-truth test first — the first
fails by seconds, the second may reveal an octave issue that must be handled explicitly
rather than papered over.

| Test | Behavior pinned |
|---|---|
| `test_vocal_detector_frames_align_with_analyzer_times` | **P2-M2**: no hop reconstruction drift |
| `test_builds_merge_preserves_all_and_is_time_ordered` | **P2-M4** |
| `test_section_energy_correct_with_leading_silence` | **P2-M5** |
| `test_fade_out_offset_applied_once` | **P2-M5** (the phase plan's second half) |
| `test_spectral_flatness_aligned_at_non_default_hop` | **P2-M6**, with the conftest mask removed |
| `test_build_windows_respect_time_signature` | **P2-M7** |
| `test_hpss_failure_logs_and_flags` | **P2-M8**, CC-3 class |
| `test_validator_no_spurious_key_warning` | **P2-F1** check 3 |
| `test_validator_downbeat_check_can_fire` | **P2-F1** check 6 |
| `test_validator_result_reaches_caller` | **P2-F1** discard half (or: the deletion test) |
| `test_detected_tempo_matches_click_track_120bpm` | **P2-F24**, first tempo ground truth in repo history |
| `test_detected_beats_match_click_positions` | **P2-F24**, first beat ground truth |
| `test_detected_key_matches_constructed_tonal_fixture` | **P2-F24**, first key ground truth |

**Test budget:** no network, no real audio files, no LLM calls. All fixtures are
synthesized in-process (the click track already is).

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/audio -v
uv run pytest tests/integration/audio -v

# defect-specific checks the verifier runs
grep -n "times_s\[1\] - times_s\[0\]" packages/twinklr/core/audio/spectral/vocals.py        # expect: no match
grep -n "4  # 4 beats per bar" packages/twinklr/core/audio/energy/builds_drops.py            # expect: no match
grep -n "spectral_flatness" packages/twinklr/core/audio/spectral/basic.py                    # expect: hop_length passed
grep -rn "hop_length=512" tests/unit/audio/conftest.py                                       # expect: parameterized, not universally pinned
```

No LOCAL-ONLY steps. No paid API calls.

## Effort & risk

**Effort: L** — eight independent defects across six modules, plus the first ground-truth
suite.

**Main risk: the ground-truth assertions may fail against the current detectors** — e.g.
librosa reporting 60 or 240 BPM for a 120 BPM click. That is a *finding*, not a reason to
loosen the assertion. Mitigation: if a detector genuinely mis-detects, assert the
octave-corrected value **explicitly** with a comment naming the octave ambiguity, and
record the behavior in the handoff as input to P2P's MIR work — do not widen the tolerance
until the test passes.

**Second risk: fixing the vocal hop changes `vocal_presence_pct` for every song**, which
feeds the lyrics agent's prompt. Mitigation: it is currently wrong by ~3% of the track;
the change is a correction, and Lane A is serial (T7 → T8) so the lyrics-order fix has
already landed and the two effects are separable in review.

**Third risk: un-pinning `hop_length` in the conftest may surface further latent
misalignments** across the spectral suite. Mitigation: that is the point; triage anything
new as either in-scope (a hop-alignment defect of the same class) or as a recorded finding
for a follow-up task — do not re-pin the fixture to hide it.

## Completion handoff (2026-08-13)

All eight defects fixed; suite **4782 passed / 18 skipped / 0 failed**; `ruff format
--check`, `ruff check --no-cache`, `mypy .` (676 files) clean. Verified against a
disposable worktree at `92af889` with its own synced venv.

### Per-fix mechanism and discriminating test

| # | Mechanism | Discriminating test | Pre-fix at 92af889 |
|---|---|---|---|
| 1 | `detect_vocals` takes `hop_length`; both `times_s`-derived expressions gone | `test_vocal_detector_frames_align_with_analyzer_times` | hop 529 vs 512; 6.43s of tail unclassified; segment at 96.77–111.33s vs truth 100–115s |
| 2 | `_detect_builds_windowed` sorts by `start_s` before the adjacent merge | `test_builds_merge_preserves_all_and_is_time_ordered` | 3 builds collapse to 1 |
| 3 | `sections.align_rms_to_work_timeline()` slices caller RMS to the work window; feeds boundaries *and* descriptors | `test_section_energy_correct_with_leading_silence`, `test_fade_out_offset_applied_once` | 1766 RMS frames against a 1542-frame timeline; fade at 30.28s vs truth 35.0s |
| 4 | `beats_per_bar` threaded from the detected time signature | `test_build_windows_respect_time_signature` | parameter absent; `* 4` hardcoded |
| 5 | `spectral_flatness(..., hop_length=hop_length)` | `test_spectral_flatness_aligned_at_non_default_hop` | length mismatch at hops 256/1024 |
| 6 | `compute_hpss` → `HpssResult(harmonic, percussive, separated, error)` + WARNING log | `test_hpss_failure_logs_and_flags`, `test_hpss_failure_flags_and_warns` | no flag, no log |
| 7 | Validator **wired** (below) | `test_validator_no_spurious_key_warning` + 4 others, `test_validator_result_reaches_caller` | see below |
| 8 | First ground-truth assertions | `tests/unit/audio/test_ground_truth.py` | see below |

### P2-F1 disposition: WIRED, not retired

Check 3 reads `features["harmonic"]["key"]`, falling back to the top-level `key` the
short-audio path writes, and reports *missing* key data as missing rather than as
0.00 confidence. The analyzer now writes `rhythm.downbeat_meta.phase_confidence`, so
check 6 can fire. Results reach `features["warnings"]` → `SongBundle.warnings`, logged
at WARNING. Both halves land together, as the review's sequencing note required.

Wired rather than deleted because the checks fire on real data once they can see it: a
real 25s analysis at `92af889` emitted `Low key detection confidence: 0.00` while the
actual confidence was **0.72**, and simultaneously *hid* a true
`Low downbeat phase confidence: 0.11`. The checks were not worthless — they were blind
and inaudible.

### Ground truth: what it does and does not prove

The four assertions pin *existing* detector behavior, so unlike fixes 1–7 they do not
fail at `92af889` for the right reason (they fail only through the changed HPSS API).
Their discriminator is **absence**: verified by grep at `92af889` that no test anywhere
asserted a detected tempo, beat position, or key against a reference value. Three
measured behaviors are **not papered over** and are routed to
`changes/twinklr-reactivation-review/build/specs/phase-2p-creative-quality/P2P-T8-mir-ab-and-adoption.md`: the hop-512
tempogram lag-grid quantization (a true 120 BPM click reports 117.4538, and ±2 BPM is
unreachable at that hop), the systematic **+1-frame beat bias** (at hop 441 every beat
is +0.0200s late, uniformly, so the one-hop assertion passes with ~zero margin — the
comment at the assertion site says so), and the undetected t=0 click. No tolerance was
widened to make anything pass.

### Test changes, each a correction — none loosened

1. **`compute_hpss` return type** — unpacking updated at its call sites:
   `core/audio/timeline/builder.py`, `tests/unit/audio/harmonic/test_hpss.py`,
   `tests/integration/audio/test_pipeline.py`. Mechanical; no assertion weakened.
2. **`tests/unit/audio/conftest.py::hop_length`** is now `params=[512, 256]` rather than
   pinned at 512 — the pin is what hid defect 5. Un-pinning surfaced exactly one
   failure, everything else passed at both hops.
3. **`tests/unit/audio/test_utils.py::test_basic_conversion`** — that one failure. It
   hardcoded frame indices `[0, 43, 86]` computed for hop 512 while consuming the
   `hop_length` fixture, so it asserted "~1 second" against 0.499s at hop 256. Now
   derives its frames from the hop under test. A test-side coupling, **not** a DSP
   defect of the class this task fixes.
4. **Existing `detect_vocals` call sites** gained
   `hop_length=round(sr * frame_step)` — reproducing exactly what the function used to
   compute internally, so those tests keep their prior semantics.
5. **`tests/unit/audio/test_analyzer.py`** now asserts features `schema_version ==
   "2.4"` (below). `tests/unit/audio/models/test_song_bundle.py` was deliberately left
   at "2.3": its dict is local fixture data for a pass-through test, not a claim about
   what the analyzer emits.

### Features schema 2.3 → 2.4, and the cache gate behind it

The features dict gained `warnings`, `harmonic.hpss` and `rhythm.downbeat_meta`, so it
is now `"2.4"`. Nothing in production gates on that string — the real gate is
`CacheKey.step_version`, which `core/caching/backends/fs.py` compares on load. Bumping
the features version alone would have left stale v3 cache entries being served as
valid: a bundle with **no** warnings, indistinguishable from a clean analysis. So
`cache_adapter.AUDIO_FEATURES_CACHE_VERSION = "4"` now backs both adapter defaults, and
`test_entry_from_an_older_cache_version_is_not_served` pins the miss. Cost is
deliberate: every existing cached analysis re-computes once.

### Left for others

- **P2-F14 (WhisperX vocal gating)** is now unblocked — its blocker was defect 1's
  misaligned evidence — but was explicitly out of scope here.
- `vocal_presence_pct` changes for every song as a consequence of fix 1. It was wrong
  by ~3% of the track; the new value is the correction.
- The MFCC mel-scale question (P2-M13-adjacent) was not investigated; no free check
  presented itself.
