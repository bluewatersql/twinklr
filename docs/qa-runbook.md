---
title: "Twinklr QA Runbook"
description: "Step-by-step procedure to validate a Twinklr build end-to-end and decide human-QA readiness."
updated: 2026-08-30
---

# Twinklr QA Runbook

A step-by-step procedure for validating a Twinklr build: from the automated safety net,
through a bounded live end-to-end show, to the human checks that only a person can make in
the xLights GUI. It also states explicitly **what is automated-covered** versus **what still
needs human eyes**.

This runbook was validated on 2026-08-30 against the post-refactor engine
(see [changes/post-refactor-validation](../changes/post-refactor-validation/spec.md)).

---

## 0. Coverage map — automated vs. human

| Concern | Automated? | Where |
|---|---|---|
| Unit/integration correctness | ✅ `make validate` (5,600+ tests, ruff, mypy) | `tests/` |
| Deterministic `.xsq` sophistication (MH) | ✅ replay-render parity vs pinned baseline | `tests/regression/test_xsq_parity.py` |
| Deterministic `.xsq` sophistication (display) | ✅ hermetic replay of resolvable plan subset | `tests/regression/test_xsq_parity.py` |
| Provider parameter/contract shape | ✅ capability policy + cache-key tests | `tests/unit/agents/...` |
| Live LLM planning produces a valid, rich `.xsq` | ⚠️ proven once (MH); rerun per release | this runbook, §3 |
| Creative taste / musicality | ❌ human | §6 |
| xLights GUI import + on-model playback | ❌ human | §5–§6 |
| Vision calibration ranking | ❌ human (owner-gated) | `docs/vision-evaluation.md` |

**Rule:** merged tooling and green offline tests are **necessary but not sufficient**. A
release is human-QA-ready only after §1–§4 pass and a person completes §5–§6.

---

## 1. Prerequisites

```bash
# Toolchain + deps (uv-managed venv)
uv sync --extra dev --extra anthropic --all-packages

# Secrets/config: a local .env supplies provider + service tokens (never committed)
#   OPENAI_API_KEY=...            # required for live runs
#   OPENAI_MODEL=gpt-5.2          # or another model in your key's catalog
#   GENIUS_ACCESS_TOKEN=...       # optional (lyrics)
#   HF_TOKEN=...                  # optional
```

- **App config is optional.** With no `config.json`, the loader uses defaults
  (`llm_provider=openai`, per-stage `gpt-5.6-*` reasoning models) and reads
  `OPENAI_API_KEY` from the environment.
- **Proxied / MITM-TLS machines:** the OpenAI SDK uses `certifi`, which will not trust a
  corporate TLS-intercepting proxy (symptom: `CERTIFICATE_VERIFY_FAILED` even though `curl`
  works). Point Python at a CA bundle that includes the proxy root, e.g.:

  ```bash
  # Build a bundle from the macOS keychains + certifi, then export it for the run
  CERTIFI=$(uv run --frozen python -c "import certifi;print(certifi.where())")
  cat "$CERTIFI" > ca-bundle.pem
  security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> ca-bundle.pem
  security find-certificate -a -p /Library/Keychains/System.keychain >> ca-bundle.pem
  export SSL_CERT_FILE="$PWD/ca-bundle.pem" REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
  ```

---

## 2. Automated safety net (no cost, run first)

```bash
# Full gate: format check + lint + type-check + tests + coverage
make validate

# Just the regression harnesses, fast: display .xsq parity and the moving-head output pins
uv run --frozen pytest tests/regression -q
```

Expected: `make validate` green (0 lint, 0 mypy errors, tests pass ≥65% coverage). The
display harness pins the pre-refactor baseline and replays its plan through the current
renderer, so any drop in emission sophistication (effect volume, effect-type vocabulary,
value-curve density, layer depth) fails the gate. The moving-head pins fix the render
fingerprint and encoded frames of every catalog family and of one delivered `.xsq`, so
any unintended moving-head output change fails it.

---

## 3. Live end-to-end show (bounded, costs money)

> Set a per-run and total USD budget before starting. One MH show is typically ~$1–2.

### 3a. Validate the rig/job config against the current schema

Config files drift as the schema evolves. Before spending, confirm they load; if a legacy
field is rejected (`"... were removed because ..."` / `schema_version` mismatch), strip the
offending fields into a scratch copy rather than editing the originals:

```bash
uv run --frozen python - <<'PY'
from twinklr.core.config.loader import load_fixture_group, load_job_config
load_fixture_group("fixture_config.json")   # raises on stale fixture fields
load_job_config("job_config.json")          # raises on stale job fields / schema_version
print("configs OK")
PY
```

### 3b. Run the moving-head pipeline

```bash
uv run --frozen twinklr run \
  --audio "data/music/<song>.mp3" \
  --config <job_config>.json \
  --out artifacts/qa-run/<song>
```

Expected console tail: `Overall Success: ✅`, `Stages Completed: 7/7`, and an emitted
`*_twinklr_mh.xsq` plus `.xtiming`/`.xmap`/trace sidecars under `--out`.

### 3c. Run the display pipeline (optional; needs a layout)

```bash
uv run --frozen twinklr display \
  --audio "data/music/<song>.mp3" \
  --layout /path/to/xlights_rgbeffects.xml \
  --config <job_config>.json \
  --out artifacts/qa-run/<song>-display
```

> **Caveat:** display recipes live in a catalog that evolves. A plan generated against an
> older catalog may reference retired recipe ids and fail to render. Regenerate the plan
> against the current catalog, or render only the resolvable subset (see the display
> regression test for the pattern).

---

## 4. Verify output sophistication

There is no moving-head metrics baseline. A moving-head `.xsq` holds constant DMX
effects, one per run of identical 20 ms frames, not value curves, so effect counts and
curve density say little about it; its trace (`.xsq.trace.json`) and `twinklr eval-report`
describe what it rendered, and the pins in §8 catch unintended output change.

---

## 5. Import into xLights (human)

1. Open your xLights show folder and import the emitted `.xsq` (and `.xtiming` tracks).
2. Confirm models/groups resolve to your layout (use the `.xmap` hint).
3. Render/preview and watch on-model playback.

> Twinklr never saves your sequence and only writes reserved layers for `inject`/`regenerate`.
> Do QA against an **expendable** copy of your show.

---

## 6. Human-QA checklist (only a person can judge)

- [ ] **Musicality** — do accents/energy changes land on the beat and section boundaries?
- [ ] **Creative taste** — is the choreography coherent and on-theme, not just valid?
- [ ] **Color/palette** — do palettes read correctly on your physical models?
- [ ] **Moving-head motion** — smooth, in-range, no clipping/whip artifacts?
- [ ] **Transitions** — section changes feel intentional (no dead or jarring cuts)?

Moving-head colour, intensity and section transitions are not planner-driven yet (see §7):
judge them as the templates author them, not as a reading of the song.
- [ ] **Layout coverage** — all intended groups animated; nothing dark that shouldn't be?
- [ ] **Import cleanliness** — no unresolved models, no clobbered user layers.
- [ ] **(Owner-gated)** vision calibration ranking, if running the evaluation harness.

Record intended vs. unintended differences from prior shows; unintended regressions block
release.

---

## 7. Known constraints & caveats

- **Python 3.13 only.** WhisperX / TorchCodec runtime is deferred under FFmpeg 9.
- **Reasoning-model latency:** per-agent timeout defaults to 300 s; high-effort GPT-5
  reasoning calls can take >60 s.
- **`temperature` is stripped for the GPT-5 reasoning line** (mutually exclusive with a
  reasoning effort); non-reasoning models (gpt-4.1/gpt-4o) keep it.
- **Display catalog drift:** plans are bound to the recipe catalog at generation time.
- **Moving-head song intent is only partly rendered (known regression).** The renderer
  applies each section's template, preset and bars, its colour and gobo on heads whose
  wheel states are tagged, its intensity on the dimmer (adjusted under `twinklr
  show` by the heads' focal role), and its timed events with the lyric moment cues they
  land on; the planner's section transitions, motif variation and density are ignored
  until the song-intent work lands
  ([plan](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)).
- **Owner-local inputs** (audio, layout, `config.json`/`fixture_config.json`/`job_config.json`,
  `.env`, local `data/templates/` overlay) are gitignored and not part of CI.

---

## 8. Regression baselines (what is pinned)

| Baseline | Kind | Pinned in |
|---|---|---|
| Moving-head output | Render fingerprint and encoded-frame hashes of every catalog family, and one delivered `.xsq` | `tests/regression/test_mh_pins.py` |
| `02_rudolph` | Display `.xsq` metrics + hermetic replay parity | `tests/regression/baselines/02_rudolph*` |

Re-pin a baseline only with an explicit decision to move the go-forward reference.
