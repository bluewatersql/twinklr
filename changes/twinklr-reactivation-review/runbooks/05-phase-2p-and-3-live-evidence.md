---
type: change
status: active
area: engineering
created: 2026-11-01
updated: 2026-11-01
---

# Runbook 05 — Phase 2P and Phase 3 live evidence (non-GUI)

**Closes (when every section is run and recorded):** the live/empirical Phase 2P and
Phase 3 exit evidence that does **not** need a person at the xLights GUI.

| Section | Task | Exit gate it feeds |
|---|---|---|
| 2 | Baseline live end-to-end run | Input for §3 and §4; reproduces the post-refactor Phase 3 proof |
| 3 | [P2P-T6](../build/specs/phase-2p-creative-quality/P2P-T6-vision-judge-and-sync-metrics.md) | AC6 (calibration, N>=5) and AC7 (one song, <= $0.20) |
| 4 | [P2P-T13](../build/specs/phase-2p-creative-quality/P2P-T13-three-arm-comparison.md) | D1 verdict (three-arm comparison) |
| 5 | [P2P-T7](../build/specs/phase-2p-creative-quality/P2P-T7-stems-stage.md) | Real Demucs on Apple Silicon, MPS/CPU fallback observed |
| 6 | [P2P-T10](../build/specs/phase-2p-creative-quality/P2P-T10-model-retarget.md) and [P2P-T11](../build/specs/phase-2p-creative-quality/P2P-T11-structured-outputs.md) | Bounded live retarget and structured-output probes |
| 7 | [P3-T4](../build/specs/phase-3-show-convergence/P3-T4-macro-structured-contract.md) | Status and owner decision only. **No commands.** |
| 8 | All | Final evidence checklist |

**Not in this runbook** (sibling
[04-xlights-gui-and-human-acceptance](04-xlights-gui-and-human-acceptance.md)): P2P-T5
preview export, P2P-T12 live injection, P3-T6 and P3-T8 GUI checks, P1P-T12. Wherever a
step below needs an xLights-rendered preview video, it says "see runbook 04".

> **Rule inherited from the program:** merged tooling and green offline tests are not
> acceptance. Record no empirical outcome without its evidence file. An honest null or
> "failed safely" is a recordable result; a missing record is not.

---

## 0. Authorization and ordering

Every paid step below is run by the owner on the owner's machine. Running a command here
is the owner's own authorization for that step's stated cap and nothing more. The earlier
2026-08-29 authorization for `post-refactor-validation` covered that change only.

Order matters:

```text
§1 setup -> §2 baseline run -> §3.2 one-song proof -> §3.3 calibration (owner-accepted)
                                                        \-> §4 three-arm (T13)
§5 (T7) and §6 (T10/T11) are independent of the above and of each other.
§7 (P3-T4) is a decision, not a run.
```

- **T13 cannot start until T6 calibration is owner-accepted.** The runner validates the
  frozen calibration file, its SHA-256, the accepted decision and the rubric version
  before it calls `backend.analyze`, and fails loudly otherwise.
- Do the free checks in each section first. Paid commands come last in each section.

| Step | Cap (from its spec) | Where spend is recorded |
|---|---|---|
| §2 baseline MH run | No spec cap. Owner-set; the 2026-08 run cost about $1-2 (target <= $5/run) | LLM call logs under `data/logging` (see §1.3) |
| §3.2 T6 one song | <= $0.20, exactly 1 request | `vision_evaluation.json` (`visual.actual_cost_usd`, `visual.usage`) |
| §3.3 T6 calibration | <= $0.20/song, <= $2.00 per run; T6 task total <= $2.00 (exceeding it needs orchestrator sign-off) | each result JSON, plus the run's `VisionBudgetLedger` printout |
| §3.3 step 1 planning runs | >= 5 extra §2 runs at about $1-2 each (owner-set cap) | LLM call logs under `data/logging` |
| §4 T13 | Judging <= $0.20 x 5N (<= $8.00 at N=8); planning <= $25.00; **hard cap $40.00** | per-call records in results file and the partial-attempt journal (§4.6) |
| §5 T7 | No paid API | n/a |
| §6.1 T10 | <= 6 calls, <= $1.00 (spec). **No test exists, see §6.1** | n/a until a test exists |
| §6.2 T11 | probe: 1 request. strict suite: 8 requests, <= $1.50. T11 total <= $2.00 | owner notes (no ledger; see §6.2) |

Raising any cap needs a new written owner decision before the call, not after.

---

## 1. Common setup

### 1.1 Toolchain

```bash
cd /path/to/twinklr
uv sync --extra dev --all-packages
make validate                       # free; confirms the checkout is healthy
command -v ffmpeg && ffmpeg -version | head -1   # required by §3 and the T13 backend
```

### 1.2 Secrets and the environment

Twinklr does **not** auto-load `.env`. Export it into the shell you run from:

```bash
set -a; source .env; set +a         # needs OPENAI_API_KEY (public OpenAI key)
test -n "$OPENAI_API_KEY" && echo "key present"
```

The successful 2026-08 live run used a **public OpenAI key** whose catalog included the
`gpt-5.6-sol`, `gpt-5.6-terra` and `gpt-5.6-luna` models (the current role defaults).
Prove the key and network at zero cost before spending (a models list is free):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"      # expect 200 (401 = bad key)
```

**Behind a TLS-intercepting proxy** (symptom: `CERTIFICATE_VERIFY_FAILED` in Python while
`curl` works): build a CA bundle and export it. This is the same recipe as
[qa-runbook §1](../../../docs/qa-runbook.md):

```bash
CERTIFI=$(uv run --frozen python -c "import certifi;print(certifi.where())")
cat "$CERTIFI" > ~/.twinklr-ca-bundle.pem
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> ~/.twinklr-ca-bundle.pem
security find-certificate -a -p /Library/Keychains/System.keychain >> ~/.twinklr-ca-bundle.pem
export SSL_CERT_FILE="$HOME/.twinklr-ca-bundle.pem" REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
```

### 1.3 Config files (all gitignored, owner-local)

Field names below are checked against `packages/twinklr/core/config/models.py`.

| File | Needed keys | Notes |
|---|---|---|
| `config.json` (`--app-config`, optional) | `llm_provider` (default `openai`), `llm_base_url` (default `https://api.openai.com/v1`), `cache_dir`, `audio_processing.enhancements.stems.{enabled,model_name,vocal_presence_threshold}` | With no file the loader uses defaults and reads `OPENAI_API_KEY` from the environment. Removed top-level fields `output_dir` and `planning` are rejected. |
| `job_config.json` (`--config`) | `schema_version` must be `"3.0"`; `fixture_config_path`; `agent.max_iterations`, `agent.success_threshold` (0-100), `agent.{plan,judge,refinement,profile,lyrics}_agent.{model,reasoning_effort,temperature,max_tokens,timeout_seconds}`; `write_checkpoint` (keep `true`; §3 and `eval-report` need `checkpoints/plans/final.json`) | Removed fields rejected: `debug`, `include_notes_track`, `planner_features`, `assumptions`, `output_dir`, `pose_config`, `project_name`; inside `agent`: `vision_judge_agent`, `token_budget`, `enforce_token_budget`, `token_buffer_pct`, `recipe_generation_agent`. Agent `timeout_seconds` defaults to 300. |
| `fixture_config.json` | the owner's moving-head rig | The 2026-08 run found the owner's old copy rejected for removed fields `channel_count`, `dmx_start_address`, `dmx_universe`, `movement_speed` and nested `orientation.{resting_position,tilt_above_horizon_deg,tilt_up_dmx}`. Strip them into a scratch copy (see 1.4). |
| `xlights_rgbeffects.xml` | layout, only for `display`/`show` | Not needed for the MH-only paths in this runbook. |

LLM call logging is on by default: `agent.llm_logging.enabled=true`, written under
`agent.llm_logging.log_path` (default `data/logging`). Keep it on; it is the spend trail
for §2.

**Where to put owner artifacts**

| Artifact | Location |
|---|---|
| Audio | `data/music/<song>.mp3` (gitignored). Never redistribute or commit. |
| Rig | `fixture_config.json` at the repo root, or any path named by `job_config.json -> fixture_config_path` |
| Scratch outputs, previews, videos | `artifacts/` (gitignored). Videos and credentials never go in Git. |
| Committable evidence | `evaluations/<YYYY-MM-DD>-<slug>/` (see `evaluations/README.md`) |

### 1.4 Validate configs before spending (free)

```bash
uv run --frozen python - <<'PY'
from twinklr.core.config.loader import load_fixture_group, load_job_config
load_fixture_group("fixture_config.json")   # raises on stale fixture fields
load_job_config("job_config.json")          # raises on stale job fields / schema_version
print("configs OK")
PY
```

A rejection names the offending fields. Copy the file to `artifacts/live-validation/` and
delete only those fields there; do not hand-edit the originals. Re-run until it prints
`configs OK`. Schema errors surface before any spend.

---

## 2. Baseline live end-to-end run (audio -> plan -> render -> .xsq)

Reproduces the post-refactor live moving-head run
([live-run-prereqs.md](../../post-refactor-validation/notes/live-run-prereqs.md): PASS,
about 93k tokens, about $1-2, 396 placed effects vs the 262 baseline). The general
procedure and the human checks are in [qa-runbook §3-§6](../../../docs/qa-runbook.md);
this section only adds what the evidence runs need.

1. **Free gate** (qa-runbook §2):

   ```bash
   make validate
   uv run --frozen pytest tests/regression/test_xsq_parity.py -q --no-cov
   ```

2. **Run** (paid). The 2026-08 reference song was `data/music/11 - Need A Favor.mp3`, which
   is directly comparable to the pinned baseline. Any song works for §3-§4.

   ```bash
   uv run --frozen twinklr run \
     --audio "data/music/<song>.mp3" \
     --config job_config.json \
     --app-config config.json \
     --out artifacts/baseline/<song>
   ```

   Flags verified against `twinklr run --help`: `--audio` and `--config` are required;
   `--out` (default cwd), `--app-config` (default `config.json`), `--template-dir`,
   `--allow-template-overrides` and `--session-id` are optional. Omit `--app-config` if you
   have no `config.json`.
   Expected tail: `Overall Success`, `Stages Completed: 6/6`, an emitted
   `*_twinklr_mh.xsq`, plus `.xtiming`/`.xmap`/trace sidecars and
   `artifacts/baseline/<song>/checkpoints/plans/final.json`.

3. **Verify sophistication** against the pinned baseline (free):

   ```bash
   uv run --frozen python - <<'PY'
   import glob
   from tests.regression.xsq_metrics import extract_xsq_metrics
   path = glob.glob("artifacts/baseline/<song>/*_twinklr_mh.xsq")[0]
   print(extract_xsq_metrics(path).to_dict())
   PY
   ```

   Compare with `tests/regression/baselines/11_need_a_favor.metrics.json`. "On par" is
   defined in qa-runbook §4. Natural LLM variation is expected.

4. **Record:** copy the metrics output, the console tail, and the token and spend totals
   from `data/logging` into `evaluations/<date>-baseline-live-run/README.md` (inputs: song,
   rig, config hashes, commit SHA). Do not write `judgment.md` content on the owner's
   behalf; leave a `PENDING-OWNER` stub.

**Display/show variants** (`twinklr display`, `twinklr show`) need a layout and are in
qa-runbook §3c. Their live evidence is part of the §7 owner decision, not this baseline.

---

## 3. P2P-T6 — vision judge and sync metrics

**Authority:** [P2P-T6 spec](../build/specs/phase-2p-creative-quality/P2P-T6-vision-judge-and-sync-metrics.md),
[docs/vision-evaluation.md](../../../docs/vision-evaluation.md).
**Exit evidence:** AC7 (one song, <= $0.20) and AC6 (N>=5 owner-accepted, hash-pinned
blinded calibration). **Owner-decision-bearing:** rubric, criteria, calibration outcome,
per-song cost budget (§3.1).

### 3.1 Owner review (no tooling; do before spending)

The spec makes these owner decisions. Read and record accept/change in the evaluation
folder (§3.2 step 5):

- the four fixed categories (musicality-by-proxy, coordination, color/palette coherence,
  variety and pacing) and the criteria wording in
  `packages/twinklr/core/reporting/evaluation/prompts/vision_judge/system.j2` and
  `user.j2`. The category set is fixed; criteria wording is the owner's to refine. The
  rubric must contain no sync question (a unit test guards this).
- the cost budget: $0.20/song, $2.00/run, 1,500 images / 512 MiB request limits. The
  per-megapixel and token prices are configuration in `VisionJudgeConfig`
  (`vision_judge.py`) and **must be checked against the current provider price sheet
  first**; the defaults are not a price quote.
- the judge model: `get_vision_judge_agent_default()` in `config/models.py`
  (`gpt-5.6-luna`, low effort, temperature 0.2, `max_tokens` 3000, timeout 180 s). It is
  a fixed evaluation default, not a `job_config.json` role.

A rubric revision invalidates a prior calibration; calibrate against the final rubric.

### 3.2 One-song live proof (AC7)

1. **Free checks.**

   ```bash
   uv run pytest tests/unit -k "sync_metrics or rubric or vision_judge" -q --no-cov
   uv run pytest tests/local_only/test_vision_evaluation.py -q --no-cov -rs
   # second command must SKIP: "Set TWINKLR_RUN_LIVE_VISION_TESTS=1 ..."
   ```

2. **Inputs for one song.** From §2: the `*_twinklr_mh.xsq` and `final.json`. Plus a
   **preview video of that same xsq**, exported through the windowed xLights workflow
   (P2P-T5): **see runbook 04**. The harness never starts or drives xLights.

3. **Run** (paid; exactly one request; refuses an estimate above $0.20 before calling):

   ```bash
   TWINKLR_RUN_LIVE_VISION_TESTS=1 \
   TWINKLR_VISION_PREVIEW=/abs/path/preview.mp4 \
   TWINKLR_VISION_XSQ=/abs/path/show_twinklr_mh.xsq \
   TWINKLR_VISION_CHECKPOINT=/abs/path/checkpoints/plans/final.json \
   uv run pytest tests/local_only/test_vision_evaluation.py \
     -m local_only -k score_one_song -q --no-cov \
     --basetemp=artifacts/t6-proof
   ```

   The env vars and `-k score_one_song` are as in `docs/vision-evaluation.md` and
   `tests/local_only/test_vision_evaluation.py`. `--basetemp` is an addition: the test
   writes its result into pytest's `tmp_path`, so without it the JSON is discarded.
   Find it with `find artifacts/t6-proof -name vision_evaluation.json`.

4. **Pass criteria** (asserted by the test): `visual.actual_cost_usd <= 0.20`,
   `logical_request_count == 1`, `provider_attempt_cap == 1`,
   `calibration_status == "uncalibrated"`.
   If the provider rejects the `input_image` data-URL payload for the configured model,
   the single request fails. That is a recordable outcome (the open integration risk named
   in the T6 handoff). Do not retry in a loop; no fallback exists by design.

5. **Record:** copy `vision_evaluation.json` to
   `evaluations/<date>-p2p-t6-one-song-proof/` with a `README.md` (song, commit SHA,
   model, cost, prices used) and a `judgment.md` holding the §3.1 owner review, or a
   `PENDING-OWNER` stub. No videos or credentials in Git. Update `evaluations/INDEX.md`.

### 3.3 Blinded calibration, N >= 5 (AC6)

**No CLI exists for this.** The shipped pieces are Python APIs (`evaluate_preview`,
`CalibrationBatch`, `calculate_calibration`, `OwnerCalibrationArtifact`). The two small
scripts below wire them. They are owner-local scratch (keep in `artifacts/`, not the
repo). They were checked offline only: `score_shows.py` byte-compiles and imports;
`freeze_calibration.py` was run on synthetic data. **Neither has been run against a live
provider.**

**Independence rule:** the artifact SHA-256 and the preview SHA-256 must each be unique
across the five-plus samples. Use five distinct songs/shows, each with its own xsq and
its own preview. Re-exporting one show five times does not count. All shows in one batch
use the same rubric version and sampling config.

1. **Produce >= 5 shows.** Repeat §2 for >= 5 different songs. Export a preview for each
   (runbook 04). Cost reminder: the five judge calls are <= $1.00 total at the $0.20 cap.

2. **Blind the inputs.** Copy previews to opaque names, e.g.
   `artifacts/t6-cal/blind/Sequence-01.mp4` ... Keep the song-to-ID key in a separate file
   you do not open until step 6. Write `artifacts/t6-cal/shows.json`:

   ```json
   [
     {"id": "Sequence-01", "preview": "/abs/artifacts/t6-cal/blind/Sequence-01.mp4",
      "xsq": "/abs/path/a_twinklr_mh.xsq", "checkpoint": "/abs/path/a/checkpoints/plans/final.json"}
   ]
   ```

3. **Score** (paid; one request per show; run cap $2.00 via the default ledger). Save as
   `artifacts/t6-cal/score_shows.py`:

   ```python
   import asyncio, json, os, sys
   from pathlib import Path
   from twinklr.core.agents.async_runner import AsyncAgentRunner
   from twinklr.core.agents.providers.openai import OpenAIProvider
   from twinklr.core.config.models import get_vision_judge_agent_default
   from twinklr.core.reporting.evaluation.collect import extract_plan, load_checkpoint
   from twinklr.core.reporting.evaluation.sync_metrics import beat_grid_from_xsq
   from twinklr.core.reporting.evaluation.vision_evaluation import evaluate_preview
   from twinklr.core.reporting.evaluation.vision_judge import VisionBudgetLedger, VisionJudgeConfig

   shows = json.loads(Path(sys.argv[1]).read_text())
   out_root = Path(sys.argv[2])
   if os.environ.get("TWINKLR_RUN_LIVE_VISION_TESTS") != "1":
       sys.exit("set TWINKLR_RUN_LIVE_VISION_TESTS=1 to authorize paid judge calls")
   if len(shows) < 5:
       sys.exit("calibration needs at least 5 independent shows")

   async def main() -> None:
       config = VisionJudgeConfig()  # edit prices here from the current price sheet
       ledger = VisionBudgetLedger(config=config)
       provider = OpenAIProvider(api_key=os.environ["OPENAI_API_KEY"])
       runner = AsyncAgentRunner(
           provider, Path("packages/twinklr/core/reporting/evaluation").resolve()
       )
       for show in shows:
           plan = extract_plan(load_checkpoint(Path(show["checkpoint"])))
           result = await evaluate_preview(
               runner=runner,
               agent_config=get_vision_judge_agent_default(),
               preview_path=Path(show["preview"]),
               artifact_path=Path(show["xsq"]),
               plan=plan,
               beat_grid=beat_grid_from_xsq(Path(show["xsq"])),
               output_dir=out_root / show["id"],
               judge_config=config,
               ledger=ledger,
           )
           print(show["id"], f"cost=${result.visual.actual_cost_usd:.4f}", flush=True)
       print(f"run total actual=${ledger.actual_usd:.4f}")

   asyncio.run(main())
   ```

   ```bash
   TWINKLR_RUN_LIVE_VISION_TESTS=1 uv run --frozen python artifacts/t6-cal/score_shows.py \
     artifacts/t6-cal/shows.json artifacts/t6-cal/results
   ```

   Run from the repo root (the prompt path is resolved relative to it). **Do not open
   `artifacts/t6-cal/results/` yet.** Keep the console total as spend evidence.

4. **Owner ranks blind.** Without opening the results, any score, justification, model
   name, or the ID key: watch each full preview in a random order, rank 1..N (**1 = best,
   no ties**) and score the same four categories 0-10. Save
   `artifacts/t6-cal/owner.json` and treat it as frozen:

   ```json
   {"Sequence-01": {"rank": 3, "scores": {"musicality_by_proxy": 6, "coordination": 5,
                    "color_palette_coherence": 7, "variety_and_pacing": 4}}}
   ```

5. **Join and freeze.** Save as `artifacts/t6-cal/freeze_calibration.py`:

   ```python
   import json, sys
   from datetime import UTC, datetime
   from pathlib import Path
   from twinklr.core.reporting.evaluation.calibration import (
       CalibrationBatch, CalibrationEvidenceSample, HumanCategoryScores,
       OwnerCalibrationArtifact, calculate_calibration,
   )
   from twinklr.core.reporting.evaluation.vision_frames import FrameSamplerConfig
   from twinklr.core.reporting.evaluation.vision_judge import VisionRubricResponse

   results_dir, owner_file, identity, decision, out = sys.argv[1:6]
   owner = json.loads(Path(owner_file).read_text())
   samples, samplings, versions = [], [], set()
   for sequence_id, entry in owner.items():
       record = json.loads((Path(results_dir) / sequence_id / "vision_evaluation.json").read_text())
       samplings.append(FrameSamplerConfig.model_validate(record["sampling"]))
       versions.add(record["visual"]["rubric_version"])
       samples.append(CalibrationEvidenceSample(
           sequence_id=sequence_id,
           owner_rank=entry["rank"],
           owner_scores=HumanCategoryScores.model_validate(entry["scores"]),
           vision_scores=VisionRubricResponse.model_validate(record["visual"]["rubric"]),
           artifact_sha256=record["artifact_sha256"],
           preview_sha256=record["preview_sha256"],
           actual_cost_usd=record["visual"]["actual_cost_usd"],
       ))
   assert len(versions) == 1 and all(s == samplings[0] for s in samplings), "mixed rubric/sampling"
   report = calculate_calibration(CalibrationBatch(samples=list(samples)))
   print(report.model_dump_json(indent=2))   # read this, then decide
   artifact = OwnerCalibrationArtifact(
       recorded_at=datetime.now(UTC), owner_identity=identity, decision=decision,
       rubric_version=versions.pop(), sampling=samplings[0], samples=samples, report=report,
   )
   Path(out).write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
   OwnerCalibrationArtifact.model_validate_json(Path(out).read_text(encoding="utf-8"))
   print("wrote", out)
   ```

   `decision` is `accepted` or `rejected`. The code sets **no automatic threshold**: the
   owner reads Spearman, the permutation p-value and per-category mean absolute error, then
   chooses. Run it once with `rejected` or inspect the printed report first if undecided,
   but only an `accepted` file can authorize calibrated status and T13.

   ```bash
   uv run --frozen python artifacts/t6-cal/freeze_calibration.py \
     artifacts/t6-cal/results artifacts/t6-cal/owner.json "<owner name>" accepted \
     artifacts/t6-cal/calibration.json
   shasum -a 256 artifacts/t6-cal/calibration.json     # this is the pin T13 needs
   ```

6. **Review disagreements** frame by frame (now open the ID key and results). Do **not**
   tune the rubric on this batch and then report the same batch as validation; after a
   rubric revision, run a new blinded batch (§3.3 steps 1-5 again). A second batch can push
   T6 past its $2.00 task total, which needs orchestrator sign-off first (T6 spec).

7. **Record:** `evaluations/<date>-p2p-t6-calibration/` with `calibration.json`, its
   SHA-256, the per-show results (not the videos), the cost totals, and the owner's
   dated decision in `judgment.md`. Until this exists every result must stay
   `uncalibrated`. Update `evaluations/INDEX.md`.

---

## 4. P2P-T13 — three-arm comparison (D1)

**Authority:** [P2P-T13 spec](../build/specs/phase-2p-creative-quality/P2P-T13-three-arm-comparison.md)
(author handoff, "Exact LOCAL-ONLY owner protocol"). **Gate:** §3.3 accepted calibration.
**Caps:** judging <= $0.20 per sequence (<= $8.00 at N=8), planning <= $25.00, **whole task
<= $40.00 hard cap**. Exceeding any cap needs a new frozen manifest and orchestrator
sign-off.

> **Blocker, read first.** Step 4.3 requires an owner-local `module:callable` backend that
> implements `ExperimentBackend`. **The repo ships the runner, spend gate, blind-review and
> report code, but no backend implementation**, and none is described step-by-step in the
> spec beyond its wiring requirements. Steps 4.4 onward cannot run until that backend
> exists. Writing it is implementation work and needs its own task and review; this
> runbook does not supply it.

1. **Free preconditions.** Calibration accepted (§3.3). Offline suite green:

   ```bash
   uv run pytest tests/unit -k "selector or experiment or comparison" -q --no-cov
   ```

   The six code preconditions were verified at `8aeda12` (spec handoff). Any regression
   of one invalidates the experiment; re-run the focused tests above.

2. **Freeze the manifest** before any run. At least 8 songs, owner-local, hashed, with
   these composition flags satisfied across the set: >= 2 genres, >= 1 prominent-lyrics
   song, >= 1 instrumental, >= 1 non-4/4 or tempo-varying, >= 1 owner-familiar. Hash each
   audio file and the rig:

   ```bash
   shasum -a 256 data/music/*.mp3 fixture_config.json artifacts/t6-cal/calibration.json
   ```

   Write `/OWNER/LOCAL/p2p-t13-manifest.json`. The skeleton below validates against
   `ComparisonManifest` (checked offline with 8 songs; extend `songs` to your set):

   ```json
   {
     "experiment_id": "p2p-t13-001",
     "frozen_at": "2026-11-01T00:00:00Z",
     "songs": [
       {"song_id": "s1", "name": "...", "audio_path": "data/music/s1.mp3",
        "audio_sha256": "<64 hex>", "genres": ["pop"], "prominent_lyrics": true,
        "instrumental": false, "non_four_four_or_tempo_varying": false,
        "owner_familiar": false}
     ],
     "seed": 13,
     "macro_planner":       {"model": "gpt-5.6-sol", "reasoning_effort": "medium", "temperature": 0.7,
                             "pricing": {"pricing_id": "<sheet+date>", "prompt_per_million_usd": 0,
                                         "reasoning_per_million_usd": 0, "completion_per_million_usd": 0}},
     "moving_head_planner": {"model": "gpt-5.6-sol", "reasoning_effort": "high", "temperature": 0.7,
                             "pricing": {"...": "same shape"}},
     "vision_judge":        {"model": "gpt-5.6-luna", "reasoning_effort": "low", "temperature": 0.2,
                             "pricing": {"...": "same shape"}},
     "grid_source": "dsp",
     "stems_setting": "disabled",
     "fixture_config_path": "fixture_config.json",
     "fixture_config_sha256": "<64 hex>",
     "evaluation_harness_version": "<commit sha>",
     "calibration_record": "artifacts/t6-cal/calibration.json",
     "calibration_record_sha256": "<64 hex from §3.3 step 5>"
   }
   ```

   The pricing rates must be **positive** (the zeros above are placeholders; the model
   validator rejects them). Use the current provider price sheet. Model, effort and
   temperature values are the frozen per-role config; set them to what the backend will
   really use. `spend`, `arms`, `llm_runs_per_song` and `preconditions` take their
   defaults; do not override them. Also record the song list by name and hash in the
   decision record before the first run (spec AC3).

3. **Provide the backend** (blocker above): `owner_p2p_t13_backend:build_backend`, a
   callable taking the `ComparisonManifest` and returning an `ExperimentBackend`
   (`analyze(song)` and `execute(request)`). Requirements are in the spec handoff
   (use `request.include_macro` as the real stage-graph switch, pass
   `request.regeneration_nonce` to both planning caches, reuse the analysis snapshot, wrap
   every provider attempt in `request.spend_gate`, convert usage with
   `arm_call_records_from_iteration`, derive scores with `SequenceScore.from_vision`).
   Video export for each of the 5N sequences needs windowed xLights: **see runbook 04**.

4. **Run exactly 5N sequences** (paid; after explicit owner approval; `--owner-opt-in` is
   required):

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli run \
     --manifest /OWNER/LOCAL/p2p-t13-manifest.json \
     --backend-factory owner_p2p_t13_backend:build_backend \
     --results /OWNER/LOCAL/p2p-t13-results.json --owner-opt-in
   ```

   Flags verified against `three_arm_cli run --help`. The module must be importable: run from
   the repo root with `PYTHONPATH=/OWNER/LOCAL/backend-dir uv run ...` so `uv` still finds
   the project. Arms per song: A1
   (deterministic), B1/B2 (full LLM), C1/C2 (macro-ablated). Failed or partial attempts
   are journaled in `/OWNER/LOCAL/.p2p-t13-results.json.partial-attempts/` as each call
   settles; a stopped run keeps its exact spend there. Keep it.

5. **Stage the blind packet** (does not write the reveal key):

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli prepare-blind \
     --results /OWNER/LOCAL/p2p-t13-results.json --seed <FROZEN-SEED> \
     --output-dir /OWNER/LOCAL/p2p-t13-blind
   ```

   Use the manifest's `seed`. The packet holds one full five-arm song plus five randomly
   drawn sequences (expanded deterministically only as needed for five independent A-vs-B
   comparisons), under opaque `Sequence-NN-<hex>.mp4` names.

6. **Owner ranks blind.** Do not open the results file, source videos, logs, plan prose or
   any non-opaque filename. Watch the packet files, then save the ordered blind IDs as a
   JSON list of strings (`/OWNER/LOCAL/p2p-t13-blind/ordered-ids.json`) and persist:

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli record-ranking \
     --packet /OWNER/LOCAL/p2p-t13-blind/blind-review.json \
     --ordered-ids /OWNER/LOCAL/p2p-t13-blind/ordered-ids.json \
     --ranking /OWNER/LOCAL/p2p-t13-blind/ranking.json
   ```

   Optional `--notes` exists. The ranking must be on disk before the reveal key can be
   written.

7. **Finalize** (unblinds, revalidates calibration, applies the frozen parity criteria,
   writes the typed report):

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli finalize \
     --manifest /OWNER/LOCAL/p2p-t13-manifest.json \
     --results /OWNER/LOCAL/p2p-t13-results.json \
     --packet /OWNER/LOCAL/p2p-t13-blind/blind-review.json \
     --ranking /OWNER/LOCAL/p2p-t13-blind/ranking.json \
     --reveal /OWNER/LOCAL/p2p-t13-blind/reveal.json \
     --report /OWNER/LOCAL/p2p-t13-comparison.json
   ```

8. **Independent verification** (no tooling beyond the report's own validators; a separate
   reviewer/verifier, not the author of the run): check the 5N matrix, hashes and cache
   identities, call records and spend within $40.00, blind commitment and ranking
   timestamps, calibrated harness evidence, and the fixed parity computation. Only then
   does the owner read the verdict.

9. **Owner verdict and records.** The parity criteria are fixed in the spec (section 4) and
   must be applied **as written**; an `INCONCLUSIVE` or null verdict is valid and must be
   recorded as such. The owner then authorizes, as separate follow-up work (no tooling):
   - update D1 in `reviews/reactivation-proposal.md` with the outcome, quoting the D1
     standing-default sentence verbatim;
   - a decision record in `memories/decisions/` (provenance and date frontmatter, links to
     the change, `memories/INDEX.md` updated);
   - commit the report to `evaluations/<date>-p2p-t13-three-arm/` (it is the first
     comparative result);
   - the deterministic arm stays in the tree whatever the outcome.

---

## 5. P2P-T7 — real Demucs separation on Apple Silicon

**Authority:** [P2P-T7 spec](../build/specs/phase-2p-creative-quality/P2P-T7-stems-stage.md).
No paid API. **Hardware:** Apple Silicon only; Intel macOS is deliberately unsupported
(explicit full-mix fallback). `uname -m` should print `arm64`.

1. **Install the optional extra** (default installs omit Demucs and Torch on purpose):

   ```bash
   uv sync --extra dev --extra stems --all-packages
   uv run python -c "import demucs, torch; print(torch.backends.mps.is_available())"
   ```

   Expect `True` for MPS. If that sync cannot resolve, stop and report; do
   not bump torch (spec says that belongs to P4-T1).

2. **Free checks:**

   ```bash
   uv run pytest tests/unit/audio -q --no-cov
   uv run pytest tests/unit/audio/test_stems_stage.py -q --no-cov -rs   # real smoke must SKIP
   ```

3. **Real separation smoke.** First run downloads `htdemucs` weights, so network is needed
   once. Use a short song:

   ```bash
   TWINKLR_REAL_STEMS_AUDIO="/abs/path/short-song.mp3" \
   uv run pytest tests/unit/audio/test_stems_stage.py \
     -m local_only -k real_separation_smoke -q --no-cov -rs --durations=1
   ```

   The test is `test_real_separation_smoke` in `tests/unit/audio/test_stems_stage.py`. It
   asserts the `drums`, `bass`, `vocals`, `other` stems exist and that separation took
   under 1,200 s. The spec's runtime expectation is about 1-2 minutes on MPS (about 6
   minutes on CPU); record the actual `--durations` time.
   The spec's own command `-k separation` also works.

4. **Observe MPS vs CPU fallback.** The test only asserts stems and time. The adapter
   (`packages/twinklr/core/audio/stems.py`) uses Demucs's own device choice (CUDA, then
   MPS, then CPU) and, if MPS fails at runtime, retries once on CPU and appends the
   warning `Demucs MPS separation failed (...); retrying once on CPU` to the result's
   `warnings`. To see which happened, add `-o log_cli=true -o log_cli_level=WARNING` to the
   pytest command above and record whether that warning appears. A forced-failure check
   for the fallback path has no command in the spec; the fallback is covered by stubbed unit
   tests only.

5. **End to end with stems (optional, paid)** sets, in `config.json`,
   `{"audio_processing": {"enhancements": {"stems": {"enabled": true}}}}` and re-runs §2.
   Features then record whether stems or full-mix were used (`SongBundle.features.stems`).
   Twinklr and xLights 2026.11 may both separate the same audio; watch for duplicate
   storage.

6. **Record:** wall time, device (MPS or CPU), whether the fallback warning appeared,
   Demucs and torch versions
   (`uv run python -c "import importlib.metadata as m, torch; print(m.version('demucs'), torch.__version__)"`)
   in `changes/twinklr-reactivation-review/evidence/<date>-p2p-t7-demucs/README.md`. Durable lessons go to `memories/` only
   after review.

---

## 6. P2P-T10 and P2P-T11 — bounded live provider probes

### 6.1 P2P-T10 live smoke (one call per role): no test exists

The spec (AC / test 8) calls for `test_live_smoke_one_call_per_role` (<= 6 calls,
<= $1.00, run with `-k live_smoke`) and says it should also answer whether `gpt-5.6-*`
accepts `json_object` mode. **No such test is in the repo** (`grep` for `live_smoke` and
`one_call_per_role` finds nothing). Do not invent one here. Options for the owner:
(a) accept that the T11 probe and strict suite (§6.2) cover the structured-output
question and the model-reachability question per role, or (b) commission the missing test
as a separate task. The T10 retarget itself (config wiring, no hardcoded literals) is
offline-verified; free checks:

```bash
uv run pytest tests/unit/agents -q --no-cov
grep -rn 'gpt-5\.2\|gpt-5-mini\|gpt-4o-mini\|gpt-image-1\.5' packages/ scripts/   # spec's audit grep
```

### 6.2 P2P-T11 probe and strict-mode suite

**Authority:** [P2P-T11 spec](../build/specs/phase-2p-creative-quality/P2P-T11-structured-outputs.md)
("Owner-gated live evidence still pending"). **Budget:** probe 1 HTTP request; strict suite
exactly 8 requests, <= $1.50; task total <= $2.00. Provider retries and strict fallback
are disabled in the harness, so call counts are exact.

1. **Free check: both skip without the opt-in.**

   ```bash
   uv run pytest tests/local_only/test_openai_structured_outputs.py -q --no-cov -rs
   ```

2. **Probe: does `gpt-5.6-sol` accept `json_object`?** (1 request)

   ```bash
   TWINKLR_RUN_LIVE_LLM_TESTS=1 uv run pytest \
     tests/local_only/test_openai_structured_outputs.py \
     -m local_only -k json_object_probe -q --no-cov
   ```

   Pass means accepted (`structured_output_mode == "json_object"`). A failure is also an
   answer, but read the error: HTTP 400 naming `json_object` or the format is "rejected";
   a TLS, auth or timeout error is not an answer, so fix the environment and re-run.

3. **Strict-mode per agent role** (8 requests, one per shipped role/root):

   ```bash
   TWINKLR_RUN_LIVE_LLM_TESTS=1 uv run pytest \
     tests/local_only/test_openai_structured_outputs.py \
     -m local_only -k live_strict_mode_per_agent -q --no-cov
   ```

   Roles: audio_profile, lyrics, group_planner, holistic_corrector, holistic_judge,
   moving_head_planner, moving_head_judge, macro_planner. Each asserts
   `structured_output_mode == "json_schema"`; the moving-head judge arm asks the model to
   omit `score` and asserts strict mode kept it. Record any role that fails and the error;
   one failing role is a real finding, not noise.

4. **Spend log:** these tests have no cost ledger. Record the request counts above,
   the pytest output, and the usage figures from the provider dashboard for the time window.

5. **Record:** append the probe answer and per-role pass/fail to the T11 spec handoff
   section (owner's call to edit the spec) and
   `changes/twinklr-reactivation-review/evidence/<date>-p2p-t11-live-probes/README.md`. Promote the `json_object` answer to
   `memories/` only after the owner has run it.

---

## 7. P3-T4 — live macro acceptance (status and decision only)

**This section contains no commands, by design.**

**Status.** P3-T4's sealed owner ledger recorded two audited live attempts. Attempt 1 failed
safely. Attempt 2 failed with HTTP 400 unsupported `temperature` (one provider request, no
retry or repair, no usage). `$3.320000` is committed and the **two-attempt lifetime cap is
exhausted. No third attempt is authorized under any outcome.** Do not run, edit, move,
reset or re-seal anything in the canonical ledger under `~/.local/state/twinklr/owner-probes/`
or the P3-T4 probe harness (`macro_planner/live_probe.py` and its frozen fixtures).

The post-refactor change recorded the P3-T4 row as **"Superseded — Phase 3 does a fresh
live E2E under new authorization (does not reopen the sealed ledger)"**
([post-refactor-validation plan](../../post-refactor-validation/plan.md), carried
inventory). Both failure classes (`$ref` sibling schema, `temperature` on reasoning
models) are fixed in code and covered offline.

**Evidence that exists:**

- [live-run-prereqs.md](../../post-refactor-validation/notes/live-run-prereqs.md): live MH
  run on public OpenAI, PASS, with the two real bugs found and fixed
  (`capabilities.py` temperature policy, zero-duration segments); fixes
  `91677ab`, `9bd9461`, `a8ce12b`, `d15ee03`.
- [memories/learnings/live-provider-run-lessons.md](../../../memories/learnings/live-provider-run-lessons.md)
- [qa-runbook §3](../../../docs/qa-runbook.md) (the reproducible procedure; §2 above)
- [P3-T4 spec](../build/specs/phase-3-show-convergence/P3-T4-macro-structured-contract.md)
  amendment and attempt-2 sections (the sealed record)

**Caveat on that evidence.** It covers the moving-head `twinklr run` path with an
LLM macro/planning stage. It is not the P3-T4 macro probe, and no live `twinklr display` or
`twinklr show` run is recorded in it.

**Owner decision required** (record it in a dated decision, then update the HANDOFF
"Continuation order" accordingly):

1. **Accept** the post-refactor live MH run as the superseding live evidence for the
   macro-contract exit, formally closing the P3-T4 live item without any new spend; or
2. **Authorize something new**: e.g. a fresh, separately capped live `display` or `show`
   E2E under a new written authorization with its own budget and ledger. That needs a new
   spec or amendment first. **No tooling or command for it exists in this runbook** and none
   may touch the sealed P3-T4 ledger.

Until the owner chooses, the item stays open. Do not infer acceptance from the offline fix.

---

## 8. Final evidence checklist

Tick only when the file exists and is linked from the owning spec or change handoff.

- [ ] §2 baseline: metrics output, console tail, token and spend, commit SHA, config hashes
      in `evaluations/<date>-baseline-live-run/`
- [ ] §3.1 owner review of rubric, criteria, cost budget recorded
- [ ] §3.2 T6 one-song `vision_evaluation.json` (cost <= $0.20, 1 request) committed
- [ ] §3.3 `calibration.json` (decision accepted, N >= 5, distinct hashes) with its SHA-256
      and dated owner decision; results remain `uncalibrated` until this exists
- [ ] §4 backend written and reviewed (precondition)
- [ ] §4 frozen manifest (>= 8 songs, name and hash) committed or recorded before run 1
- [ ] §4 `p2p-t13-results.json`, partial-attempt journal, blind packet, `ranking.json`,
      `reveal.json`, `p2p-t13-comparison.json`; spend <= $40.00
- [ ] §4 independent verification note; owner verdict (incl. `INCONCLUSIVE` if so)
- [ ] §4 D1 update in the proposal, `memories/decisions/` record, `memories/INDEX.md`,
      committed evaluation result
- [ ] §5 T7: wall time, device, fallback warning (seen or not), versions
- [ ] §6.1 T10 live-smoke gap resolved (accepted as covered by §6.2, or test commissioned)
- [ ] §6.2 T11: probe answer, 8 per-role outcomes, request counts
- [ ] §7 P3-T4 owner decision (accept superseding evidence, or authorize new work)
- [ ] `changes/ACTIVE.md`, `evaluations/INDEX.md` and affected `memories/INDEX.md` updated
- [ ] `make validate` green on the commit used for all runs (fresh output)

After the evidence exists, the HANDOFF "Owner/local gates still pending" and phase exit
records are updated by the owner or a follow-up task; this runbook does not edit them.
