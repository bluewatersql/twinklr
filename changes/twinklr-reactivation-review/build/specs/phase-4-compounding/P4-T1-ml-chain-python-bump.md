# P4-T1 — ML chain + Python bump (D7)

Phase: 4-compounding · Lane: ml-chain (solo lane; touches `pyproject.toml`, lockfile,
`packages/twinklr/core/audio/lyrics/`, `config/models.py`, CI config) · Executor: opus ·
Verifier: opus · Depends on: Phase 2P merged (per `changes/twinklr-reactivation-review/build/plan/07-phase-4-compounding.md`
task table)

⚖ **Owner-decision-bearing.** The Python 3.12→3.13 interpreter bump is a project-wide
change with no golden-test signal of its own (nothing in the render/audio harnesses
pins interpreter version). The owner reviews: (1) whether to take 3.13 now or defer it
behind M3 dependency landing, (2) whether pyannote-audio 4.x's API surface (unverified
in this repo — no prior 4.x usage exists to diff against) is acceptable to adopt sight
first, (3) whether beat-this/all-in-one-mlx (D10, out of this task's scope but sharing
the torch/torchaudio pin) constrain the timing of this bump.

## Objective

Land one coordinated dependency change — torch/torchaudio 2.8.x, whisperx 3.8.6,
pyannote-audio 3.3.2→4.x, Python 3.12→3.13 — with the orphaned diarization module
deleted FIRST so pyannote 4.x's breaking-change surface has nothing left in-repo to
break. Update `memories/constraints/python-3.12-only.md` to reflect the new floor with
provenance. Land the `sqlite-vec` extra removal (M7) as a zero-risk rider on the same
pyproject edit since it touches the same file and diff review pass.

### Owner amendment — current stable mutually compatible graph (2026-08-26)

The owner chose the newest stable **application graph**, not independently newest
versions of every transitive package. Official stable WhisperX remains 3.8.6 and binds
torch/torchaudio to the 2.8 line, torchvision to the 0.23 line, TorchCodec to 0.6–0.7,
and Python below 3.14; stable pyannote-audio is 4.0.7. Therefore this task retains
Python `>=3.13,<3.14`, torch/torchaudio 2.8.0, WhisperX 3.8.6, and pyannote-audio 4.x.
Torchvision 0.23.0 and TorchCodec 0.7.0 remain transitive lock results rather than new
direct declarations. Independently raising torch or TorchCodec would be incompatible
with current stable WhisperX and is not an upgrade of the usable application stack.

The owner explicitly accepts package resolution/sync while deferring optional
WhisperX/TorchCodec runtime audio execution against the current default FFmpeg 9.0.1,
which the resolved stable TorchCodec does not support. This task makes no runtime-
readiness, audio, or model-download claim. A briefly installed keg-only FFmpeg 7 was
removed without ever being linked; default FFmpeg 9.0.1 remains healthy.

## Evidence & background

**modernization.md M3** (reviews/modernization.md:63–76): whisperx 3.8.6 pins
`torch~=2.8.0` — the target is torch/torchaudio 2.8.x, not the currently locked 2.4.0
and not latest 2.13 (whisperx forbids it). Requires pyannote-audio 3.3.2 → 4.x (major;
"API breakage risk concentrates here — the repo's diarization module is currently
orphaned, which lowers the cost"), plus new whisperx deps: `ctranslate2>=4.5`,
`faster-whisper>=1.2`, `transformers>=4.48`, `torchcodec`, `triton` (linux-only).

**Python version** (modernization.md M3): "the 3.12-only constraint no longer holds
externally — whisperx supports `>=3.10,<3.14`; torch/pydantic support 3.13+. Python
3.12 is now security-only (no new binaries). Recommend 3.12 → 3.13 as part of this
bump; supersedes `memories/constraints/python-3.12-only.md` (update at closeout with
provenance). 3.14 remains blocked by whisperx."

**D7** (reactivation-proposal.md:168–172): "coordinated bump post-M1 — torch 2.8.x,
whisperx 3.8.6, pyannote 4.x (delete orphaned diarization first), Python 3.13 ⚖. Watch
item: torchaudio is in maintenance wind-down (decode/encode moved to TorchCodec in
2.10, 2026-01) — prefer deps that don't hard-require it (demucs 4.1.0 already dropped
it; beat-this still declares it)." The torchaudio wind-down is a **watch item for
future D8/D10 work (out of this task's scope)**, not a blocker here — this task pins
2.8.x per whisperx's own requirement.

**Sequencing constraint, copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:**
> P4-T1 ML chain + Python bump (D7): delete the orphaned diarization module FIRST
> (pyannote-4.x breakage concentrates there), then torch/torchaudio 2.8.x + whisperx
> 3.8.6 + pyannote 4.x + Python 3.12→3.13 ⚖.

**Diarization deletion evidence (P2-F5, deterministic-audio-analysis.md:656):**
`lyrics/diarization.py` + `diarization_models.py` fully orphaned; `enable_diarization`
config flag also dead. "repo-wide grep: only self-import within the pair;
`config/models.py:250` field never read anywhere." Disposition: REMOVE. This is a
subset of the P4-T3 dead-tail wave, pulled forward into this task per the plan's
explicit sequencing note ("diarization goes in P4-T1" — `07-phase-4-compounding.md`
task table, P4-T3 row).

**M7 sqlite-vec (modernization.md:142–146):** "Declared as the `fe` extra, never
imported anywhere. Upstream is healthy but pre-v1 ('expect breaking changes'). Carrying
an unused optional dep on a pre-v1 library is pure liability — drop the extra."

**M5 tooling note (modernization.md:86–91, informational only — NOT in this task's
scope):** ruff 0.15→0.16 and pytest 9.0.2→9.1.1 are trivial and may ride along if
convenient; **mypy 1.19→2.3 is explicitly deferred as its own item — do not bump mypy
in this task**, it will surface a wave of new errors unrelated to the ML chain.

## Current behavior

- `pyproject.toml` pins Python `>=3.12,<3.13` (or equivalent) and torch/torchaudio at
  versions compatible with the currently locked whisperx (pre-3.8.6), pyannote-audio
  3.3.2, and declares the `fe` extra pulling in `sqlite-vec`.
- `packages/twinklr/core/audio/lyrics/diarization.py` and `diarization_models.py`
  exist, self-import only within the pair, and are never called from any live
  pipeline path. `config/models.py:250`'s `enable_diarization` field is read nowhere.
- `memories/constraints/python-3.12-only.md` states 3.12 as a hard, currently-true
  constraint.

## Target behavior

- `packages/twinklr/core/audio/lyrics/diarization.py`, `diarization_models.py`, and
  `enable_diarization` (config/models.py:250 and its call sites, if any beyond the
  dead field itself) are deleted. Any test files exercising only the diarization pair
  are deleted with them (self-contained — verify via grep before deleting: only tests
  importing `diarization.py`/`diarization_models.py` and nothing else qualify).
- `pyproject.toml`/lockfile: torch/torchaudio pinned to 2.8.x, whisperx to 3.8.6,
  pyannote-audio to the 4.x line, Python floor raised to 3.13 (interpreter constraint,
  CI matrix, `requires-python`). New whisperx transitive deps (`ctranslate2>=4.5`,
  `faster-whisper>=1.2`, `transformers>=4.48`, `torchcodec`, `triton` linux-only)
  resolve correctly via `uv lock`.
- `fe` extra (sqlite-vec) removed from `pyproject.toml` entirely.
- `memories/constraints/python-3.12-only.md` updated: either superseded (marked
  resolved, pointing to this task/date) or rewritten to state the new 3.13 floor,
  with provenance (date, this task ID, link to `modernization.md` M3).
- Any code that imports pyannote-audio 3.x-only APIs (search
  `packages/twinklr/core/audio/` and `agents/` for `pyannote` imports beyond the
  deleted diarization module) is updated for 4.x's API surface — **the diarization
  deletion is expected to remove all in-repo pyannote usage**, but verify this
  assumption by grep before assuming zero remaining call sites.

**Non-goals:** D8 (demucs stems), D10 (beat-this/all-in-one MIR upgrade), mypy 2.x
bump, OpenAI SDK 3.x (M4) — all explicitly deferred to later/separate work per
`modernization.md`'s recommended sequencing. Do not touch model-ID retargeting (M1,
already landed in Phase 2P per the plan's dependency).

## Implementation approach

1. **Delete diarization first.** Remove `lyrics/diarization.py`, `diarization_models.py`,
   their dedicated tests, and the dead `enable_diarization` field
   (`config/models.py:250`) plus its Pydantic model entry. Run the full test suite to
   confirm nothing else referenced them (expected: clean, since P2-F5 confirms
   zero non-self importers).
2. **Bump the ML chain in one `pyproject.toml`/lockfile edit**: torch/torchaudio 2.8.x,
   whisperx 3.8.6, pyannote-audio 4.x line, new whisperx transitive deps. Run
   `uv lock` and resolve any conflicts. Remove the `fe` extra (sqlite-vec) in the same
   edit.
3. **Raise the Python floor to 3.13** (`requires-python`, CI matrix files, any
   `python_requires`-adjacent tooling config). Re-run `uv sync --extra dev
   --all-packages` from a clean environment to confirm the resolution succeeds under
   3.13.
4. **Grep for remaining pyannote 3.x API usage** outside the deleted diarization
   module (expected: none, per P2-F5's "self-import only within the pair" — confirm,
   don't assume).
5. **Update the constraint memory**: `memories/constraints/python-3.12-only.md`,
   per the memory protocol in `AGENTS.md` (record provenance and date, link this
   task and `modernization.md` M3).
6. Re-verify all cited line numbers before editing — baseline `aa8d325` evidence,
   the tree will have moved since Phase 2P landed.

## Acceptance criteria

- `lyrics/diarization.py`, `diarization_models.py`, and `enable_diarization` are absent
  from application source. Documentation and contract tests may name the retired
  surface; direct application imports of either deleted module are zero.
- `pyproject.toml` declares torch/torchaudio 2.8.x, whisperx 3.8.6, pyannote-audio
  4.x, Python `>=3.13`; the `fe` extra is absent.
- `uv sync --extra dev --all-packages` succeeds from a clean checkout under Python
  3.13 with no manual intervention.
- `memories/constraints/python-3.12-only.md` reflects the 3.13 floor with dated
  provenance, OR is marked superseded with a pointer to the replacement statement.
- No remaining `import pyannote` outside dependency code (i.e., zero in-repo
  application call sites) — confirmed by grep, not assumed.
- `make validate` passes (format + lint-fix + type-check + test) on the new
  toolchain, modulo any KNOWN pre-existing failures already recorded in
  `memories/learnings/known-test-failures.md` — do not silently absorb new failures
  into that list; any NEW failure caused by this bump must be fixed, not filed away.

## Tests

- No new behavioral tests are expected from this task (it's a dependency/interpreter
  bump, not a feature). The diarization deletion is validated by the existing suite
  passing with the module gone (delete-first, then run tests — a red run before
  deletion would indicate a live caller was missed).
- If any whisperx/pyannote-audio 4.x call site requires an adapter shim (API
  signature changes), add a focused unit test pinning the adapter's behavior against
  the new library version.

## Verification commands

```bash
uv sync --extra dev --all-packages     # clean-checkout resolution under 3.13
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/ -v
test ! -e packages/twinklr/core/audio/lyrics/diarization.py
test ! -e packages/twinklr/core/audio/lyrics/diarization_models.py
! git grep -n 'enable_diarization\|audio\.lyrics\.diarization\|diarization_models' -- packages/twinklr
! git grep -n -E '^(from|import) pyannote' -- packages/twinklr
```

No LOCAL-ONLY steps — this task has no live-API or xLights-GUI dependency. The actual
whisperx/pyannote-audio transcription/diarization pipeline behavior under the new
versions is NOT re-validated end-to-end here (no audio fixture harness exists for
that per the review's SF-1/CC-7 findings); that is out of scope for a dependency bump
and belongs to whichever future task first exercises WhisperX live.

## Effort & risk

**L.** Main risk: pyannote-audio 4.x is a major version with unknown API drift
relative to the deleted 3.3.2-era diarization module — but that module is deleted
FIRST specifically to zero out the in-repo blast radius, per the sequencing
constraint. Residual risk is dependency-resolution conflicts between torch 2.8.x's
transitive requirements and other pinned packages (e.g., pydantic, ruff toolchain) —
mitigate by running `uv lock` in isolation before touching application code, and by
re-verifying the Python 3.13 floor doesn't break any other package in the workspace
(`packages/twinklr/cli`, etc.) before merging.

## Author implementation handoff — 2026-08-26

Status: **independently approved and integrated at `56d9aa0`.** The candidate was based
on `0adb566885866dd6462733eea6e8594703cd48af` in isolated branch
`codex/p4t1-python313`; clean-main `make validate` passed after integration with 5,453
tests passed, 38 skipped, clean Ruff format/lint, and mypy clean across 738 source files.

Implemented:

- Removed the orphaned diarization modules, their dedicated tests, and the dead
  `enable_diarization` config field before changing dependencies. `LyricsWord.speaker`
  remains as a neutral source-provided label.
- Coordinated root/core/CLI on Python `>=3.13,<3.14`, Ruff `py313`, mypy 3.13, and CI
  3.13. The lock requires macOS arm64 and Linux x86_64 environments. Ruff's Python
  3.13 modernization also reduced the two `httpx.Auth` generator annotations to the
  current two-parameter `Generator` form; runtime behavior is unchanged.
- Locked the owner-amended newest stable mutually compatible graph: torch and
  torchaudio 2.8.0, WhisperX 3.8.6, pyannote-audio 4.0.7, transitive torchvision
  0.23.0, and transitive TorchCodec 0.7.0. No WhisperX transitive was promoted to a
  direct declaration.
- Removed the root/core `fe` extra and sqlite-vec from the lock; corrected the false
  sqlite-vec ANN documentation. Added the missing root normalization-extra forwarder
  so all required extra combinations are addressable.
- The released `bezier` package rejected Python 3.13. With explicit owner approval,
  replaced its one live curve call with an in-repo de Casteljau evaluator and removed
  the dependency. Known linear/quadratic/cubic, endpoint, clamp, ordering, shape, type,
  and invalid-input coverage is red-first. An external 3.12 parity check against the
  old package matched 18/18 samples within `2e-16` without committing generated data.
- Migrated the dormant P3-T4 probe fixture's frozen interpreter identity from 3.12.13
  to 3.13.15 so its fail-closed tests remain executable. This does not change the
  sealed owner ledger, reopen its exhausted cap, authorize a third request, or create
  live acceptance.

Owner runtime override and external-state closeout:

- Package resolution/sync is accepted without claiming WhisperX runtime audio
  readiness on the default FFmpeg 9. Stable WhisperX 3.8.6 resolves TorchCodec 0.7,
  whose supported FFmpeg range excludes FFmpeg 9; runtime audio execution is deferred.
- A superseded attempt briefly installed Homebrew's keg-only FFmpeg 7 without linking
  it. It was uninstalled after the override. Homebrew auto-removal also removed its
  Python 3.13 dependency, so validation was restored with uv-managed CPython 3.13.15.
  Default `ffmpeg` remains healthy at 9.0.1 (`ffmpeg` formula 9.0.1_1); no downgrade or
  relink occurred.
- No audio, model, provider, xLights, or other live application action occurred.

Fresh author evidence on uv-managed CPython 3.13.15:

- `uv sync --locked --extra dev --extra ml --all-packages`: pass, 192-package lock / 165
  installed packages.
- Locked dry-run metadata resolution: `ml`, `ml+stems`, `ml+mir-beats`, and
  `ml+normalization` all pass.
- Installed metadata exactly matches torch/torchaudio 2.8.0, torchvision 0.23.0,
  TorchCodec 0.7.0, WhisperX 3.8.6, and pyannote-audio 4.0.7.
- Focused platform/deletion/curve/WhisperX/probe regressions: pass; P3-T4 identity lane
  alone is 54 passed after the interpreter-fixture migration.
- Full suite: **5,453 passed, 38 skipped**, 88% coverage. The warnings are pre-existing
  third-party syntax, resource-lifecycle, and deprecation warnings; no failure is
  carried.
- Ruff format/check clean, mypy clean across **738 source files**, and
  `git diff --check` clean.
- `make validate` itself refuses any dirty worktree before running because it mutates
  formatting/lint state. The same four constituent gates were run explicitly on this
  deliberately uncommitted review freeze; the orchestrator must rerun `make validate`
  from the committed integration candidate.

### Frozen implementation/test manifest

This 20-entry manifest is the sole detailed implementation boundary. Deleted entries
are hashed as the literal `DELETED`; present entries contribute their SHA-256 line:

```text
.github/workflows/ci.yml
packages/twinklr/cli/pyproject.toml
packages/twinklr/core/api/http/auth.py
packages/twinklr/core/audio/lyrics/diarization.py (DELETED)
packages/twinklr/core/audio/lyrics/diarization_models.py (DELETED)
packages/twinklr/core/audio/lyrics/whisperx_service.py
packages/twinklr/core/audio/models/__init__.py
packages/twinklr/core/audio/models/lyrics.py
packages/twinklr/core/config/models.py
packages/twinklr/core/curves/functions/parametric.py
packages/twinklr/core/pyproject.toml
pyproject.toml
tests/fixtures/p3_t4_macro_probe/context.json
tests/unit/audio/lyrics/test_diarization_models.py (DELETED)
tests/unit/audio/lyrics/test_diarization_service.py (DELETED)
tests/unit/audio/test_stems_dependencies.py
tests/unit/config/test_audio_enhancement_config.py
tests/unit/curves/functions/test_parametric.py
uv.lock
tests/unit/test_p4_t1_contract.py
```

Manifest SHA-256:
`e5e4ba3a613af01707745957e2f5673d91bcd82680a935775f253136c1ca434c`.
The reproducible recipe, run from the worktree root with the entries above in order, is:

```bash
for file in "${files[@]}"; do
  printf '%s\n' "$file"
  if [ -f "$file" ]; then shasum -a 256 "$file"; else printf 'DELETED\n'; fi
done | shasum -a 256
```
