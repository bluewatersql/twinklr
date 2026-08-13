---
type: change
status: active
area: audio
updated: 2026-08-13
---

# Phase 2 — Deterministic Audio Analysis

_Stage 3 phase review. Baseline `aa8d325`. Author: general-purpose (sonnet)
"phase2-author". Read-only against application code; this file is the only write
target. Verifier: "phase2-verifier" (code-reviewer, opus), Stage 7. Stage 2's product
thesis review is in flight concurrently — any "should this exist" judgment below is
marked PROVISIONAL and may be superseded by that review's verdict._

**Verification note (2026-08-13, opus code-reviewer, non-author)**: the original
draft was strong on dead-code/schema-drift detection but wrong or overstated on 3 of
5 priority items, and missed 4+ defects as serious as anything it originally found —
including live DSP correctness bugs the original draft's synthetic-test-only
inspection could not have surfaced. Verdict: **17 ACCEPTED, 5 REVISED, 1 REJECTED,
14 MISSED findings added (3 HIGH)**. Every revision and addition below is applied in
place and tagged `[VERIFIED-REVISED]`, `[VERIFIED-REJECTED→INFO]`, or `[ADDED
Stage 7]`; unmarked content was accepted as originally written. Full verifier record:
`reviews/verification.md` §"Phase 2".

## 1. Scope & exclusions

**In scope**: `packages/twinklr/core/audio/` in full — `analyzer.py` (735 lines, read
in full), `cache_adapter.py` (145 lines, read in full), `enhancement_factory.py` (168
lines, read in full), `sections.py` (78 lines, read in full — canonical section-ID
generator, distinct from `structure/sections.py`), `utils.py`; subpackages
`metadata/`, `lyrics/` (incl. `providers/`), `phonemes/`, `rhythm/`, `energy/`,
`spectral/`, `harmonic/`, `structure/`, `timeline/`, `validation/`, `advanced/`,
`genre/`, `context/`, `models/`. Plus `packages/twinklr/core/api/audio/{acoustid,
musicbrainz}.py` for retry/rate-limit behavior as it is exercised from the audio
side (client construction happens in `enhancement_factory.py`). All findings below
were gathered via direct reading (analyzer.py, cache_adapter.py,
enhancement_factory.py, sections.py, and — at Stage 7 revision — vocals.py, hpss.py,
basic.py, builds_drops.py, key.py, features.py, acoustid.py, client.py, config/
models.py, and the relevant conftest/test files) plus four parallel read-only
sub-audits from the original pass covering metadata/lyrics/phonemes, DSP detectors,
validation/genre/context/models, and API clients/test realism — every claim below
carries file:line evidence.

**Excluded** (owned by other phases, referenced not re-derived): the shared
`api/http/` client internals beyond what audio's retry/timeout policy resolves to
(phase 1 owns `core/api/http/` itself — and, per Stage 7, phase 1's own finding
P1-F1 directly changes this phase's §3.6/§4 conclusions, reconciled below); whether
lyrics/metadata text is actually escaped or bounded once it reaches an LLM prompt
template (phase 3 owns `core/agents/prompts/`) — this review establishes what audio/
hands off and confirms audio/ does zero sanitization at its own boundary (§10,
P2-F20); `feature_engineering/` consumption of `SongBundle` (phase 6); CLI/config
wiring of audio settings beyond what `enhancement_factory.py` reads (phase 1/7).

## 2. Purpose, entry points, contracts, state, invariants, dependencies, consumers

**Purpose**: extract deterministic musical structure (tempo, beats, bars, key,
chords, energy, spectral bands, song sections, a rendering timeline) from a raw audio
file, plus best-effort "enhancement" data (embedded/AcoustID/MusicBrainz metadata,
lyrics from four fallback sources, phonemes/visemes for lip-sync) — packaged as a
cached `SongBundle` that is the sole audio-derived input to every downstream
LLM-agent and rendering stage.

**Entry point**: `AudioAnalyzer.analyze(audio_path)` / `.analyze_sync(...)`
(`analyzer.py:116-223`) — the only production entry point into this subsystem;
`_process_audio` (`analyzer.py:474-700`) is the synchronous DSP core, run via
`asyncio.to_thread` (`analyzer.py:184`).

**Contracts**: output is `SongBundle` (`models/song_bundle.py`), `schema_version:
Literal["3.0"]`. Its `features` field is `dict[str, Any]` holding a **wholly
different, unenforced schema_version — `"2.3"` — set inside the dict itself**
(`song_bundle.py:49-51`, docstring: *"features: Complete v2.3 features dict
(backward compatible)"*; `analyzer.py:654,718` set `features["schema_version"] =
"2.3"`). This is the subsystem's central data-ownership defect: the only thing that
enforces the internal shape of `features` is `analyzer.py`'s own construction code —
Pydantic validates nothing below the dict boundary. `metadata`/`lyrics`/`phonemes`
sub-bundles are properly typed Pydantic models with a `StageStatus` (`OK`/`SKIPPED`/
`FAILED`, `models/enums.py:6-11`) contract — but that contract is applied
inconsistently: `MetadataBundle` and `LyricsBundle` carry `stage_status`;
`PhonemeBundle` does not (§10, P2-F16), so phoneme-stage failures have no structured
signal at all.

**State**: cached via `FSCache` at content-addressed keys (`domain="audio",
step_id="audio.features", step_version="3"`, `cache_adapter.py:91-96`); no other
persistent state. `step_version` is a **static literal**, decoupled from both
`features["schema_version"]` and `SongBundle.schema_version` — nothing in the
codebase bumps it when the inner dict shape changes (§10, P2-F10).

**Invariants (as implemented, not always as intended)**: audio < 10s routes to a
degenerate `_minimal_features` path with a different, incompatible dict shape
(`analyzer.py:492-495,703-734` — e.g. only this path has a top-level `"key"` key,
which is otherwise nested at `features["harmonic"]["key"]`); every enhancement stage
is individually feature-flagged and independently exception-wrapped so a
provider/ML failure degrades to `SKIPPED`/`FAILED` rather than aborting analysis
(`analyzer.py:236-242,310-347,349-417,419-472`); validation exists
(`validation/validator.py`) but its output never leaves `analyzer.py` except as a
DEBUG log line (`analyzer.py:696-698`) — it has zero behavioral effect on the
pipeline or on what callers see (§10, P2-F1, compound finding — see §4).

**Dependencies**: librosa/numpy/scipy for all DSP; `httpx`-based `AsyncApiClient`
(phase 1) for AcoustID/MusicBrainz/Genius/LRCLib HTTP; lazily-imported
`whisperx`/`torch`/`g2p_en`/`python-Levenshtein` for ML enhancement stages;
`core.caching.FSCache` for persistence.

**Consumers**: `SongBundle.features` (the untyped dict) is read positionally by
`AudioProfile`/`Lyrics` LLM agents and moving-heads rendering (phase 3/4, not
re-derived here); `metadata`/`lyrics` resolved strings (artist/title/lyric text) are
handed to agent prompt construction (phase 3) and to
`core/formats/xlights/sequence/timeline.py` (phase 5) — the only external, non-test
consumer of `LyricsBundle` found by direct grep.

## 3. Representative execution paths inspected

1. **Full happy-path analysis of a normal-length track with all enhancements
   enabled**: `analyze()` → embedded-metadata fast pass (genre hint) →
   `_process_audio` (HPSS → onset → beats/tempo/time-signature → downbeats → energy
   → builds/drops → two separate STFT computations → spectral/dynamic features →
   vocal detection → key/chords/pitch → section detection → tempo-changes →
   tension → timeline → `validate_features` (discarded) → assemble `features` dict)
   → parallel metadata+lyrics extraction (`asyncio.gather`) → phoneme extraction →
   `SongBundle` construction → cache store. Traced end to end
   (`analyzer.py:116-308,474-700`); confirmed the two STFT computations at
   `analyzer.py:542-544` and `analyzer.py:592-594` are numerically identical under
   default config (`frame_length=2048` matches the hardcoded `n_fft=2048` at line
   592) — genuine redundant compute (§10, P2-F12).
2. **Lyrics resolution chain, no artist/title, offline**: embedded lyrics miss →
   `artist`/`title` both `None` so LRCLib/Genius lookups are skipped entirely
   (`pipeline.py` fallback logic) → WhisperX transcribe attempted if enabled → on
   `ImportError`/`OSError`/any exception, caught by a broad `except Exception` in
   `pipeline.py` → `LyricsBundle(stage_status=FAILED or SKIPPED, warnings=[...])`.
   No uncaught-exception path found for zero-network + zero-API-key operation.
3. **Instrumental track with known artist/title (no lyrics anywhere), WhisperX
   enabled**: LRCLib/Genius correctly return empty. **The pipeline does not check
   vocal presence before invoking WhisperX transcription** — `vocal_segments` is
   threaded through only for a post-hoc quality metric
   (`pipeline.py:334-337,530-533`), never as a gate. `[VERIFIED-REVISED]` narrowed
   at Stage 7: WhisperX defaults **off** (`config/models.py:244-246`,
   `enable_whisperx: bool = Field(default=False)`), so this path requires explicit
   opt-in, not a default-config risk; and `vocal_presence_pct` **is** surfaced to
   the downstream lyrics agent (outside this phase's scope) — nothing currently
   acts on it there either. The remedy is also blocked on P2-M2 (§10): the vocal
   detector itself is time-misaligned, so gating on its output today would gate on
   drifted evidence.
4. **Silent/near-silent audio through key detection.** `[VERIFIED-REJECTED→INFO]`:
   the original draft claimed silent audio could propagate `NaN` key-detection
   confidence. Direct trace of `harmonic/key.py:50-53`'s `corr()` shows this is
   wrong — `a_norm = (a - a.mean()) / (a.std() + 1e-9)`; for degenerate/all-zero
   chroma, `a.mean() == 0` and `a.std() == 0`, so the numerator is exactly `0.0` and
   the division by `1e-9` yields exactly `0.0`, not `NaN` (no `0/0` occurs). Both
   `major_conf` and `minor_conf` are therefore deterministically `0.0`,
   `major_conf >= minor_conf` (`key.py:72`) is `True` (`0.0 >= 0.0`), and the
   function returns `{"key": "C", "mode": "major", "confidence": 0.0}` — a correct,
   deterministic degenerate result, not garbage. Downgraded to INFO: the only real
   gap is that `test_key.py:117-132`'s silent-audio test doesn't explicitly assert
   `confidence == 0.0`, so this deterministic behavior isn't locked in by a test,
   but no live defect exists (§10, P2-F17).
5. **Validator path on a normal production run**: `validate_features(features)`
   executes all 6 checks; 2 of 6 are structurally incapable of ever functioning
   correctly against the current schema, and the entire mechanism's output is
   discarded regardless (§4, §10 P2-F1 — merged compound finding, was F1+F2+F3 in
   the original draft).
6. **AcoustID candidate with multiple MBIDs → MusicBrainz lookups.**
   `[VERIFIED-REVISED, reconciled with phase 1's P1-F1]`: the original draft traced
   `metadata/pipeline.py` firing concurrent MusicBrainz lookups via `asyncio.gather`
   when an AcoustID result carries multiple MBIDs, and flagged this as a live
   MusicBrainz-ToS violation. Phase 1's independently-confirmed **P1-F1** changes
   the premise: `AcoustIDClient.lookup` (`api/audio/acoustid.py:57-97`) passes
   whatever `AsyncApiClient.get(...)` returns straight to `self._parse_response(...)`
   (`acoustid.py:87`), and `_parse_response`'s first line is `if "status" not in
   data:` (`acoustid.py:112`) — `data` here is an `httpx.Response` object (per
   `api/http/client.py:622-635`), which does not support the `in` operator the same
   way a `dict` does, so this raises a `TypeError` on **every** AcoustID call, not
   just malformed ones. `AcoustIDClient.lookup`'s own `except Exception as e:` at
   the bottom of the method catches this and re-raises as `AcoustIDError`
   (confirmed shape at `acoustid.py:92-97`), which `metadata/pipeline.py`'s
   `_query_acoustid` catches and degrades to an empty candidate list with a
   warning. **Net effect: AcoustID never returns real candidates today, so the
   multi-MBID concurrent-`asyncio.gather` code path this finding depends on is
   never reached in production** — the MusicBrainz concurrency violation is real
   code but **latent, not live**. It becomes live the moment P1-F1 is fixed without
   also landing pacing for MusicBrainz in the same change — a Stage 8 sequencing
   constraint, not a currently-active defect (§10, P2-F13 revised; §11).
7. **`[ADDED Stage 7]` Full-metadata-available lyrics resolution, WhisperX
   enabled**: `_build_song_bundle` (`analyzer.py:274-289`) runs metadata and lyrics
   extraction **in parallel** via `asyncio.gather(self._extract_metadata_if_enabled(...),
   self._extract_lyrics_if_enabled(audio_path, duration_ms, None, vocal_segments))`
   (`analyzer.py:276-279`) — the lyrics call is given `metadata_bundle=None`
   unconditionally on this first pass, regardless of whether metadata extraction
   will succeed moments later. Inside `_extract_lyrics_if_enabled`, a `None`
   metadata bundle means `artist`/`title` stay `None`
   (`analyzer.py:380-395`), which structurally skips LRCLib and Genius (both gated
   on artist/title being present, per §3.2). If WhisperX is enabled, the pipeline
   falls through directly to ASR transcription and returns a **non-SKIPPED**
   `LyricsBundle`. The retry-with-real-metadata logic that follows
   (`analyzer.py:282-288`, `if lyrics_bundle.stage_status == StageStatus.SKIPPED
   and metadata_bundle.stage_status != StageStatus.SKIPPED`) only fires when the
   first pass came back `SKIPPED` — which it won't, because WhisperX succeeded. So
   for any song where metadata *would* have resolved the real artist/title, the
   authoritative LRCLib/Genius sources are **never actually consulted**, and
   ASR-transcribed (lower-fidelity) lyrics silently outrank synced lyrics — an
   inversion of the pipeline's own declared fallback order (embedded → LRCLib →
   Genius → WhisperX, §2 of the original draft, still correct as *written* but not
   as *executed* under this race). With WhisperX disabled, the cost is different
   but still real: the first pass returns `SKIPPED` (nothing found without
   artist/title), the retry condition fires, and lyrics extraction runs a
   **second, fully redundant time** with real metadata (§10, P2-M1, HIGH).
8. **`[ADDED Stage 7]` Vocal-detection frame-time alignment.**
   `spectral/vocals.py:43`: `hop_length = int(sr * (times_s[1] - times_s[0])) if
   len(times_s) > 1 else 512` reconstructs a hop length by inverting the time
   delta between the first two entries of the `times_s` array passed in from
   `analyzer.py:574` (`np.asarray(spectral_features["times_s"])`). That array is
   built by `spectral/basic.py:43` as `as_float_list(times_s, 3)` — **rounded to 3
   decimal places** before being handed off. At the app's default `sr=44100`,
   `hop_length=512`, the true frame interval is `512/44100 ≈ 0.0116099...s`, which
   rounds to `0.012` at 3 decimals; `int(44100 * 0.012) = int(529.2) = 529` — a
   **512→529 hop-length drift** (confirmed by direct calculation), reconstructed
   and then used to recompute `librosa.feature.rms` for the harmonic/percussive
   components inside `detect_vocals` (`vocals.py:45-46`) at the wrong frame rate.
   Over a ~4-minute track this misalignment accumulates to roughly 6-8 seconds of
   drift between the vocal-detector's frame index and the rest of the pipeline's
   time axis — silently, with no warning, on every production run, not just an
   edge case (§10, P2-M2, HIGH — also blocks the P2-F14 vocal-gating remedy, since
   gating WhisperX on drifted vocal evidence wouldn't be trustworthy either).
9. **`[ADDED Stage 7]` Section/build energy trace on a track with leading silence
   or a strong build.** Two independent, compounding bugs live on this path: (a)
   `energy/builds_drops.py:284`, `builds.sort(key=lambda b: b["energy_gain"],
   reverse=True)`, re-orders the builds list from chronological to
   energy-magnitude order **before** the adjacent-build merge loop at
   `builds_drops.py:287-304`, which assumes `merged_builds[-1]` is the
   *immediately time-preceding* build (`gap = build["start_s"] -
   last["end_s"]`) — once the list is sorted by energy instead of time, that
   assumption is false, so the merge can silently absorb/extend the wrong build or
   skip merging genuinely adjacent ones, and the final `builds` list returned to
   the analyzer is not guaranteed to be time-ordered (§10, P2-M4, MEDIUM-HIGH). (b)
   `structure/sections.py:290`'s `_pass_precomputed = start_offset_s == 0.0` guard
   correctly gates `chroma_cqt`/`onset_env`/`stft_mag`/`y_harm` reuse to only when
   no leading-silence trim occurred — but `rms_for_energy` (the pre-computed,
   **original-untrimmed-timeline** RMS energy curve from `analyzer.py:525-528`) is
   passed unconditionally at `sections.py:323,340` regardless of `start_offset_s`,
   into functions operating on the **trimmed (work) timeline**
   (`boundaries_work`/`beat_times`). For any track with leading silence
   (`start_offset_s > 0`), every section's computed energy is read from the wrong
   original-timeline offset, shifting all section energy values and downstream
   energy-based labeling (§10, P2-M5, MEDIUM).
10. **`[ADDED Stage 7]` HPSS failure fallback on genuinely difficult input.**
    `harmonic/hpss.py:18-24`'s `compute_hpss` wraps `librosa.effects.hpss(y)` in a
    bare `except Exception`, and on any failure returns the **same array twice**
    (`y_copy` for both harmonic and percussive components) with no log line and no
    status flag anywhere in the returned tuple. Every downstream consumer of
    `y_harm`/`y_perc` — vocal detection's `harmonic_ratio = rms_h / (rms_h + rms_p
    + 1e-9)` (`spectral/vocals.py:59`) chief among them — would then compute
    `rms_h == rms_p` for every frame, collapsing `harmonic_ratio` to a constant
    `~0.5` across the entire track, silently, with the only observable trace being
    a flat `hpss_perc_ratio` curve in the output (§10, P2-M8, MEDIUM).

## 4. Implementation assessment

**`[VERIFIED-REVISED, merged]` The validator/discard chain is one compound defect,
not three independent ones — the validation layer is decorative.** The original
draft's F1 (check 3 always warns falsely), F2 (check 6 is permanently dead), and F3
(results discarded at DEBUG) are three facets of a single mechanism that has zero
real-world effect and should not be triple-counted (§10, merged into P2-F1).
`validate_features` (`validation/validator.py:23-50`) checks: unusual tempo, too-few
beats, low key confidence, irregular beat spacing, no sections, low downbeat
confidence. Checks 1, 2, 4, 5 correctly match the current schema. Check 3 reads
`result["key"]["confidence"]` (`validator.py:31`) — but `analyzer.py` never writes a
top-level `"key"` key on the normal (≥10s) path; key data lives at
`features["harmonic"]["key"]` (`analyzer.py:684`). `result.get("key", {})` therefore
always returns `{}`, `key_conf` defaults to `0`, and `0 < 0.3` is always true — the
"Low key detection confidence: 0.00" warning fires on **every single production
run** regardless of actual key-detection quality. Check 6 reads
`result["rhythm"]["downbeat_meta"]["phase_confidence"]` (`validator.py:48`) —
`analyzer.py` discards `phase_confidence` entirely when building `features["rhythm"]`
(`analyzer.py:666-669` keeps only `beat_confidence` and `downbeats`); the check's
chained `.get(...)` calls silently fall through to a hardcoded default `1.0`, so
`1.0 < 0.4` never fires — permanently dead. And regardless of whether checks 3/6 are
fixed, the entire return value is only ever logged at DEBUG
(`analyzer.py:696-698`) and never reaches `SongBundle.warnings` or any caller —
confirmed by repo-wide grep, no caller besides `analyzer.py` and its own tests
inspects the return value. `tests/unit/audio/validation/test_validator.py` hand-crafts
input dicts using the *stale* shape the validator expects, so the test suite could
never have caught this drift. Fixing checks 3/6 without also fixing the discard
would only add more warnings nobody sees; fixing the discard first would surface
today's broken checks' false positives. **Sequence matters: fix the schema-alignment
of checks 3/6 and the discard together, not independently** (§10, P2-F1, merged
MED-HIGH).

**The untyped `features: dict[str, Any]` is the subsystem's central architectural
liability.** It is constructed by ~15 DSP calls assembling nested dict literals with
no schema enforcement (`analyzer.py:653-693`), consumed by validator, section-ID
generator, and (outside this phase's scope) LLM-agent prompt builders and rendering
— all by string-keyed dict access with no compile-time or runtime shape guarantee.
`tests/unit/audio/models/test_song_bundle.py:22-27` demonstrates this concretely: a
test constructs `features` with a typo'd key (`"bars"` instead of `bars_s`/`bars`)
and `SongBundle` accepts it without complaint. `[VERIFIED-REVISED]` evidence
corrected/strengthened at Stage 7: the drift is 2 broken *reads* against the schema
(checks 3 and 6, above), not a broader count, but the live-code evidence is
stronger than originally cited — `analyzer.py:667` emits `beat_confidence` as a
plain `float` (`time_sig_result.get("confidence", 0.0)`) on the success path but
`analyzer.py:728` (`_minimal_features`) emits `"beat_confidence": []`, an **empty
list**, for the identical dict key under the identical `schema_version: "2.3"` — a
type-inconsistent contract within the same nominal schema version, not merely a
missing-key drift. This is the same failure class that already broke the validator
and `genre/classifier.py`/`context/{hints,unified_map}.py` (next paragraph) — the
untyped boundary doesn't just risk *a* future schema-drift bug, it has already
produced multiple independent instances of the same bug class, undetected by any
test, in the current baseline.

**Orphaned modules confirm a second, worse instance of the same drift class.**
`genre/classifier.py`, `context/hints.py`, `context/unified_map.py` are unreferenced
by any live pipeline path (confirmed by repo-wide grep for their public entry points
— only self-referencing tests remain). They read a features shape that predates the
current one: `context/hints.py:48,193` (`unified_map.py`) expect
`song_features.get("extensions", {}).get("timeline"/"composites", {})` — there is no
`"extensions"` key anywhere in the current schema; `timeline`/`composites` are
top-level (`analyzer.py:691-692`). `hints.py:70,75,84` expect top-level `"key"`,
`"pitch"`, `"chords"` — all three now live under `features["harmonic"]`
(`analyzer.py:682-687`). Worst instance: `hints.py:80-81` calls
`song_features.get("vocals", {}).get("statistics", {})` — in the current schema
`features["vocals"]` is a **list** (`analyzer.py:680`), not a dict, so this call
would raise `AttributeError` if the code path were ever exercised against live data,
not merely return an empty default. **`[VERIFIED, hygiene correction]** the
`extensions`-wrapper citation at line 193 belongs to `context/unified_map.py`, not
`context/hints.py` (which is 186 lines total and does not reach line 193) — fixed
above. These modules cannot be safely re-enabled without a rewrite against the
current schema; they are not "temporarily disabled," they are broken against the
schema that has existed since at least the current baseline. **Remediation note
added at Stage 7**: `tests/unit/audio/conftest.py:219-`'s shared `sample_song_features`
fixture (consumed by `test_hints.py`, `context/hints.py:281`'s `"extensions"` key
included) itself encodes this same phantom pre-refactor schema — any rewrite of
`context/hints.py`/`unified_map.py` against the current schema must also correct
this fixture, or its tests will keep "passing" against a shape production code
never produces (§10, P2-F4).

**Dead-code duplication is extensive and, in two cases, the dead copy has silently
diverged from the live version — a maintenance trap for anyone who greps for the
function name and finds the wrong one.** `rhythm/beats.py:194-282` (`[VERIFIED,
hygiene correction]`: function spans to the file's last line, 282, not 283 as
originally cited) has its own `detect_tempo_changes`, never imported by
`analyzer.py` (which uses `rhythm/tempo.py:11-97`'s version, `analyzer.py:51,612`).
It is not a verbatim copy — it uses a different beat-tracking call signature, a
different (absolute vs. relative) change-detection threshold, and a different
silent-audio fallback tempo (`120.0` vs `0.0`) — and it is still directly
unit-tested (`test_beats.py:402-560`), consuming real test-maintenance effort for
code nothing calls. **`[VERIFIED-REVISED]` severity raised at Stage 7**: this dead
copy is not merely an internal leftover — `rhythm/__init__.py` re-exports
`detect_tempo_changes` from `beats.py`, not `tempo.py`, making the **behaviorally
diverged, dead-in-production version the package's own exported public API** for
anyone importing `from twinklr.core.audio.rhythm import detect_tempo_changes`
instead of the module-qualified path `analyzer.py` actually uses — raised from
LOW-MEDIUM to MEDIUM (§10, P2-F6). Similarly, `structure/sections.py::SongSectionDetector`
has three private methods (`_build_beat_grid`, `_compute_section_descriptors`,
`_build_diagnostics`, lines 449-505/599-741/829-864) that duplicate module-level
functions in `orchestration.py` — `SongSectionDetector.detect()` calls only the
`orchestration.py` versions (`sections.py:284,334,375`). The dead
`_compute_section_descriptors` copy is not just redundant but **less safe**: it
lacks a boundary-index guard the live `orchestration.compute_section_descriptors`
has (`orchestration.py:169-179` vs. the unguarded direct index at
`sections.py:665-669`).

**`[VERIFIED-REVISED]` `structure/models.py::Section`/`SectionDiagnostics` — "wire it
in" is not a small fix.** The original draft's disposition (FIX: wire the model in
at the production construction site) understated the gap: at Stage 7, the
production plain-dict shape built by `orchestration.py` and the `Section` Pydantic
model have **diverged** — production dicts carry extra fields the model doesn't
declare, and some production `label` values are not valid under the model's
constraints, so a naive "construct `Section(**section_dict)` instead of a plain
dict" change would raise validation errors on real output today. Wiring the model
in requires reconciling the model's schema with actual production output first, not
a mechanical one-line swap (§10, P2-F8 disposition revised to MODERNIZE).

**`[ADDED Stage 7]` A hardcoded placeholder silently replaces a real computed
metric.** `structure/sections.py:791-795` — the *live*, called (`sections.py:359`)
`_build_result` method contains a comment block showing the real derivation
(`# threshold = descriptors.derive_repeat_threshold(...)`,
`# rep_strength = np.array(...)`, `# energy_vals = np.array(...)`) immediately
followed by `discrimination = 0.5  # Placeholder` (`sections.py:795`), which then
flows into the result's `meta.discrimination` field (`sections.py:825`) alongside
another hardcoded placeholder, `"repeat_threshold_derived": 0.9  # Placeholder`
(`sections.py:824`). Both values are shipped in every production `SongBundle` as if
computed, with no flag distinguishing them from genuine metrics — any downstream
consumer or diagnostic reading `structure.meta.discrimination` today is reading a
constant, not a signal (§10, P2-M12, MEDIUM-HIGH — a fabricated-metric class of bug
distinct from dead code, since this one actively misleads a live field).

**`[ADDED Stage 7]` Three further, smaller DSP correctness gaps.** (1)
`spectral/basic.py:36-38` computes `spectral_flatness` via
`librosa.feature.spectral_flatness(y=np.asarray(y, dtype=np.float32))` — unlike the
three sibling calls in the same function (`centroid`, `bandwidth`, `rolloff`, lines
27-35), this call **omits `hop_length=hop_length`**, so it runs at librosa's
internal default hop (512, matching the app's own default `hop_length=512` by
coincidence) rather than whatever hop length the job actually configures. Under
default config this is invisible; under any non-default `hop_length` job config,
`spectral_flatness` silently misaligns frame-for-frame against `times_s` (built
correctly at `basic.py:40` from the real `hop_length`) and every other spectral
array in the same dict (§10, P2-M6, MEDIUM — masked by `tests/unit/audio/conftest.py`
pinning `hop_length=512` throughout). (2) `energy/builds_drops.py:88`,
`bar_duration_s = 60.0 / tempo_bpm * 4  # 4 beats per bar`, hardcodes 4 beats per
bar for every build/drop window-size and drop-search-window calculation, ignoring
the time signature `detect_time_signature` already computed
(`analyzer.py:503-506`) and threads through the rest of the pipeline — a track in
3/4 gets build/drop windows sized ~33% too long, with no override path (§10,
P2-M7, MEDIUM). (3) `rhythm/beats.py`/`analyzer.py:667` label a field
`"beat_confidence"` that actually holds the **time-signature detection**
confidence (`time_sig_result.get("confidence", 0.0)`), not a per-beat or
beat-tracking confidence — the name promises something the value doesn't measure,
compounding the type-inconsistency already noted above (float on the normal path,
empty list in `_minimal_features`) (§10, P2-M9, LOW-MEDIUM).

**Two enhancement-layer correctness/compliance items, revised at Stage 7.** (1)
WhisperX transcription is never gated on vocal presence — confirmed still true, but
narrowed: WhisperX defaults off (`config/models.py:244-246`), and
`vocal_presence_pct` is already surfaced to the downstream lyrics agent (outside
this phase), so the gap is "nothing acts on the signal that exists" rather than "no
signal exists at all" — and any fix is blocked on P2-M2 (§3.8) since the vocal
detector itself is currently misaligned (§10, P2-F14 narrowed). (2) MusicBrainz's
documented 1 req/sec, no-concurrent-requests policy is acknowledged in code
comments (`musicbrainz.py:6-9,33-35`) but not enforced by the framework HTTP client
or by `metadata/pipeline.py:161-164`'s `asyncio.gather(*mb_tasks)` — **but per §3.6
above, this path is currently unreachable in production** because AcoustID always
raises before ever producing MBIDs to fan out on (P1-F1). Related config fields
(`musicbrainz_rate_limit_rps`, `musicbrainz_timeout_s`, `http_max_retries`,
`http_timeout_s`, `http_circuit_breaker_threshold` — `config/models.py:315-323`) are
declared and unread anywhere in `core/audio/` or `core/api/`. Downgraded from
MEDIUM-HIGH (live risk) to MEDIUM (latent risk with a hard Stage 8 sequencing
constraint: any fix to P1-F1 must land MusicBrainz pacing in the *same* change, or
it reintroduces a live ToS violation) (§10, P2-F13 revised).

**`[ADDED Stage 7]` Resource-leak and dead-configuration gaps in the enhancement
factory.** `enhancement_factory.py:61-62,115-116` constructs two separate
`AsyncApiClient(config=http_config)` instances — one for metadata (AcoustID/
MusicBrainz), one for lyrics (LRCLib/Genius) — each wrapping an `httpx.AsyncClient`
connection pool (`api/http/client.py:454`). `AsyncApiClient` exposes `aclose()` and
context-manager support (`client.py:468-476`) specifically for this, but a
repo-wide grep of `core/audio/`, `core/pipeline/`, and `cli/` finds **zero calls to
`aclose()`** anywhere — every `AudioAnalyzer` construction leaks its two HTTP
connection pools for the life of the process. Both clients are also constructed
with placeholder `base_url`s (`"http://localhost"` at `enhancement_factory.py:61`,
`"https://api.placeholder.local"` at `:115` — the comment at `:114` confirms this is
intentional since providers use absolute URLs, but it means `base_url` validation
offers no real safety net either) (§10, P2-M10, LOW-MEDIUM). Separately: five
`enable_*` network-feature flags (`enable_acoustid`, `enable_musicbrainz`,
`enable_lyrics_lookup`, `enable_whisperx`, `enable_diarization`) all
**default to `False`** (`config/models.py:234-249`), and `AppConfig` is a plain
Pydantic model (`ConfigDict(extra="ignore")`, `config/models.py:226`), not a
`BaseSettings` subclass with environment-variable binding — so a user who sets
`ACOUSTID_API_KEY`/`GENIUS_ACCESS_TOKEN` in their shell (as multiple field
docstrings instruct, e.g. `config/models.py:309,313`) gets no behavior change at
all unless they *also* separately flip the corresponding `enable_*` flag to `true`
in `config.json` — the same "documented, silently a no-op" class phase 7
independently found across the user guide (P7-M2) (§10, P2-M11, MEDIUM).

**`[ADDED Stage 7, SUSPECTED — not conclusively proven]` MFCC may be computed from
a linear-frequency spectrogram rather than a mel-scaled one.**
`structure/features.py:74-82`: `P_db = librosa.power_to_db(S**2)` where `S` is a
linear-frequency STFT magnitude (`stft_mag`, `2049` bins at default `n_fft=2048`,
not a mel filterbank output), and `mfcc = librosa.feature.mfcc(S=P_db, sr=sr,
n_mfcc=13)`. `librosa.feature.mfcc`'s `S=` parameter is documented to accept a
log-power **mel** spectrogram, applying only a DCT on top of it — it does not
re-apply a mel filterbank when `S` is supplied directly. Feeding it a
linear-frequency log-power spectrogram instead would compute a DCT over
linear-frequency bins, which is not the perceptually-weighted MFCC the code's own
docstring claims ("MFCC: Timbre (13 coefficients)", `features.py:81`). This review
did not execute the code or compare output against a reference mel-based MFCC
implementation to confirm the practical impact (hence SUSPECTED, not CONFIRMED) —
flagged for a cheap Stage 4/7 runtime check (compare against
`librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)` on the same input) rather than
asserted as a defect here (§10, P2-M13-adjacent, see note in §10).

## 5. Tests & validation assessment

**`[VERIFIED-REVISED]` Test realism, corrected to the defensible form**: the
original draft's blanket "no ground-truth assertions exist" claim overstated the
gap. At Stage 7, real ground-truth assertions were found to exist — roughly 15
across the DSP test suite, including a reference-loop check inside the Foote-novelty
tests that verifies detected boundaries against a deliberately constructed
self-similar signal with known segment boundaries. **The defensible, narrower
claim stands**: **no test anywhere in the repository asserts a detected tempo
value, beat position, or key label against a known-correct reference value** — the
existing ground-truth-adjacent tests check structural/self-consistency properties
(boundaries land near constructed segment edges, output shape matches input shape),
not "does this synthetic 120 BPM click track get detected as ~120 BPM" or "does
this stub sine tone map to the expected pitch class." `click_track_120bpm`'s known
120 BPM (`tests/unit/audio/conftest.py:16-111`) is used by only two files
(`test_hpss.py`, `test_bands.py`) for weak, non-tempo assertions ("percussive
energy > 0"); no rhythm test (`test_beats.py`/`test_tempo.py`) uses it at all, and
`tests/integration/audio/test_pipeline.py`'s explicit `beat_freq = 2.0` (120 BPM)
synthetic WAV is never checked against detected tempo — only `tempo_bpm > 0`. This
is the real, still-serious gap: the "deterministic code handles precision" product
principle has no test enforcing that detected values are *accurate*, only that they
exist and have a plausible shape (§10, P2-F24 revised).

**`tests/integration/audio/test_lyrics_analyzer_integration.py` is mislabeled** —
despite its path, it performs no real audio decoding (creates a 0-byte file via
`.touch()`) and mocks `AudioAnalyzer._process_audio` directly in every test — it is
a unit test of `StageStatus` control-flow branching, not an integration test. This
overlaps with phase 7's test-architecture findings on `integration`-marker
misapplication — noted for cross-phase coordination, not re-derived as a separate
finding here.

**AcoustID/MusicBrainz clients are tested exclusively against mocks** (`AsyncMock`
providers throughout `tests/unit/api/audio/`) — no real network call is ever
exercised. Given §3.6/§4's P1-F1 reconciliation, this also means the mocked tests
never would have caught the real `TypeError` bug, since the mocks bypass
`_parse_response`'s actual input shape entirely — a concrete example of mock-only
testing masking a live defect.

**One genuine positive**: `merge.py`'s scoring/merge logic has an explicit
determinism test (`test_merge_policy.py`'s
`test_score_candidate_deterministic`/`test_merge_metadata_deterministic`) — a good
pattern other modules in this phase could usefully copy.

## 6. Critical assessment — should this subsystem exist in its current form (PROVISIONAL)

**`[VERIFIED-REVISED]` KEEP verdict on the deterministic DSP core survives Stage 7,
but not unconditionally.** The original draft's "sound engineering, keep as-is"
framing for rhythm/energy/spectral/harmonic/structure/timeline understated real,
live correctness defects the verifier's deeper trace surfaced: **P2-M2** (vocal
detector's hop-length reconstruction drifts ~6-8s over a 4-minute track, live on
every run), **P2-M4** (build list silently loses chronological order and can
mis-merge, live whenever a build is detected), and **P2-M5** (section energy is
read from the wrong timeline offset on any track with leading silence, live
whenever `_trim_audio` trims anything). None of these invalidate the *architecture*
— beat-grid-as-timing-authority, chroma/onset/HPSS precompute reuse, and Foote-based
section detection remain genuinely sound design choices — but the verdict must be
stated precisely: **KEEP the architecture; these three specific, live correctness
bugs must be fixed before the DSP core's output can be trusted at the precision the
product's "deterministic code handles precision" principle implies.** The
precompute-reuse discipline itself also has three now-documented exceptions
(§3.1's STFT duplication, P2-M6's flatness hop mismatch, and the MFCC mel-scale
question, §4) that should be fixed alongside, not treated as separately
acceptable — they are all instances of the same "computed once correctly in one
place, recomputed incorrectly or inconsistently in another" pattern.

The **enhancement layer (metadata/lyrics/phonemes) is architecturally sound in its
degradation design** (layered exception handling, `StageStatus` semantics where
applied), but the priority-ranked live issue in this layer is now **P2-M1** (the
lyrics-source fallback order inversion under parallelization, §3.7) — more
consequential than the previously-flagged MusicBrainz concurrency item, which
Stage 7 downgraded to latent (§3.6, §4).

**The untyped `features` dict as the system's core data contract is the question
this phase cannot resolve alone (PROVISIONAL, feeds Stage 2).** The dict shape has
already drifted, silently, breaking multiple consumers (validator, two orphaned
modules) without a single test catching it, and the type-inconsistent
`beat_confidence` field (float vs. empty list under the same schema version, §4)
shows the drift risk is present even within a single "unchanged" schema version, not
only across version bumps. If the schema is no longer under active change (plausible
given the ~4-month commit dormancy discovery.md documents), the case for leaving it
untyped weakens considerably; if it is expected to keep evolving, at minimum the
validator and any code reading `features` should be regenerated/type-checked against
a single schema definition rather than hand-matched dict-access strings that can
silently drift again. Recommend: model the **stable subset** actually consumed by
validator, section-ID generation, and downstream agents/renderers (tempo, beats,
bars, key, sections, timeline, composites) even if less-consumed detail fields
remain a loosely-typed dict.

**Whether audio/ should be split into deterministic-DSP vs. enhancement (network/ML)
packages (PROVISIONAL, feeds Stage 2/8)**: the code already has this seam implicitly
— `_process_audio` (pure DSP, thread-pooled, no I/O) is cleanly separable from the
network/ML enhancement methods. A physical package split would mainly clarify
intent and let the "deterministic" framing actually be true at the package
boundary — low-risk, mechanical, cheap, and directionally correct, not urgent.

## 7. Comparison with credible simpler/modern alternatives

**Section detection**: the "Foote novelty + baseline grid" combination is
real — `segmentation.py:30-75`'s `compute_foote_novelty` is a correct, vectorized
implementation of Foote's (2000) checkerboard-kernel self-similarity novelty
function (confirmed by algorithm structure — the code does not itself cite "Foote
2000," this attribution is INFERRED from matching a well-known technique). The
"baseline grid" half (evenly-spaced candidate boundaries snapped to the beat grid,
unioned with novelty peaks to guarantee minimum section coverage) is an ad hoc
engineering heuristic, not a named literature method. This is a reasonable,
defensible design — self-similarity-based novelty detection remains a standard MIR
technique, comparable in spirit to what libraries like `msaf` (Music Structure
Analysis Framework) implement (INFERRED — general MIR domain knowledge, not
verified against msaf's current source). No in-repo evidence shows this approach
was benchmarked against alternatives such as deep-learning boundary detectors
(which would trade determinism for potentially higher accuracy). Given the
product's stated "deterministic code handles precision" principle, a hand-tunable,
non-ML self-similarity approach is arguably the *more* aligned choice even if a
learned model might score higher on some accuracy benchmark — implementation and
product intent may already be well-matched here; flagging the comparison as open
rather than asserting a verdict, and noting that the *implementation* of that
approach has live correctness bugs (§3.9, §4) separate from the *choice* of
approach being sound.

**AcoustID/MusicBrainz metadata enrichment vs. simpler alternatives**: with the
concurrency violation now understood as latent (blocked entirely by P1-F1), the
correct sequencing is to fix P1-F1's `TypeError` and land basic MusicBrainz pacing
(sequential-with-delay is likely sufficient given probable usage volume, pending
Stage 4 runtime data) in the same change — building a full token-bucket limiter
ahead of confirming AcoustID even works would be solving a problem that cannot
manifest yet.

## 8. Relevant doc/context claims

| Claim (source) | Observed status |
|---|---|
| discovery.md §5: "2 of 6 validator checks broken by schema drift, results discarded at DEBUG" | **Confirmed and detailed** — exact checks identified (§4), exact root cause traced key-by-key; treated as one compound finding at Stage 7, not three (P2-F1) |
| discovery.md §5: "orphaned diarization/GenreClassifier/context-builders (stale schema)" | **Confirmed**, with concrete schema-mismatch evidence including one `AttributeError`-on-execution risk (`context/hints.py:80-81`, §4); the shared test fixture perpetuating the stale schema also identified (§4) |
| discovery.md §5: "dead duplicate tempo-changes fn + 3 detector methods" | **Confirmed**, and found to be behaviorally-diverged (not verbatim) in the tempo case, and less-safe (not just redundant) in one section-detector case; the tempo case's severity raised at Stage 7 since the dead version is the package's exported public API |
| discovery.md §5: "Pydantic Section model dead (production sections are plain dicts)" | **Confirmed**; also extends to `SectionDiagnostics`; Stage 7 found the model and production dicts have since diverged in shape, raising the remediation cost from FIX to MODERNIZE |
| discovery.md §3: "features dict is untyped legacy v2.3 shape inside SongBundle v3.0" | **Confirmed**; elevated from a labeling oddity to a demonstrated defect class (§4, §6) — the untyped boundary has already caused multiple independent silent-drift incidents in this baseline, including a within-version type inconsistency |
| discovery.md §3: "nondeterministic stages (network/ML) inside the 'deterministic' layer" | **Confirmed** at the package-structure level (§6) — no enforced boundary between DSP and network/ML code inside `audio/` |
| discovery.md §5: "unreachable ImportError guard in enhancement_factory" | **Corrected/refined** — the guard is reachable (fires if `python-Levenshtein` is missing) but does not protect against the torch/whisperx import failures its placement suggests it's meant to catch; that risk is real but is already caught by a broader `except Exception` one layer up in `lyrics/pipeline.py`. Net exposure is low; the finding is a clarity/maintainability smell, not an active gap (§10, P2-F19, LOW) |
| manifest.md: "LyricsBundle version inconsistency" | **Confirmed** — docstring says `3.0.0`, all 4 construction sites hardcode `"1.0.0"` |
| Phase 1's P1-F1 (`AcoustIDClient._parse_response` `TypeError` on every call) | **Independently confirmed** from the audio side at Stage 7 (§3.6) — this phase's original MusicBrainz-concurrency framing (P2-F13) is reconciled and downgraded to latent as a direct consequence |

## 9. Architecture worth preserving

- **Single shared timing authority**: `orchestration.build_beat_grid` prefers
  externally-supplied `beats_s`/`bars_s` and only estimates its own grid as a
  fallback, with a final synthetic-grid safety net — avoids inconsistent timing
  grids across detectors, a real risk in a system with this many independent
  feature extractors.
- **Precomputation reuse discipline, with three now-documented exceptions**: chroma,
  onset envelope, and HPSS components are each computed exactly once in
  `analyzer.py` and threaded through 6+ downstream detectors (§3.1). The pattern
  itself is good practice worth keeping; verified exceptions to keep in view during
  remediation are the duplicate STFT computation (§3.1, P2-F12), the
  `spectral_flatness` hop-length mismatch (§4, P2-M6), and the MFCC mel-scale
  question (§4, SUSPECTED) — none of these undermine the pattern's value, but all
  three should be fixed as part of the same remediation pass since they're the
  same failure mode (inconsistent reuse of precomputed spectral data).
- **Layered, consistent degradation for network/ML enhancement stages**: every
  provider client independently catches its own exceptions and returns an empty/
  `None` result, and every pipeline caller catches again — a genuine
  defense-in-depth pattern that makes "the DSP core must never crash because a
  lyrics API is down" actually true in practice, not just in intent. (Note per
  §3.6/§4: this same defense-in-depth pattern is *why* P1-F1's `TypeError` has gone
  unnoticed for this long — the layered catching that makes the system robust also
  makes a live bug invisible without explicit testing of the actual data shapes
  crossing each boundary.)
- **`StageStatus` (OK/SKIPPED/FAILED)** where it is applied (metadata, lyrics) gives
  downstream code a clean, correct way to distinguish "nothing to find" from "tried
  and failed" — the extension needed is completeness (phonemes), not a redesign.
- **Robust, outlier-resistant normalization** (`descriptors.robust_sigmoid_norm`
  uses MAD-based scoring with an explicit flat-0.5 fallback for degenerate/no-
  variance input) and **bounds double-enforcement** in section counting are both
  genuinely defense-in-depth designs, not accidental redundancy.
- **`merge_metadata`'s deterministic, documented scoring formula** with an explicit
  determinism test is a pattern the rest of the enhancement layer should emulate.
- **Confirmed clean at Stage 7** (exhaustively checked, no findings): no in-place
  mutation of shared numpy arrays across the analysis pipeline; `SongBundle`'s
  contracts as described in §2; the cache-cost characterization in §4 (full-file
  SHA256 on every call); the Foote-novelty implementation's own correctness.

## 10. Candidate findings

| ID | Title | Severity | Confidence | Evidence | Assessment Relationship | Disposition |
|---|---|---|---|---|---|---|
| P2-F1 | `[VERIFIED-REVISED, merged from F1+F2+F3]` `validate_features` is decorative: 2 of 6 checks are structurally incapable of matching the current schema (spurious "0.00" key-confidence warning on every run; downbeat check permanently dead), and the entire result is discarded at DEBUG regardless — count this as one compound finding, not three | MED-HIGH | CONFIRMED | `validation/validator.py:31-33,48-50` vs `analyzer.py:684,666-669`; `analyzer.py:696-698` (discard); repo-wide grep confirms no other caller inspects the return value | ALIGNED_BUT_FLAWED | FIX (fix schema alignment and the discard together — see §4 sequencing note) |
| P2-F4 | `genre/classifier.py`, `context/hints.py`, `context/unified_map.py` are orphaned and read a pre-refactor features schema; one path (`vocals.statistics`) would raise `AttributeError` if executed against current data; the shared `sample_song_features` test fixture (`conftest.py:219-`) perpetuates the same phantom schema | MEDIUM | CONFIRMED | `context/hints.py:48,70,75,80-81,84,93` and `context/unified_map.py:193-194` (hygiene-corrected citation) vs `analyzer.py:670-693` (schema keys moved/renamed); repo-wide grep confirms zero live importers | BOTH_REQUIRE_RETHINKING | REMOVE (or full rewrite against current schema **and** fixture, if the lighting-hints/unified-map capability is still wanted — Stage 2 product question) |
| P2-F5 | `lyrics/diarization.py` + `diarization_models.py` fully orphaned; `enable_diarization` config flag also dead | LOW-MEDIUM | CONFIRMED | repo-wide grep: only self-import within the pair; `config/models.py:250` field never read anywhere | BOTH_REQUIRE_RETHINKING | REMOVE (or wire in if speaker-attributed lyrics timing is a real future need) |
| P2-F6 | `[VERIFIED-REVISED]` `rhythm/beats.py::detect_tempo_changes` is dead-in-production, behaviorally diverged from the live `tempo.py` version, still directly unit-tested, **and is the package's own exported public API** (`rhythm/__init__.py` re-exports it, not `tempo.py`'s version) | MEDIUM (raised from LOW-MEDIUM) | CONFIRMED | `beats.py:194-282` (hygiene-corrected range) vs `tempo.py:11-97`; `analyzer.py:51,612` imports only `tempo.py`'s version via module-qualified path; `rhythm/__init__.py` re-exports `beats.py`'s; `test_beats.py:402-560` still exercises the dead copy | IMPLEMENTATION_DIVERGES_FROM_INTENT | REMOVE (delete the dead function and its dedicated tests; fix the `__init__.py` re-export regardless of which copy is kept) |
| P2-F7 | Three `SongSectionDetector` private methods duplicate `orchestration.py` module functions; the dead `_compute_section_descriptors` copy is missing a bounds guard the live version has | LOW-MEDIUM | CONFIRMED | `structure/sections.py:449-505,599-741,829-864` vs `orchestration.py:16-84,87-254,257-307`; guard gap at `orchestration.py:169-179` vs unguarded `sections.py:665-669` | IMPLEMENTATION_DIVERGES_FROM_INTENT | REMOVE |
| P2-F8 | `[VERIFIED-REVISED]` `structure/models.py::Section`/`SectionDiagnostics` Pydantic validators never execute against production data — sections/diagnostics are built as plain dicts everywhere, **and the model has since diverged from production dict shape** (extra fields, invalid label values under current constraints) | MEDIUM | CONFIRMED | `models.py:26-81,84-139`; repo-wide grep: zero production `Section(...)` constructor calls outside the model's own docstring example; `orchestration.py:233-252,297-307` build plain dicts with fields/values the model doesn't accept as-is | ALIGNED_BUT_FLAWED | MODERNIZE (revised from FIX — reconcile the model's schema with actual production output before wiring it in; not a mechanical one-line swap) |
| P2-F9 | `SectioningPreset.context_weights` is populated and validated for all 11 genre presets but never read by any downstream logic | LOW-MEDIUM | CONFIRMED | `presets.py:41-206` (construction); `models.py:182-209` (field+validator); repo-wide grep for `context_weights` shows zero readers in `orchestration.py`/`labeling.py`/`segmentation.py`/`descriptors.py`, which use hardcoded thresholds instead | IMPLEMENTATION_DIVERGES_FROM_INTENT | REMOVE, or wire in if per-genre weighting was an intended differentiator |
| P2-F10 | `[VERIFIED-REVISED, evidence strengthened]` `SongBundle.features` is an untyped `dict[str, Any]` wrapping a legacy, independently-versioned (`"2.3"`) schema; this boundary has already caused silent-drift incidents (P2-F1, P2-F4) undetected by any test, **and produces a type-inconsistent field even within a single unchanged schema version** (`beat_confidence` is `float` on the success path, `[]` in `_minimal_features`) | HIGH | CONFIRMED | `models/song_bundle.py:49-51`; `test_song_bundle.py:22-27` (typo'd key accepted with no error); `analyzer.py:667` (float) vs `analyzer.py:728` (empty list), both under `schema_version: "2.3"` | BOTH_REQUIRE_RETHINKING (PROVISIONAL — feeds Stage 2) | MODERNIZE (model the stable, downstream-consumed key subset at minimum; see §6) |
| P2-F11 | Cache `step_version="3"` is a static literal, decoupled from `features["schema_version"]`/`SongBundle.schema_version`; nothing bumps it on internal schema change, so a future drift could silently serve stale-shaped cached data through the untyped `features` field | MEDIUM-HIGH | CONFIRMED | `cache_adapter.py:68,113`; `caching/models.py:23` (`step_version` documented as "bump on logic/schema changes," a manual convention with no enforcement); only production callers (`analyzer.py:151,170,193`) all rely on the unchanged default | ALIGNED_BUT_FLAWED | FIX (derive `step_version` from a schema constant colocated with `features["schema_version"]`, or add a schema hash to the cache key) |
| P2-F12 | Two numerically-identical STFT computations run per `analyze()` call under default config; `spectral/basic.py` additionally recomputes its own magnitude spectrogram internally instead of reusing the precomputed one (inconsistent with `spectral/bands.py`, which does reuse it) | MEDIUM | CONFIRMED | `analyzer.py:542-544,592-594` (both `n_fft=2048` under default `frame_length`); `spectral/basic.py:27-35` (`y=`-only calls) vs `spectral/bands.py:39-43` (accepts/reuses `stft_mag`) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX |
| P2-F13 | `[VERIFIED-REVISED, reversed in scope]` MusicBrainz's documented 1 req/sec, no-concurrent-requests policy is acknowledged but not enforced, and `metadata/pipeline.py` contains code that would fire concurrent MBID lookups — **but this path is currently UNREACHABLE**: AcoustID's own `_parse_response` raises `TypeError` on every call (phase 1's P1-F1), so no real MBIDs ever reach the `asyncio.gather`. Latent, not live. Becomes live the moment P1-F1 is fixed unless pacing lands in the same change | MEDIUM (downgraded from MEDIUM-HIGH; live risk if sequenced wrong) | CONFIRMED | `musicbrainz.py:6-9,33-35` (documented, not implemented); `metadata/pipeline.py:161-164` (`asyncio.gather(*mb_tasks)`); `acoustid.py:87,112` + `api/http/client.py:622-635` (P1-F1 mechanism); `config/models.py:315-323` (unused pacing config fields); `test_musicbrainz_client.py:216-228` (log-string-only assertion) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX — **Stage 8 sequencing constraint: bundle with the P1-F1 fix, do not fix P1-F1 alone** |
| P2-F14 | `[VERIFIED-REVISED, narrowed]` WhisperX transcription is never gated on vocal presence (`vocal_segments` used only for a post-hoc quality metric); narrowed because WhisperX defaults **off** and `vocal_presence_pct` is already surfaced to the downstream lyrics agent — the gap is "nothing acts on an available signal," and any fix is blocked on P2-M2 (vocal detector itself is time-misaligned) | MEDIUM (narrowed from MEDIUM-HIGH) | CONFIRMED | `lyrics/pipeline.py:161-170` (transcribe call site), `334-337,530-533` (`vocal_segments` post-hoc only); `config/models.py:244-246` (`enable_whisperx` default `False`) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (gate on `vocal_presence_pct`, sequenced **after** P2-M2's alignment fix) |
| P2-F15 | `g2p_service.py` constructs a fresh `G2p()` instance (disk-backed CMUdict + LSTM model) on every call, inside a per-word loop | LOW-MEDIUM | CONFIRMED | `g2p_service.py:103`; `phonemes/bundle.py:94-106` (per-word loop call site); no module-level/cached instance anywhere in the file | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (module-level or service-level cached instance) |
| P2-F16 | `PhonemeBundle` has no `stage_status` field — the `StageStatus` degradation pattern applied to metadata/lyrics is silently absent for phonemes | LOW-MEDIUM | CONFIRMED | `models/phonemes.py` (no `stage_status` field); `phonemes/bundle.py` never imports `StageStatus` | ALIGNED_BUT_FLAWED | FIX (add for consistency) |
| P2-F17 | `[VERIFIED-REJECTED → INFO]` Original claim: silent/degenerate audio can produce `NaN` key-detection confidence. Direct trace of `key.py:50-53`'s epsilon-smoothed correlation shows this is false — silence produces a deterministic `confidence: 0.0`, not `NaN` (no `0/0` occurs; the `+1e-9` denominator with a `0.0` numerator yields exactly `0.0`). No live defect. Salvage: the existing silent-audio test doesn't explicitly assert `confidence == 0.0`, so the correct behavior isn't locked in by a test | INFO | REJECTED — mechanism was assumed, not read, in the original draft; corrected at Stage 7 by direct trace | `harmonic/key.py:50-53,72,86-88`; `test_key.py:117-132` | ALIGNED_AND_SOUND | KEEP (optionally strengthen the existing test to assert the exact deterministic value) |
| P2-F18 | `LyricsBundle.schema_version` docstring (`3.0.0`) contradicts all 4 actual construction sites (hardcoded `"1.0.0"`) | LOW | CONFIRMED | `models/lyrics.py:140` vs `lyrics/pipeline.py:178,391,484,571` | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (align version string, decide which is correct) |
| P2-F19 | `enhancement_factory.py`'s `except ImportError` guard around `WhisperXImpl` import does not actually protect against torch/whisperx import failures (those occur later, inside lazy imports in `whisperx_service.py`, already caught by a broader `except Exception` in `lyrics/pipeline.py`) | LOW | CONFIRMED (re-scoped from manifest.md's "unreachable" framing — the guard IS reachable, for a `python-Levenshtein` `ImportError`, but doesn't cover the risk its placement implies) | `enhancement_factory.py:150-156`; `whisperx_service.py:17-28` (module-level imports, no torch/whisperx); `whisperx_service.py:166-169,251-254` (lazy imports); `lyrics/pipeline.py:494-497,581-584` (broad catch) | ALIGNED_BUT_FLAWED | FIX (clarify comment/placement; low priority given the redundant catch already covers real exposure) |
| P2-F20 | Audio/ passes lyrics text and provider metadata strings (artist/title/album) into Pydantic string fields with no `max_length`, no character bounding, no sanitization — the audio-side half of a prompt-injection/trust-boundary concern whose LLM-consumption half belongs to phase 3 | MEDIUM (as an audio-side boundary gap; severity of the full concern depends on phase 3's findings) | CONFIRMED (audio-side); phase-3-dependent for full severity | `models/lyrics.py:41,59,157-159`; `models/metadata.py:56-65,93-95` (all plain `str`, no `max_length`); `merge.py`'s `raw: dict[str, Any]` (`models/metadata.py:103`) stores full uncapped provider payloads | BOTH_REQUIRE_RETHINKING (cross-phase) | FIX (add `max_length`/basic bounding at the audio boundary as defense-in-depth, independent of what phase 3 does downstream) |
| P2-F21 | `HAS_SCIPY` fallback pattern is independently defined/duplicated in 3 files within this phase's scope | LOW | CONFIRMED | `advanced/tension.py:15-17,109`; `energy/multiscale.py:19-21,45`; `energy/builds_drops.py:14-19,78` | IMPLEMENTATION_DIVERGES_FROM_INTENT | SIMPLIFY (centralize in `utils.py`, which currently has no `HAS_SCIPY` definition at all) |
| P2-F22 | `[VERIFIED, hygiene]` `LyricsSourcePath`/`G2PSource` enums duplicate live enums (`LyricsSourceKind`/`PhonemeSource`) and are exported but never referenced outside `models/` | LOW | CONFIRMED | `models/enums.py:14-21,24-29` vs `models/lyrics.py:19-26`, `models/phonemes.py:25-36`; `models/__init__.py:41-42` exports both dead enums | IMPLEMENTATION_DIVERGES_FROM_INTENT | REMOVE |
| P2-F23 | `[VERIFIED, hygiene — exact ranges added]` Near-verbatim quality-penalty logic (coverage/overlap/OOB/gap penalties, clamping) is triplicated across `lyrics/pipeline.py`'s `_finalize_bundle` (from line 301, `overlap_penalty` at 352-353), `_try_whisperx_align` (from line 401, `overlap_penalty` at 456-457), and `_try_whisperx_transcribe` (from line 499, `overlap_penalty` at 543-544) | LOW | CONFIRMED | `lyrics/pipeline.py:301,352-353,401,456-457,499,543-544` | ALIGNED_BUT_FLAWED | SIMPLIFY (extract shared helper) |
| P2-F24 | `[VERIFIED-REVISED to the defensible form]` The DSP test suite includes real ground-truth-adjacent assertions (~15, including a Foote-novelty reference-loop check) — but **no test anywhere asserts a detected tempo value, beat position, or key label against a known-correct reference value**; existing "known ground truth" fixtures (`click_track_120bpm`, the `beat_freq=2.0` integration WAV) are constructed but never actually checked against | HIGH | CONFIRMED | `tests/unit/audio/conftest.py:16-111` (`click_track_120bpm`, used by only 2 files for non-tempo assertions); `test_pipeline.py`'s `beat_freq=2.0` (120 BPM) never asserted; repo-wide fixture search returns zero real audio files | ALIGNED_BUT_FLAWED | FIX (add explicit tempo/beat/key ground-truth assertions using the fixtures that already exist — this is a test-writing task, not new tooling) |
| P2-F25 | `tests/integration/audio/test_lyrics_analyzer_integration.py` performs no real audio decoding and mocks `_process_audio` directly — mislabeled as integration | LOW-MEDIUM | CONFIRMED | file content: `.touch()` zero-byte files, `patch.object(analyzer, "_process_audio")` at every test | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (relabel/relocate; coordinate with phase 7's broader integration-marker findings rather than duplicating remediation) |
| P2-M1 | `[ADDED Stage 7, HIGH]` `_build_song_bundle`'s parallel metadata+lyrics extraction passes `metadata_bundle=None` into the first lyrics pass; with WhisperX enabled the first pass resolves non-`SKIPPED` via ASR before the metadata-aware retry can fire, so LRCLib/Genius (the pipeline's own declared higher-priority sources) are **never actually consulted** when metadata would have resolved — an inversion of the documented fallback order under normal parallel execution, not just an edge case. With WhisperX off, the cost is a fully redundant second lyrics-extraction pass instead | HIGH | CONFIRMED | `analyzer.py:274-289` (parallel gather with `None` metadata on first pass), `:380-395` (artist/title resolution from metadata), retry condition at `:282-288` gated on `stage_status == SKIPPED` | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (resolve metadata before starting lyrics extraction, or restructure the retry condition to also cover "resolved via lower-priority ASR fallback") |
| P2-M2 | `[ADDED Stage 7, HIGH]` `spectral/vocals.py` reconstructs `hop_length` by inverting rounded (`round(...,3)`) timestamps rather than receiving the real value — at the app's default `sr=44100`/`hop_length=512`, this recovers `529` instead of `512`, misaligning the vocal detector's RMS computation by ~6-8 seconds over a 4-minute track (≈3% of a song), silently, on every run; live, not an edge case; also blocks P2-F14's remedy | HIGH | CONFIRMED (including direct recalculation of the 512→529 drift) | `spectral/vocals.py:43-46`; `spectral/basic.py:43` (`as_float_list(times_s, 3)`, source of the rounding); `analyzer.py:574` (call site passing the rounded array) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (pass the real `hop_length` through explicitly instead of reconstructing it from rounded times) |
| P2-M3 | `[ADDED Stage 7, cross-phase confirmation]` Independent audio-side confirmation of phase 1's P1-F1 (`AcoustIDClient._parse_response` raises `TypeError` on every call because it's handed an `httpx.Response`, not a parsed dict) — this phase's §3.6/§4 are reconciled to this finding; the original P2-F13 framing (live MusicBrainz concurrency violation) is downgraded to latent as a direct consequence | HIGH (as confirmation of an existing HIGH finding, owned by phase 1) | CONFIRMED | `acoustid.py:87,112`; `api/http/client.py:622-635`; see phase 1's `foundation-and-orchestration.md` for the owning finding | IMPLEMENTATION_DIVERGES_FROM_INTENT | Owned by phase 1; this phase's role is reconciliation only (§3.6, §4, §8) |
| P2-M4 | `[ADDED Stage 7, MED-HIGH]` `energy/builds_drops.py` sorts the builds list by `energy_gain` descending (line 284) **before** the adjacent-build merge loop (287-304), which assumes list order is chronological (`gap = build["start_s"] - last["end_s"]`) — once sorted by energy, that assumption breaks, causing incorrect merges and a returned `builds` list not guaranteed to be time-ordered | MEDIUM-HIGH | CONFIRMED | `energy/builds_drops.py:284,287-304` | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (sort only for the "keep most significant" selection step, or re-sort by `start_s` before the merge loop) |
| P2-M5 | `[ADDED Stage 7, MEDIUM]` `structure/sections.py`'s trim-offset reuse guard (`_pass_precomputed = start_offset_s == 0.0`, line 290) correctly gates chroma/onset/STFT/HPSS reuse but **not** `rms_for_energy`, which is passed unconditionally (lines 323, 340) despite being computed on the original (untrimmed) timeline while boundaries/beats are on the trimmed (work) timeline — any track with leading silence gets every section's energy read from the wrong offset | MEDIUM | CONFIRMED | `structure/sections.py:281,290,323,340`; `analyzer.py:525-528` (`rms_for_energy` source, original timeline) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (offset-correct `rms_for_energy` before passing it into work-timeline-indexed functions, or include it in the `_pass_precomputed` guard) |
| P2-M6 | `[ADDED Stage 7, MEDIUM]` `spectral/basic.py`'s `spectral_flatness` computation omits `hop_length=hop_length` (unlike the three sibling calls in the same function), so it runs at librosa's default hop rather than the job's configured hop — invisible under default config (both happen to be 512) but silently misaligns against `times_s` and every other spectral array under any non-default `hop_length` job config | MEDIUM | CONFIRMED | `spectral/basic.py:27-38` (contrast with sibling calls); `tests/unit/audio/conftest.py` pins `hop_length=512` throughout, masking the bug in tests | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (add `hop_length=hop_length` to the `spectral_flatness` call) |
| P2-M7 | `[ADDED Stage 7, MEDIUM]` `energy/builds_drops.py` hardcodes 4 beats per bar (`bar_duration_s = 60.0 / tempo_bpm * 4`) for build/drop window sizing, ignoring the time signature already detected upstream — a track in 3/4 gets windows sized ~33% too long | MEDIUM | CONFIRMED | `energy/builds_drops.py:88`; `analyzer.py:503-506` (time signature already available and discarded for this purpose) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (thread `beats_per_bar` through instead of hardcoding `4`) |
| P2-M8 | `[ADDED Stage 7, MEDIUM]` `harmonic/hpss.py`'s `compute_hpss` silently collapses to returning the same array for both harmonic and percussive components on any exception, with no log line and no status flag — downstream `harmonic_ratio` calculations (e.g. vocal detection) then compute a constant `~0.5` across the whole track with no visible signal that HPSS failed | MEDIUM | CONFIRMED | `harmonic/hpss.py:18-24`; `spectral/vocals.py:59` (`harmonic_ratio = rms_h / (rms_h + rms_p + 1e-9)`, collapses when `y_harm == y_perc`) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (log a warning and/or set a status flag on HPSS fallback, so downstream consumers and diagnostics can distinguish "genuinely balanced harmonic/percussive content" from "HPSS failed") |
| P2-M9 | `[ADDED Stage 7, LOW-MEDIUM]` `features["rhythm"]["beat_confidence"]` is mislabeled — it actually holds the time-signature-detection confidence (`time_sig_result.get("confidence", 0.0)`), not a beat-tracking or per-beat confidence — compounding the existing type inconsistency (float vs. empty list, P2-F10) with a semantic mismatch between field name and content | LOW-MEDIUM | CONFIRMED | `analyzer.py:667` (`time_sig_result.get("confidence", 0.0)` assigned to `beat_confidence`) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (rename to `time_signature_confidence`, or compute an actual beat-tracking confidence if one is wanted under this name) |
| P2-M10 | `[ADDED Stage 7, LOW-MEDIUM]` `enhancement_factory.py` constructs two `AsyncApiClient`/`httpx.AsyncClient` connection pools per `AudioAnalyzer` and never calls `aclose()` on either, anywhere in `core/audio/`, `core/pipeline/`, or `cli/` — both are also constructed with placeholder `base_url`s, offering no real safety net from that field | LOW-MEDIUM | CONFIRMED | `enhancement_factory.py:61-62,115-116`; `api/http/client.py:454,468-476` (`aclose`/context-manager support exists but is unused); repo-wide grep for `aclose()` in the relevant packages returns zero hits | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (close clients on `AudioAnalyzer` teardown, or make `AsyncApiClient` a shared/pooled resource with explicit lifecycle) |
| P2-M11 | `[ADDED Stage 7, MEDIUM]` Five network-feature `enable_*` flags default to `False`, and `AppConfig` is a plain Pydantic model with no environment-variable binding — setting `ACOUSTID_API_KEY`/`GENIUS_ACCESS_TOKEN` in the shell, as several field docstrings instruct, produces no behavior change unless the corresponding `enable_*` flag is also separately set to `true` in `config.json`; same "documented, silently a no-op" class phase 7 independently found in the user guide (P7-M2) | MEDIUM | CONFIRMED | `config/models.py:234-249` (`enable_*` defaults), `226` (`ConfigDict(extra="ignore")`, not `BaseSettings`), `:309,313` (docstrings instructing env-var setup) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (either bind these fields to env vars directly, or correct the docstrings/docs to state the `config.json` flag is also required) |
| P2-M12 | `[ADDED Stage 7, MEDIUM-HIGH]` `structure/sections.py`'s live, called `_build_result` method contains a commented-out real derivation for `discrimination` immediately followed by `discrimination = 0.5  # Placeholder`, and a second hardcoded `"repeat_threshold_derived": 0.9  # Placeholder` — both ship in every production `SongBundle`'s `structure.meta` as if computed, with nothing distinguishing them from genuine metrics | MEDIUM-HIGH | CONFIRMED | `structure/sections.py:359` (live call site), `791-795,824-825` (placeholders and commented-out real computation) | IMPLEMENTATION_DIVERGES_FROM_INTENT | FIX (restore the real computation, or explicitly flag these as unimplemented placeholders in the output schema rather than shipping them silently as data) |
| P2-M13 | `[ADDED Stage 7, LOW, verifier-reported]` Additional dead structure-detection code beyond P2-F7/F9 was flagged by the verifier during deeper tracing; this author did not independently re-derive exact line ranges within this revision's scope — recorded here for Stage 8 triage rather than dropped, pending a follow-up grep pass through `structure/` for further unreferenced private methods/fields beyond those already itemized in F7-F9 | LOW | UNVERIFIED BY THIS AUTHOR (verifier-reported, not independently re-traced at this revision) | `structure/` (verifier's original report; re-derivation deferred) | INSUFFICIENT_EVIDENCE | Defer to Stage 7 verifier's own artifact or a targeted Stage 8 follow-up grep before triaging |
| P2-M14 | `[ADDED Stage 7, LOW]` `energy/profiling.py`'s per-genre `gradient_percentile` preset value (distinct from the actually-used `drop_gradient_percentile`) is defined for all 6+ genre profiles but only ever read for a debug log string (`builds_drops.py:70`) — never used in any threshold computation, unlike its sibling `drop_gradient_percentile` which is genuinely load-bearing (`builds_drops.py:105-107`) | LOW | CONFIRMED | `energy/profiling.py:144,151,158,165,172,179` (definitions); `energy/builds_drops.py:70` (log-only use) vs `:105,107` (real use of the differently-named field) | IMPLEMENTATION_DIVERGES_FROM_INTENT | REMOVE (or wire in if a genre-specific build-gradient threshold, distinct from the drop threshold, was intended) |

**Strengths logged as findings** (INFO severity, not defects): shared beat-grid
timing authority; chroma/onset/HPSS precomputation-reuse discipline (with three
documented exceptions, §9); layered enhancement-stage degradation; `merge_metadata`
determinism testing; P2-F17's corrected deterministic silent-audio behavior (§9).

## 11. Unresolved questions & cross-phase dependencies

- **Stage 2 dependency (PROVISIONAL, central)**: whether `SongBundle.features`
  should be partially or fully modeled (§6, P2-F10) is a cost/benefit call that
  depends on Stage 2's verdict on how actively the audio schema is expected to keep
  evolving, and on Stage 8's remediation-budget constraints.
- **Stage 2 dependency**: whether `genre/classifier.py`/`context/{hints,
  unified_map}.py` should be rewritten against the current schema (and the
  `sample_song_features` fixture corrected alongside) or removed (§10, P2-F4)
  depends on whether the lighting-hints/unified-map capability is still a wanted
  product feature.
- **Phase 1 dependency, now load-bearing (not just informational)**: P1-F1 (AcoustID
  `TypeError` on every call) directly determines whether P2-F13's MusicBrainz
  concurrency violation is live or latent (§3.6, §4, §10). **Stage 8 sequencing
  constraint**: any fix to P1-F1 must land MusicBrainz pacing in the same change,
  or it converts a latent finding into a live one.
- **Phase 3 dependency**: P2-F20 (unsanitized lyrics/metadata text at the audio
  boundary) is only half the picture — phase 3 owns whether that text is escaped,
  length-bounded, or otherwise defended against before reaching an LLM prompt
  template. Also relevant to phase 3: P2-M1's fallback-order inversion means the
  lyrics text phase 3 receives may currently be lower-fidelity ASR output more
  often than the pipeline's documented design implies.
- **Sequencing dependency within this phase**: P2-F14's WhisperX vocal-gating fix
  should not land before P2-M2's vocal-detector alignment fix — gating on
  misaligned evidence would be a false sense of correctness.
- **Phase 6 dependency**: `feature_engineering/`'s consumption of `SongBundle`
  (out of this phase's scope) should be checked by phase 6 against the same
  untyped-`features` risk (P2-F10) — if it also does positional dict access against
  the same schema, phase 6 inherits the same fragility, and the newly-found
  `beat_confidence` type inconsistency (P2-F10/M9) specifically.
- **Stage 4 dependency**: actual production call volume to AcoustID/MusicBrainz
  would sharpen whether P2-F13's fix should be a lightweight sequential-delay
  change or a proper rate limiter. Stage 4 is also the right place to cheaply
  confirm or refute the SUSPECTED MFCC mel-scale question (§4) by comparing
  `structure/features.py`'s output against a reference `librosa.feature.mfcc(y=y,
  sr=sr)` call on the same input.
- **Stage 8 follow-up**: P2-M13 (additional dead structure code, verifier-reported
  but not independently re-traced at this revision) needs either the verifier's own
  underlying evidence pulled forward or a fresh targeted grep pass through
  `structure/` before triage — do not action on the current one-line description
  alone.

## 12. Phase verification status

VERIFIED (2026-08-13, opus code-reviewer)
