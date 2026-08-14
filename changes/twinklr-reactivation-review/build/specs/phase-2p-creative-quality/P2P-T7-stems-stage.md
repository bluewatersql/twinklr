# P2P-T7 — Stems stage (D8)

Phase: 2P (Creative Quality, Measured) · Lane: M (analysis substrate, parallel) · Executor: sonnet · Verifier: opus · Depends on: P1P-T8

## Objective

Add source separation as an opt-in, cached analysis stage, and derive from it the
three per-stem features that are the highest-leverage new planner signals: drum-stem
onsets for accent/beat confidence, bass-stem energy for build/drop truth, and
vocal-stem presence as the lyrics/WhisperX gate — replacing the full-mix vocal
detector whose alignment defect P1P-T8 just fixed.

## Evidence & background

Finding: **D8 (designed, was a mention)** — research-verified, accessed 2026-08-13.
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D8,
D7 (torchaudio watch item), §5 (risks); `.../reviews/verification.md` "Phase 2"
(P2-M2, P2-F14); `.../reviews/findings.md` SF-1, SF-2.

### D8 quoted in full (the version, licence and integration facts are load-bearing)

> **D8 — Stems (designed, was a mention)**: adopt **demucs 4.1.0** from the
> maintained repo (adefossez/demucs — facebookresearch is archived; 4.1.0 released
> 2026-07-11, MIT, `>=3.10`, torch unpinned so 2.8-compatible, torchaudio no longer
> required; MPS automatic on Apple Silicon; htdemucs 9.0 dB SDR, `htdemucs_ft` +0.2
> dB at 4× cost). **Integration**: an opt-in, cached analysis stage (≈1–2 min/song
> MPS, ~6 min CPU) producing per-stem features — drum-stem onsets → accent/beat
> confidence for both planners, bass-stem energy → build/drop truth, vocal-stem
> presence → replaces the misaligned full-mix vocal detector as the lyrics/WhisperX
> gate. Fallback option if torch-free is ever wanted on macOS: `demucs-mlx`
> (single-maintainer risk, noted). Cache key = audio hash + model name.

Related constraint from D7 (dependency hygiene):

> Watch item: torchaudio is in maintenance wind-down (decode/encode moved to
> TorchCodec in 2.10, 2026-01) — prefer deps that don't hard-require it (demucs 4.1.0
> already dropped it; beat-this still declares it).

Risk note from §5:

> **New-dependency risk (D10/D8)**: `all-in-one-mlx` and `demucs-mlx` are
> single-maintainer; mitigations — canonical demucs is multi-year stable, beat-this
> is CPJKU-institutional, and the A/B gate means we never depend on a model we
> haven't verified against our own fixtures.

So: **adopt canonical demucs 4.1.0 from adefossez/demucs. `demucs-mlx` is a named
fallback, not the target, and carries single-maintainer risk.**

### What this replaces

- **P2-M2 (HIGH)**: `spectral/vocals.py` "reconstructs hop_length by inverting rounded
  timestamps (512→529 at 44.1kHz) → vocal-detector evidence drifts ~6-8s out of
  alignment over a 4-min track, ~3% of song truncated, invisible in output — live on
  every run". P1P-T8 fixes that arithmetic. This task supersedes the *detector* where
  stems are available: a separated vocal stem's presence is direct evidence, not an
  inference from the full mix.
- **P2-F14**: WhisperX has no vocal gate; `vocal_presence_pct` "IS surfaced to the
  lyrics agent — nothing acts on it". With stems, the gate becomes real. (Note
  `LyricContextModel.vocal_presence_pct` as a *solicited response field* is on
  P2P-T1's deletion list — that is the LLM echoing it back, a different thing from
  the computed input. Do not confuse the two.)
- **SF-1 / P2-M4**: builds/drops correctness. Bass-stem energy gives build/drop a
  truth source rather than full-mix energy heuristics. P1P-T8 fixes the merge
  time-order violation; this task improves the input.

### xLights context (M6)

> stem-aware "Generate AI Lyrics" with HTDemucs separation (2026.11)

The host application already ships HTDemucs separation. That does not change this
task, but it is evidence the approach is standard, and it is worth noting in the
handoff that Twinklr and xLights may end up separating the same audio twice.

## Current behavior

- No source separation exists in the repository. All audio features derive from the
  full mix (`core/audio/` — `spectral/`, `energy/`, `rhythm/`, `structure/`,
  `harmonic/` verified present).
- Vocal presence is inferred from the full mix by `spectral/vocals.py`.
- WhisperX runs without a vocal gate (defaults off).

## Target behavior

1. **An opt-in cached analysis stage.** Off by default. When enabled, it separates the
   song into stems once and caches the result; every later feature computation reads
   the cache. Runtime expectation: ≈1–2 min/song on MPS, ~6 min CPU.
2. **Cache key = audio hash + model name** (D8, verbatim). Not the file path, not a
   session id. This matters: CC-5 records "random session UUID defeats reuse" and
   "CWD-relative root" as existing cache defects that P1P-T9 fixes — the stems cache
   must be built on the fixed foundation, and its key must make re-running with a
   different separation model a clean miss.
3. **Three derived feature families**, each landing in the existing feature schema
   beside their full-mix equivalents (not replacing them silently):
   - **drum-stem onsets → accent/beat confidence** for both planners;
   - **bass-stem energy → build/drop truth** feeding the builds/drops detector;
   - **vocal-stem presence → the lyrics/WhisperX gate**, replacing the full-mix
     detector where stems exist.
4. **Graceful, loud degradation.** With stems disabled or unavailable, every consumer
   falls back to the full-mix path and **records that it did**. CC-3 (silent-degradation
   class) is the pattern to avoid: "HPSS except-Exception fallback silently collapses
   harmonic_ratio to 0.5 everywhere (no log, no status)". A stems fallback emits a
   status flag that reaches the analysis result, not just a DEBUG log.
5. **Dependency hygiene.** demucs 4.1.0 from the maintained repo (MIT, `>=3.10`, torch
   unpinned, torchaudio not required). Declare it as an **optional extra**, not a core
   dependency — the stage is opt-in and the ML chain bump (D7/M3) is Phase 4 work.
   Do not pin torch here; do not introduce a torchaudio requirement.
6. **MPS is automatic on Apple Silicon**; do not hand-roll device selection beyond
   what demucs does, and do not assume CUDA.

### Non-goals

- The MIR model A/B (**P2P-T8**) — separate task, separate gate.
- The coordinated torch/whisperx/pyannote/Python bump (**Phase 4**, D7/M3).
- `demucs-mlx` adoption (named fallback only; single-maintainer risk).
- `htdemucs_ft` as the default (+0.2 dB SDR at 4× cost — not worth it; make it a
  config option if trivial).
- Re-architecting the analysis pipeline. This is one new cached stage plus three
  feature consumers.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/audio/` — the analysis package; add the stems stage beside
  the existing families. Follow `analyzer.py`'s stage conventions and
  `cache_adapter.py`'s caching seam rather than inventing a parallel cache.
- `packages/twinklr/core/audio/spectral/vocals.py` — the full-mix detector; becomes
  the fallback path, not the primary, when stems are present.
- The builds/drops detector under `energy/` or `structure/` — bass-stem energy input.
- The onset/rhythm path under `rhythm/` — drum-stem onsets input.
- WhisperX gating (lyrics stage) — vocal-stem presence input.
- Dependency declaration: the workspace `pyproject.toml` optional-dependencies.

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.
> - `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
>   pass at every merge.

Lane constraint from the phase doc: Lane M is `T7 → T8`, and **merges before T13**.
T8 changes the beat/downbeat source; T7 changes the feature substrate. Land T7 first
so T8's A/B runs against a stable feature layer.

Test-hygiene constraint: the default test suite must not download model weights or
require torch. CC-7 records "NLTK network dep" as a finding — "unit tests require a
live NLTK download" is itself a defect. Do not add a second instance of it.

## Acceptance criteria

1. The stems stage exists, is **off by default**, and when enabled produces cached
   per-stem audio (or per-stem features) keyed by **audio hash + model name**.
2. Re-running an identical analysis with stems enabled is a cache hit (no second
   separation); changing the model name is a clean miss.
3. Drum-stem onsets, bass-stem energy and vocal-stem presence are computed and reach
   their three consumers (accent/beat confidence, builds/drops, lyrics/WhisperX gate).
4. With stems disabled, every consumer falls back to the full-mix path and the
   analysis result carries an explicit status flag recording the fallback — verified
   by a test asserting the flag, not a log line.
5. On a fixture song with stems enabled, vocal-presence gating behaves correctly on
   both an instrumental fixture (gate closed) and a vocal fixture (gate open).
6. demucs is declared as an optional extra; `uv sync` without the extra still
   installs and the full suite still passes; no torchaudio requirement is introduced.
7. The default test suite runs with no model download and no network.
8. `make validate` check-only forms pass.

## Tests

1. `test_stems_stage_disabled_by_default` — the config default, pinned.
2. `test_stems_cache_key_is_audio_hash_plus_model` — same audio + same model → hit;
   different model → miss; different audio → miss. Ground-truth assertions on the key
   itself, not on timing.
3. `test_fallback_sets_status_flag` — stems unavailable → full-mix path taken **and**
   the status flag present in the result (the CC-3 guard).
4. `test_drum_onsets_feed_accent_confidence` / `test_bass_energy_feeds_builds_drops` /
   `test_vocal_presence_gates_transcription` — each with a stubbed separator returning
   synthetic stems, so no model weights are needed.
5. `test_instrumental_fixture_gates_off_transcription` — end-to-end-ish with the
   stubbed separator.
6. **LOCAL-ONLY** `test_real_separation_smoke` — one short real song through demucs
   4.1.0 on MPS, asserting four stems appear and the runtime is within an order of
   magnitude of the 1–2 min expectation. Marked, excluded from CI.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/audio -q
uv run pytest -m "not local_only" -q
uv sync --extra dev --all-packages          # must succeed WITHOUT the stems extra
```

LOCAL-ONLY (Apple Silicon, stems extra installed):

```bash
uv sync --extra stems
uv run pytest -m local_only -k separation -q
```

No paid API calls.

## Effort & risk

**M.** Main risk: dependency weight. demucs pulls torch, and torch's version is
contested territory — whisperx currently pins `torch~=2.8.0` while the repo's lock has
2.4.0, and the coordinated bump is deliberately Phase 4 work. Mitigation: optional
extra, torch unpinned by demucs 4.1.0 (verified), no torchaudio requirement, and a
default suite that never imports it. If `uv sync --extra stems` cannot resolve against
the current lock, **stop and report** rather than bumping torch inside this task —
that is D7/M3's change to make. Second risk: silent quality regression if a consumer
switches to stem-derived features without comparison; mitigated by keeping both
feature families present and flagging which was used, so P2P-T8's A/B and P2P-T13's
comparison can attribute changes correctly.

## Implementation handoff (2026-08-14)

Implemented, pending the independent verifier/owner gates below:

- Added the opt-in `StemSeparationConfig` and a lazy Demucs adapter. The default
  environment neither imports Demucs nor downloads weights. Demucs's own device
  default supplies automatic MPS selection; an MPS runtime failure retries once on
  CPU and records a warning.
- Cached compact derived features through `FSCache` with the exact
  `sha256(audio_hash:model_name)` identity. Only successful separation is reusable;
  unavailable results are not stored as successful stem cache entries, and enabled
  SongBundle caches with missing/unavailable/wrong-model status are rejected.
- Wired drum-stem onsets into beat/accent confidence, bass-stem energy into the
  existing build/drop detector, and vocal-stem presence/segments into both the
  primary vocal feature path and the WhisperX gate. Full-mix equivalents and source
  provenance remain beside every selected feature family. Disabled/unavailable
  paths expose an explicit full-mix-fallback status in `SongBundle.features.stems`.
- Surfaced the selected stem signals and provenance to the audio-profile prompt,
  which supplies the shared creative substrate consumed by downstream planning.
- Added root and core `stems` extras plus lock entries. The core extra intentionally
  declares two Demucs requirements:
  `demucs==4.1.0; sys_platform != 'darwin'` and
  `demucs==4.1.0; sys_platform == 'darwin' and platform_machine != 'x86_64'`.
  This keeps Intel macOS installable while runtime analysis reports the explicit
  unsupported/full-mix fallback. No NumPy, Torch, WhisperX, pyannote, or torchaudio
  constraint was changed.

Fresh evidence in the isolated implementation worktree:

- Red first: focused collection failed with
  `ModuleNotFoundError: No module named 'twinklr.core.audio.stems'`.
- Focused stems/config/lyrics/profile contract: `46 passed, 1 skipped` after adding
  the two fixture gate cases; the skip is the declared LOCAL-ONLY real separation.
- Audio suite: `810 passed, 1 skipped`.
- Static gates: Ruff format check `1312 files already formatted`; Ruff check
  `All checks passed`; mypy `709 source files` with no issues.
- `uv sync --extra dev --all-packages` succeeds and removes/omits Demucs and Torch.
- On Apple Silicon, `uv sync --extra stems` resolves and installs Demucs 4.1.0 with
  the existing Torch 2.4.0 and NumPy 2.3.5 (no dependency bump). The equivalent
  `aarch64-apple-darwin` dry run selects Demucs.
- The `x86_64-apple-darwin` dry run resolves successfully and does not select Demucs
  or Torch; the manifest marker unit test pins this behavior.
- Full non-LOCAL suite initially found one strict-template compatibility failure;
  the prompt guard was corrected; the fresh full rerun is green:
  `5070 passed, 25 skipped, 12 deselected` (87% coverage).

Verifier remediation (2026-08-14): outer SongBundle acceptance now recomputes the
expected vocal gate from stored `vocal_presence_pct` and the current configured
threshold. A mismatch in either direction rejects the outer bundle, while the
unchanged audio-hash + model inner key reuses successful stem features. Two
end-to-end cache regressions prove the bundle and lyrics gate rebuild, the refreshed
stem result is an inner-cache hit, and the separator call count remains exactly one.
Unavailable enabled results remain rejected, disabled results remain reusable, and
the outer cache version intentionally stays threshold-agnostic because acceptance
validates the threshold-derived content directly.

Residual owner/verifier gates:

- Run `TWINKLR_REAL_STEMS_AUDIO=<short-song> uv run pytest -m local_only
  -k separation -q` with the stems extra on Apple Silicon. This is the only test that
  downloads/executes the model and is deliberately excluded from default tests.
- Confirm live MPS runtime and the one-time CPU fallback on owner hardware. Intel
  macOS is deliberately unsupported for stems, not an unverified supported target.
- Twinklr and xLights 2026.11 may both separate the same audio. No cache handoff to
  xLights exists in this task, so owners should watch for duplicate runtime/storage.
- No paid API, live xLights, or LOCAL-ONLY model call was made in this lane.
