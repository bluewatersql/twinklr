---
type: change
status: active
area: engineering
created: 2026-11-01
updated: 2026-11-01
---

# Runbook 04 — xLights GUI, preview, and human-acceptance evidence

Owner-run, step-by-step procedure for every deferred xLights-GUI, preview-render, and
human-judgment exit in the reactivation campaign. The campaign deferred these "until a
meaningful, fully working end-to-end show exists"
([HANDOFF](../build/plan/HANDOFF.md), "Next-agent handoff" item 4). That milestone now
exists: the post-refactor-validation change produced a live moving-head (MH) show on
`11 - Need A Favor.mp3` that emitted a valid `.xsq`
([plan Phase 3](../../post-refactor-validation/plan.md),
[live-run-prereqs](../../post-refactor-validation/notes/live-run-prereqs.md)). Deferral
never waived these gates; merged tooling and green offline tests are not acceptance.

This runbook does **not** duplicate [docs/qa-runbook.md](../../../docs/qa-runbook.md)
(automated safety net, config validation, live-run command, `.xsq` metrics, generic
import/QA checklist) or [docs/vision-evaluation.md](../../../docs/vision-evaluation.md)
(cost controls, N>=5 owner calibration protocol). It links to them and covers only the
GUI/human steps they do not.

Specs are authority; where this file and a spec disagree, the spec wins:
[P1P-T12](../build/specs/phase-1p-render-truth/P1P-T12-xlights-acceptance-test.md),
[P1P-T11](../build/specs/phase-1p-render-truth/P1P-T11-delivery-v1-xtiming-fresh-xsq-xmap.md),
[P1P-T10](../build/specs/phase-1p-render-truth/P1P-T10-evaluation-writer-and-bridge.md),
[P2P-T5](../build/specs/phase-2p-creative-quality/P2P-T5-preview-render-client.md),
[P2P-T12](../build/specs/phase-2p-creative-quality/P2P-T12-live-injection-workflow-v1.md),
[P3-T6](../build/specs/phase-3-show-convergence/P3-T6-unified-export-core.md),
[P3-T8](../build/specs/phase-3-show-convergence/P3-T8-show-level-evaluation.md).

---

## What the xLights GUI work is

- **Does a real xLights accept what Twinklr emits? (P1P-T12)** A scripted suite imports
  Twinklr's `.xsq`, `.xtiming` and `.xmap` into a running xLights 2026.15 and checks it does
  not reject them, with and without `xlights_rgbeffects.xml` in the show folder. Only a real
  xLights can answer; no repository test can.
- **Does it open *and* look right? (P1P-T12, P3-T6)** "It imported" is not "it works". A
  person opens one imported effect in the xLights UI to confirm its settings were not
  silently dropped, saves the sequence, and diffs it against what Twinklr wrote. That diff
  is the only ground truth for what xLights really requires and whether it rewrites times
  or palettes.
- **Can we render a preview video? (P2P-T5)** Video export needs a *windowed* xLights
  (headless gives FSEQ only), so it can only run on your Mac. It produces the video that
  the vision judge and the human reviewer both look at.
- **Is live injection safe? (P2P-T12)** Twinklr can write effects straight into an open
  sequence. We prove it on a throwaway scratch sequence only, never on a show you care
  about, then discard the result.
- **Is the show any good? (P1P-T10 judgment, P3-T8)** Taste, musicality and
  cross-part coordination are human judgments; a vision model scores the same frames, and
  the two are recorded side by side as the first calibration data point. Nobody, including
  an agent, may fill these in for you.
- **Two safety facts.** xLights' automation API has no authentication (any local process can
  drive xLights while it is on), and some steps spend money on LLM/vision calls. This runbook
  flags both on every step that matters.

---

## Step index and cost summary

| # | Step | Exit evidence | GUI | Paid calls |
|---|---|---|---|---|
| 0 | Generate / locate the end-to-end show | prerequisite | no | **Yes if regenerated** (~$1-2 per MH run) |
| 1.1 | Human judgment of golden fixture | P1P-T10 `judgment.md` | yes (watch) | no |
| 1.2 | Acceptance suite, mode `with_rgbeffects` | P1P-T12 | yes | no |
| 1.3 | Acceptance suite, mode `bare` | P1P-T12 | yes | no |
| 1.4 | Parameter inspection, save, diff, ground-truth fixture | P1P-T12 | yes | no |
| 1.5 | Delivery import check on the real show | P1P-T11 (via T12) | yes | no |
| 2.1 | Preview video export | P2P-T5 | yes (windowed) | no |
| 2.2 | Live injection round trip, scratch sequence | P2P-T12 | yes | no |
| 2.3 | Optional CLI `inject` / `regenerate` on scratch | P2P-T12 manual validation | yes | **Yes** (cap below) |
| 3.1 | Palette index 0 + quantization save-and-diff | P3-T6 | yes | no |
| 3.2 | Seeding check | P3-T6 | n/a | superseded, see step |
| 3.3 | One-song vision proof on the MH show: **run once, in runbook 05 §3.2** | P2P-T6 (feeds P3-T8) | no (uses 2.1 video) | **Yes**, hard cap $0.20 |
| 3.4 | Combined-show evaluation + human judgment | P3-T8 | yes | **Yes**, ~$0.15, hard cap $1.00; combined show itself blocked, see step |

Nothing in this runbook authorizes spend beyond the caps shown. Re-confirm each cap in the
owning spec before running.

---

## One-time setup

### S1. Safety rules (read first)

1. **Never point any of this at your real show folder or a sequence you care about.**
   Use a copied, expendable show folder (S3) and scratch sequences only.
2. The xLights automation API is **unauthenticated**. Enable it only while a step needs it,
   run on a trusted machine, and disable it when done (S2, Teardown).
3. Twinklr never saves your sequence. Anything you save from xLights you save yourself,
   into the scratch show folder.
4. Close xLights sequences **without saving** after each run unless the step says to save.
5. Do not commit preview videos, API keys, or the scratch show folder. Evidence that is
   committed is small text (records, diffs, the saved `.xsq` fixture).

### S2. xLights version and the HTTP automation API

- Install **xLights 2026.15** (the version the specs and tests target) as a *windowed*
  app. Record the exact build string from xLights itself (Help > About), not from docs.
- Enable the HTTP automation API in xLights preferences. `tests/golden/README.md`
  ("xLights acceptance (P1P-T12)") says Tools > Preferences, local interface only; the exact
  checkbox label is not recorded in the repo, so look for the automation/xFade HTTP option.
  Default port is **49913** (49914 is the second-instance port).
- The golden acceptance suite probes **only** `http://127.0.0.1:49913` and has no env var to
  change it (`tests/golden/xlights_client.py`, `DEFAULT_BASE_URL`). The newer
  `XLightsAutomationClient` (used by steps 2.1-2.3) tries 49913 then 49914. Run only one
  xLights instance.
- Reachability probe (read-only; the same `getVersion` call the suite uses at collection):

  ```bash
  curl -s -X POST http://127.0.0.1:49913/xlDoAutomation -d '{"cmd":"getVersion"}'
  ```

  Paste the response into the evidence record; it is the authoritative build string for
  the P1P-T12 run record.

### S3. Expendable show folders

Create two **copies** (never your live show). Pick a scratch root, e.g.
`export XL_SCRATCH="$HOME/xlights-scratch"`.

| Folder | Must contain | Used by |
|---|---|---|
| `$XL_SCRATCH/show-with-rgbeffects` | a copied `xlights_rgbeffects.xml` (and `xlights_networks.xml`) | mode `with_rgbeffects`, scratch sequences, preview, injection |
| `$XL_SCRATCH/show-bare` | **no** `xlights_rgbeffects.xml` | mode `bare` |

Required layout content (from `tests/golden/harness.py`): the four golden-rig DMX moving
heads must exist as models named exactly **`Dmx MH1`, `Dmx MH2`, `Dmx MH3`, `Dmx MH4`**
in `show-with-rgbeffects`. For the real-show steps (0, 1.5, 2.1-3.1) the models named in
the show's `fixture_config.json` must also exist (the live run used the owner's real 4-MH
rig names). Add a model named `Yard Arches` (any type) for step 3.1.

Switch xLights between the two folders with its show-folder selector (File menu; label per
xLights convention, not recorded in the repo), then **restart/confirm** which folder is
open. The API has no "open show folder" command, which is why mode must be declared by env
var (step 1.2/1.3).

Verify before each mode run:

```bash
ls "$XL_SCRATCH/show-with-rgbeffects/xlights_rgbeffects.xml"   # must exist for with_rgbeffects
ls "$XL_SCRATCH/show-bare/xlights_rgbeffects.xml"              # must be absent for bare
```

Caveat: xLights may create `xlights_rgbeffects.xml` itself when it opens or exits an empty
folder. Re-run the second `ls` *after* opening the bare folder in xLights; if the file has
appeared, the "bare" arm is not bare. Note this in the evidence record (open decision D3).

### S4. Environment

Run all commands from the repo root. Use `uv run --frozen` (plain `uv run` rebuilds the
workspace and can take minutes).

```bash
cd /Users/ondeck/work/github/twinklr
uv sync --extra dev --all-packages      # once; same as docs/qa-runbook.md section 1
```

Env vars the tests read (verified in source):

| Variable | Read by | Meaning |
|---|---|---|
| `TWINKLR_XLIGHTS_SHOWDIR_MODE` | `tests/golden/test_xlights_acceptance.py` | `with_rgbeffects` or `bare`; gates the two Q1 arms (any other value skips both) |
| `TWINKLR_XLIGHTS_PREVIEW_SEQUENCE` | `tests/golden/test_preview_render_local.py` | absolute path of the `.xsq` to preview; no default (skips if unset) |
| `TWINKLR_RUN_LIVE_XLIGHTS_INJECTION` | `tests/local_only/test_live_injection.py` | must be exactly `1` |
| `TWINKLR_XLIGHTS_SCRATCH_SEQUENCE` | same | absolute path of the already-open scratch `.xsq`; test refuses to mutate any other open sequence |
| `TWINKLR_XLIGHTS_SCRATCH_MODEL` | same | exact model name to inject into (spec example: `Dmx MH1`) |
| `TWINKLR_RUN_LIVE_VISION_TESTS` | `tests/local_only/test_vision_evaluation.py` | must be exactly `1` (paid) |
| `OPENAI_API_KEY` | same, and all `twinklr run/inject` | provider key |
| `TWINKLR_VISION_PREVIEW` / `TWINKLR_VISION_XSQ` / `TWINKLR_VISION_CHECKPOINT` | same | absolute paths: preview video, the show's `.xsq`, `checkpoints/plans/final.json` |

Behind a TLS-intercepting proxy, build and export `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` per
[docs/qa-runbook.md](../../../docs/qa-runbook.md) section 1 before any paid step.

Pytest markers (from `pyproject.toml`): `requires_xlights` (golden suite; auto-skips
when port 49913 is unreachable) and `local_only` (owner-invoked; never CI). Default
`pytest` runs deselect nothing by marker, but each test self-skips without its env vars.

Optional sanity check that everything skips safely with xLights **off** (no live calls):

```bash
uv run --frozen pytest tests/golden/test_xlights_acceptance.py tests/golden/test_preview_render_local.py tests/local_only/test_live_injection.py -q -rs
```

Expected: every test reported skipped with a reason.

---

## Step 0 — Generate or locate the end-to-end show

**Paid if regenerated.** Prefer locating the existing run.

0a. Locate (the 2026-08-29 run's outputs are under the owner's gitignored `artifacts/`,
which is absent from a fresh checkout):

```bash
find ~ -name '*_twinklr_mh.xsq' -path '*11*Need*' 2>/dev/null
```

Each `twinklr run` writes `--out/<song_name>/` containing `<song_name>_twinklr_mh.xsq`, one
`.xtiming` per timing track, a `.xmap`, a trace sidecar, and (when `write_checkpoint` is
true, its default) `checkpoints/plans/final.json`.

0b. Regenerate only if 0a finds nothing or the show predates the P3-T6 emission core
(integrated 2026-08-26; the 2026-08-29 run postdates it). Cost ~$1-2 per
[docs/qa-runbook.md](../../../docs/qa-runbook.md) section 3, which has the prerequisite
config validation and the exact command:

```bash
uv run --frozen twinklr run \
  --audio "data/music/11 - Need A Favor.mp3" \
  --config <job_config.live>.json \
  --out artifacts/qa-run
```

Verify: console tail shows success, and the `.xsq` exists. Set for later steps:

```bash
export SHOW_DIR="<absolute path to .../11 - Need A Favor or equivalent output dir>"
export SHOW_XSQ="$(ls "$SHOW_DIR"/*_twinklr_mh.xsq | head -1)"
export SHOW_CHECKPOINT="$SHOW_DIR/checkpoints/plans/final.json"
ls "$SHOW_XSQ" "$SHOW_CHECKPOINT" "$SHOW_DIR"/*.xtiming "$SHOW_DIR"/*.xmap
```

Copy the show to the scratch folder so nothing writes back into artifacts, then point the
variables at the copy:

```bash
cp -R "$SHOW_DIR" "$XL_SCRATCH/show-under-test"
export SHOW_DIR="$XL_SCRATCH/show-under-test"
export SHOW_XSQ="$(ls "$SHOW_DIR"/*_twinklr_mh.xsq | head -1)"
export SHOW_CHECKPOINT="$SHOW_DIR/checkpoints/plans/final.json"
```

---

## Phase 1P

### 1.1 Human judgment of the golden fixture (P1P-T10)

Target: `evaluations/2026-08-13-golden-fixture-mh4-minimal/judgment.md`
(status: PENDING-OWNER). Only a person may fill it. No paid calls.

1. Open the scratch show `show-with-rgbeffects` (models `Dmx MH1`-`MH4` present).
2. New scratch sequence; import effects from
   `evaluations/2026-08-13-golden-fixture-mh4-minimal/rendered.xsq` (xLights effect-import
   dialog, map `Dmx MH1`-`MH4` by name; or use the automation import in step 1.2 first).
3. Read `evaluations/2026-08-13-golden-fixture-mh4-minimal/report.md` and `README.md`.
   Note: this fixture used a synthetic click/tone audio, not a song, and `rendered.xsq`
   carries the older `2024.10` version stamp.
4. Watch/inspect the moving-head choreography.
5. Fill the Record block in `judgment.md`: what was watched, judgment, overall score 0-10,
   date, reviewer. Replace the PENDING-OWNER banner only once genuinely done. Per the
   P1P-T10 spec, also note in the record which fixes were in the tree for the artifact's
   commit (`92af8895767aaa9bd70dbec07400d541e8c27023`) so it is interpretable later.
6. Update the Judgment column for that row in `evaluations/INDEX.md`.

Decision D1: judge this synthetic/stale artifact as-is, or regenerate a golden render at
current HEAD, or judge the real-song MH show from Step 0 and record that (the evaluations
README says the project may prefer the real-song run). The spec authorizes exactly one
real-song paid run for P1P-T10 and it is the owner's call.

### 1.2 P1P-T12 acceptance suite, mode `with_rgbeffects`

No paid calls. Spec: seven tests covering Q1 (import with/without rgbeffects), Q2
(version stamp, current and synthetic `1999.99`), Q3 (shutter, rig
`mh4_shutter_out_of_window`, channel 17), Q4 (`split_lr_sweep_counter` overlap clamp), and
`.xtiming` standalone import with marker times checked against the beat grid.

1. In xLights open `$XL_SCRATCH/show-with-rgbeffects`. Confirm `Dmx MH1`-`MH4` exist.
2. Enable the automation API (S2). Probe with `getVersion` (S2); save the output.
3. Run, retaining the generated files (pytest's `--basetemp` keeps the tmp dirs so the
   generated `.xsq`/`.xmap`/`.xtiming` can be diffed in step 1.4):

   ```bash
   TWINKLR_XLIGHTS_SHOWDIR_MODE=with_rgbeffects \
     uv run --frozen pytest tests/golden/test_xlights_acceptance.py -v -rs \
     --basetemp "$XL_SCRATCH/acc-basetemp-with"
   ```

   The suite calls `newSequence` before every test, so each import lands in a throwaway
   sequence; it never saves. It does **not** use an env var for the port.
4. Expected: the `bare` Q1 arm skips with a reason naming the required mode; the other
   six tests run. Record pass/fail per test and, for any failure, the exact xLights
   response text (`response.body` is in the assertion message).
5. Known fragility (from the test source): the success check `_assert_import_succeeded`
   fails on any response containing the substrings "error" or "fail", and the response
   shape for `importXLightsSequence` is documented in the code as unverified against a real
   xLights. A failure whose body is actually benign (for example a field named
   `errors: 0`) is a test-assertion issue, not an xLights rejection: record the raw body
   and route to a follow-up rather than editing the test on the spot (spec: do not "fix"
   findings in this task).
6. In xLights close the throwaway sequence **without saving**.

### 1.3 P1P-T12 acceptance suite, mode `bare`

1. Quit xLights fully. Open `$XL_SCRATCH/show-bare` (no `xlights_rgbeffects.xml`). Re-check
   the file is still absent (S3 caveat). Re-enable the API if it reset.
2. Run:

   ```bash
   TWINKLR_XLIGHTS_SHOWDIR_MODE=bare \
     uv run --frozen pytest tests/golden/test_xlights_acceptance.py -v -rs \
     --basetemp "$XL_SCRATCH/acc-basetemp-bare"
   ```

3. Expected: the `with_rgbeffects` arm skips; everything else runs. The owner confirmed on
   2026-08-14 that a bare `.xsq` imports; this run pins that result. A failure is **not** a
   reason to revert the generate-fresh contract (spec P1P-T12, "Effort & risk"); record it
   and route to a follow-up.
4. Close the throwaway sequence without saving.

Record for both runs: xLights build string, `git rev-parse HEAD`, rigs used
(`mh4_minimal`, `mh4_shutter_out_of_window`), date, per-test outcome.

### 1.4 Parameter inspection, save, diff, ground-truth fixture (manual, required by P1P-T12)

Spec P5 section V4 risk 5: silently ignored `E_*` keys look like success at load time, so
this manual inspection is a required acceptance criterion. It is not scriptable
(the automation surface used here has no "get effect parameters" command in the golden
client).

Use the retained baseline file (path pattern from the fixtures; confirm with `ls`):

```bash
ls "$XL_SCRATCH"/acc-basetemp-with/xlights_acceptance_baseline*/
```

1. In `show-with-rgbeffects`, create a new sequence (Media/Animation; frame 20 ms) and
   import effects from `baseline.xsq` with mapping file `baseline.xmap`
   (effect-import dialog; menu labels per xLights convention).
2. Click any one DMX effect on `Dmx MH1`, open its settings, and compare each visible DMX
   slider/value-curve against the settings string in the generated file:
   `grep -m1 'E_SLIDER_DMX' "$XL_SCRATCH"/acc-basetemp-with/xlights_acceptance_baseline*/baseline.xsq`.
   Write down any key present in the file but absent or zero in the UI.
3. Q3 shutter check: in the same way import the `shutter_high*` delivery
   (`xlights_acceptance_shutter_high*/shutter_high.xsq`). The file must contain
   `E_SLIDER_DMX17=255`; confirm channel 17 reads 255 in the effect UI (and on a connected
   fixture if you have one). Record the evidence used.
4. Q4: import `overlap.xsq`; confirm no overlapping-effects warning and that effects
   appear sequentially on one layer.
5. Save the sequence from xLights into the scratch show folder (File > Save As), then:

   ```bash
   diff <(xmllint --format "$XL_SCRATCH/acc-basetemp-with/xlights_acceptance_baseline0/baseline.xsq") \
        <(xmllint --format "$XL_SCRATCH/show-with-rgbeffects/<saved-name>.xsq") \
        > "$XL_SCRATCH/baseline-vs-saved.diff"
   ```

   (diff command from the P1P-T12 spec; adjust the `baseline0` directory name to what `ls`
   showed.)
6. Summarize the diff (root sections xLights added, `<Jukebox/>`, `nextid`, `ref`/`palette`
   indices, timing-track layer count: the P5 section V4 risk list). Commit the
   xLights-saved file as the first ground-truth fixture **regardless of outcome**
   (location is an owner decision, D4; the existing fixtures live in `tests/golden/fixtures/`).

### 1.5 P1P-T11 delivery check on the real show (manual)

P1P-T11's own spec defers all GUI evidence to P1P-T12; step 1.2 already covers
`.xtiming` standalone import and `.xsq`/`.xmap` import for the golden rig. This step
repeats it on the real show for completeness and is not a spec-required gate.

1. In `show-with-rgbeffects`, with a scratch sequence open, import each file from
   `$XL_SCRATCH/show-under-test/*.xtiming` (timing-track import) and confirm the tracks
   appear with markers at expected bar/beat positions.
2. Import `*_twinklr_mh.xsq` with `*.xmap` (same dialog as 1.4). Confirm models resolve to
   your layout and no unresolved-model warnings appear.
3. Close without saving.

---

## Phase 2P (GUI-bound)

### 2.1 P2P-T5 preview rendering against the windowed xLights

No paid calls. Needs a *windowed* xLights (not `--headless`) with the API on. The client
issues `loadSequence`, `renderAll`, `exportVideoPreview`, `closeSequence` in that order.

1. Launch xLights windowed against `show-with-rgbeffects`; API on; no unsaved work open.
2. Run the committed smoke test on a short sequence (the spec asks for one short fixture):

   ```bash
   TWINKLR_XLIGHTS_PREVIEW_SEQUENCE="$XL_SCRATCH/acc-basetemp-with/xlights_acceptance_baseline0/baseline.xsq" \
     uv run --frozen pytest tests/golden/test_preview_render_local.py -m local_only -q
   ```

   It asserts only that a video file exists and is non-empty, and does not print its path.
3. Run it again for the full show (needed by steps 3.3/3.4), capturing the video path and
   frame rate. The snippet below uses the verified `render_preview` / `PreviewResult`
   API (`video_path`, `frame_rate`, `frame_ms`) but has **not** been executed:

   ```bash
   uv run --frozen python - <<'PY'
   import asyncio, os
   from pathlib import Path
   from twinklr.core.api.xlights import XLightsAutomationClient

   async def main() -> None:
       async with XLightsAutomationClient() as client:
           r = await client.render_preview(Path(os.environ["SHOW_XSQ"]))
       print(r.video_path, r.frame_rate, r.frame_ms)

   asyncio.run(main())
   PY
   ```

   Export can be slow; the client defaults to 15 minute render and export timeouts.
4. Open the video: confirm it plays, is not black, and audio is muxed in.
5. Record: video path (do not commit), size, frame rate, duration, date, xLights build.
6. If xLights is not running, the client should fail with a single actionable message
   naming the port and the windowed requirement (spec criterion 3); note if you see a raw
   connection traceback instead.

Expected captured request/response pairs should become the fake-transport fixtures the
spec asks for (spec "Effort & risk"); that is follow-up work, not part of this run.

### 2.2 P2P-T12 live injection round trip (scratch sequence only)

No paid calls. This test **mutates the open sequence** and leaves the effect visible. It
never saves. It refuses to run if the open sequence's path is not exactly the one you name.

1. In `show-with-rgbeffects`, create a new sequence and **save it once** to
   `$XL_SCRATCH/show-with-rgbeffects/scratch-inject.xsq` so it has a real path (the test
   compares the open sequence's `fullseq` path to the env var). Leave it open.
2. Confirm the model exists (`Dmx MH1`). API on.
3. Run:

   ```bash
   TWINKLR_RUN_LIVE_XLIGHTS_INJECTION=1 \
   TWINKLR_XLIGHTS_SCRATCH_SEQUENCE="$XL_SCRATCH/show-with-rgbeffects/scratch-inject.xsq" \
   TWINKLR_XLIGHTS_SCRATCH_MODEL='Dmx MH1' \
     uv run --frozen pytest tests/local_only/test_live_injection.py -m local_only -q
   ```

4. Expected: 1 passed. It injects one `DMX` effect (`E_SLIDER_DMX1=128`, 0-500 ms,
   section id `local_smoke`) on a reserved layer (99+), calls `renderAll`, then
   `checkSequence` (expects result code 200).
5. In the GUI: scroll to layer 99 on `Dmx MH1` and confirm the 500 ms effect exists. Click
   it and confirm its setting. Do **not** save.
6. Discard: close the sequence without saving, delete `scratch-inject.xsq` and any
   `.xbkp`, disable the API.

### 2.3 Optional: CLI `inject` and `regenerate` against the scratch sequence

**Paid.** Spec manual-validation cap: at most 3 songs' worth of section re-plans, at most
$3.00. This goes beyond the committed pytest harness; do it only if you want the end-to-end
iteration loop evidence. Both commands also plan against the live layout (`getModels`).

1. Open a fresh scratch sequence (as 2.2) in a show folder whose layout contains your
   configured MH model names.
2. Dry run first (prints exact writes, no writes):

   ```bash
   uv run --frozen twinklr inject --audio "data/music/11 - Need A Favor.mp3" \
     --config <job_config.live>.json --out "$XL_SCRATCH/inject-out" --dry-run
   ```

3. Real injection, then one section:

   ```bash
   uv run --frozen twinklr inject --audio "data/music/11 - Need A Favor.mp3" \
     --config <job_config.live>.json --out "$XL_SCRATCH/inject-out"
   uv run --frozen twinklr regenerate <section_id> \
     --audio "data/music/11 - Need A Favor.mp3" \
     --config <job_config.live>.json --out "$XL_SCRATCH/inject-out"
   ```

   `<section_id>` is a canonical unique ID such as `chorus_2` (help text); take it from the
   dry-run output or the run's `macro_sections.json`.
4. In the GUI, inspect layers 99+ on the MH models; confirm only the regenerated section
   changed. Do not save. Close without saving; disable the API. On a timeout, per
   `docs/user-guide.md`: do not save, inspect layers 99+, re-run the same command (idempotent
   recovery).
5. Record spend (console/ledger) against the $3.00 cap.

---

## Phase 3

### 3.1 P3-T6 empirical GUI acceptance: palette index 0 and quantization

No paid calls. Spec questions: does xLights apply the first-registered palette
(settles P5-M4) and does it rewrite effect times (settles P5-M3).

**Palette index 0 ($0, offline fixture).** The committed
`tests/golden/fixtures/display_pipeline_first.xsq` post-dates the amendment (20 ms grid,
explicit `palette="0"`, version `2026.15`). Do not edit it (it is a golden pin); copy it:

```bash
cp tests/golden/fixtures/display_pipeline_first.xsq "$XL_SCRATCH/palette0.xsq"
```

1. In a scratch sequence in a show with a model named `Yard Arches`, import effects from
   `palette0.xsq` mapped to that model.
2. Click the Color Wash effect (520 ms to 6520 ms) and open its palette. Expected colors,
   from the file's palette 0: `#E53935`, `#43A047`, `#F5F1E8`, `#FFFFFF`, brightness 50.
3. Record applied / fell back to default / other (screenshot into the evidence record).

**Quantization (save-and-diff).** Use the MH show from Step 0.

1. Import `$SHOW_XSQ` with its `.xmap` into a scratch sequence (as 1.4), save as
   `$XL_SCRATCH/show-with-rgbeffects/q-saved.xsq`.
2. Diff:

   ```bash
   diff <(xmllint --format "$SHOW_XSQ") <(xmllint --format "$XL_SCRATCH/show-with-rgbeffects/q-saved.xsq") > "$XL_SCRATCH/q.diff"
   grep -c 'startTime=' "$XL_SCRATCH/q.diff"
   ```

3. Record whether any effect `startTime`/`endTime` changed. Effects are on the 20 ms grid
   per the amendment, so unchanged times is the expected outcome; any rewrite is a finding.

Discard the saved scratch sequence afterwards.

### 3.2 P3-T6 "Seeding" check: superseded

The original LOCAL-ONLY item (export into a real user template and confirm pre-existing
effects are unchanged) is no longer reachable: the owner-approved 2026-08-26 amendment makes
export **fresh-only** and rejects mutation through a parsed user document, so no code path
writes into a user template. See decision D5; nothing to run.

### 3.3 One-song vision proof on the MH show (P2P-T6)

This paid proof is in
[runbook 05 §3.2](05-phase-2p-and-3-live-evidence.md), which owns its cap and evidence home.
Run it there **once**, using the preview video from step 2.1 and the scratch-copy
`$SHOW_XSQ` / `$SHOW_CHECKPOINT` set above. Do not run it again here.

### 3.4 P3-T8 show-level evaluation: combined show, vision judge, human judgment

Spec exit: one combined-show evaluation record, with deterministic metrics, rubric-v2
scores, a human judgment beside it, calibration line, and recipe join, committed under
the P1P-T10 record path.

What exists and what does not:

- **Deterministic tier (offline, $0).** `twinklr show` writes `<xsq>.evaluation.json`
  beside the show XSQ; then:

  ```bash
  uv run --frozen twinklr show-eval "<xsq>.evaluation.json" --out "$XL_SCRATCH/show-eval.json"
  ```

- **Completed-record validation.** After a completed record exists (strict, file-backed
  provenance with relative paths):
  `uv run --frozen twinklr eval-report <path-to-completed-show-record>`.
- **No command produces the combined show for free.** `twinklr show` (flags: `--audio
  --layout --fixture-config --config`, optional `--app-config --out --fe-output-dir
  --style --session-id`) makes paid planner calls and exercises the P3-T4 path whose live
  acceptance is still open with its two-attempt cap exhausted ("no third request is
  authorized", HANDOFF). Do not run it live without an explicit owner decision (D6).
- **Missing tooling.** There is no CLI or script that (a) samples frames and runs the
  show-level judge live (`judge_show_frames` in `reporting/evaluation/show_judge.py` is a
  library function only, no local_only test), (b) assembles and writes a
  `ShowEvaluationRecord`, or (c) captures the human judgment fields. See the report list
  at the end of this runbook.

Procedure once D6 is resolved and tooling exists (or is written):

1. Generate the combined show (`twinklr show ...`); copy outputs and the
   `.evaluation.json` manifest into the scratch folder.
2. In windowed xLights, export its preview (step 2.1 snippet with that `.xsq`).
3. Run the deterministic tier (`show-eval` above).
4. Live judge: one request, budget about $0.15, hard cap $1.00 for the task, actual spend
   recorded. The judge never scores sync/alignment (spec, non-negotiable).
5. **Human judgment, blind to the model's scores.** Watch the full video, then score the
   same categories 0-10: musicality-by-proxy, coordination, color/palette coherence,
   variety and pacing, and cross-part coordination (null if a part is absent); add free
   text; record reviewer and timestamp. These are the exact `HumanShowJudgment` fields
   (`show_record.py`). The five cross-part criteria definitions live in
   `show_judge.py` (`CoordinationCriterion`): apply them to the same frames.
6. Commit the record and its relative-path evidence bundle under `evaluations/<date>-<slug>/`,
   add a row to `evaluations/INDEX.md`, then run `eval-report` on the record to prove it
   reloads.

---

## Teardown (every session)

1. Close all scratch sequences without saving; delete scratch `.xsq` and `.xbkp` files.
2. **Disable the xLights automation API.** Quit xLights.
3. Confirm no stray files in the repo: `git status --porcelain` should show only your
   intended evidence edits. Never commit videos, `.env`, or `$XL_SCRATCH`.

---

## Evidence recording and final checklist

Specs name some locations and not others. Where a spec is silent, this runbook proposes a
single dated record, `changes/twinklr-reactivation-review/evidence/YYYY-MM-DD-xlights-gui.md`
(decision D4; no such directory exists yet), and a HANDOFF update once each exit is real.
Do not mark any exit done without its artifact.

| Exit | Artifact (where) | Done when |
|---|---|---|
| P1P-T10 human judgment | `evaluations/2026-08-13-golden-fixture-mh4-minimal/judgment.md` Record filled; `evaluations/INDEX.md` row updated | Reviewer, 0-10 score, date, free text present; PENDING-OWNER banner removed |
| P1P-T12 acceptance, both modes | New row(s) in `tests/golden/README.md` "Run record" (xLights build, Twinklr SHA, rigs, date, per-test outcome incl. skips) or `tests/golden/XLIGHTS-ACCEPTANCE.md` per spec; owner-confirmed Q1-Q4 stated | Both `with_rgbeffects` and `bare` runs recorded; Q1-Q4 each answered |
| P1P-T12 param inspection | Same record: which effect, which keys compared, mismatches | At least one effect inspected |
| P1P-T12 ground truth | xLights-saved `.xsq` committed + diff summary; optional `test_emitted_xsq_matches_saved_ground_truth_structure` | Fixture committed regardless of outcome |
| P1P-T12 hygiene | Evidence of API disabled afterwards; no repo change enables it | Checked in Teardown |
| P1P-T11 delivery import | Section in the evidence record (step 1.5) | `.xtiming` markers and `.xsq`/`.xmap` import confirmed on the real show |
| P2P-T5 preview | Evidence record: video size, frame rate, duration, date, build; `test_live_preview_export` result | Non-empty playable video exported |
| P2P-T12 injection | Evidence record: pytest result, layer 99 screenshot/observation, scratch discarded | `1 passed` and scratch discarded |
| P2P-T12 optional CLI loop | Evidence record: dry-run output, regenerate result, spend vs $3.00 | Only if run |
| P3-T6 palette 0 | Evidence record: palette applied / fallback (settles P5-M4) | Result recorded |
| P3-T6 quantization | Evidence record: diff summary (settles P5-M3) | Result recorded |
| P3-T6 seeding | Evidence record: note "superseded by fresh-only amendment" | Owner acknowledges D5 |
| P2P-T6 one-song proof | Preserved `vision_evaluation.json` with dated owner artifact (not committed videos) | Cost <= $0.20, status `uncalibrated` |
| P3-T8 combined-show record | `evaluations/<date>-<slug>/` record + human judgment + calibration line; `eval-report` reload | Spec criteria 6-8 satisfied; owner D6 resolved |

---

## Open owner decisions

- **D1** — Which artifact the Phase 1P human judgment covers (synthetic fixture as-is,
  regenerated at HEAD, or the real-song MH show).
- **D2** — Whether the one real-song P1P-T10 run is still wanted.
- **D3** — Whether a "bare" show folder that xLights silently populates with
  `xlights_rgbeffects.xml` still counts as the bare arm.
- **D4** — Where non-spec-named evidence lives (proposed `changes/.../evidence/`), and the
  filename for the committed xLights-saved fixture.
- **D5** — Formally close P3-T6 "seeding" as superseded by the fresh-only amendment.
- **D6** — Authorize (or defer) the paid `twinklr show` run needed for the P3-T8 combined
  show given the exhausted P3-T4 live cap, and approve the tooling to run/record the
  show-level judge.
