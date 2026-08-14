# 2026-08-13 — golden-fixture run (`mh4_minimal`)

The repository's first committed evaluation result (P1P-T10). Produced entirely offline —
no LLM calls, no network access — using the deterministic plan fixture from P1P-T2
(`tests/golden/harness.py:build_plan`) and a synthetic audio file, not a real song.

## Why not a real song + a real LLM run

P1P-T10's spec authorizes exactly one paid LLM run (`twinklr run` against a real song) as a
**LOCAL-ONLY**, human-operated step, explicitly excluded from automated/agent iteration
("must not be repeated for iteration", "budget: one run"). Spending that budget is a real,
outward-facing financial action; an executing agent should not take it unilaterally without
the project owner present. This run instead exercises the *identical* production code path
— checkpoint writer → `twinklr eval-report` → `generate_evaluation_report` → the real
`RenderingPipeline` — end to end, satisfying the acceptance criteria without that cost. The
real-song run remains a deliberate follow-up for the project owner; see `judgment.md`.

## Inputs

- **Plan**: `tests/golden/harness.py:build_plan()` — the P1P-T2 deterministic 7-section
  plan fixture used by the golden suite (`intro`, `chorus`, `drop`, `breakdown`, `one_bar`,
  `phrase`, `arc`).
- **Rig**: `mh4_minimal` (`tests/golden/harness.py:RIGS`) — 4 heads, pan/tilt/dimmer only.
  Serialized to `fixture_config.json`.
- **Audio**: a synthetic 64s mono WAV (deterministic click track + 220Hz tone). Generated
  by `generate_audio.py` — reproducible, not committed as a binary (run the script to
  recreate `tone.wav`). Not a real song; used only so `AudioAnalyzer`'s tempo/structure
  detection has something to run against, exercising `eval-report`'s full path unmocked.
  It detected ~117.45 BPM and 3 structural sections — a synthetic-signal artifact, not a
  musical judgment.
- **XSQ template**: `tests/golden/fixtures/minimal.xsq`.
- **Commit**: `92af8895767aaa9bd70dbec07400d541e8c27023` (recorded in `report.md`/
  `report.json`'s `run.git_sha` field, captured by `collect.build_run_metadata` via
  `git rev-parse HEAD` at `eval-report` run time — `checkpoint.json` itself holds only
  `run_id` and `plan`, no commit SHA) — the base tree this task built on top of.

## How it was produced

1. `checkpoint.json` — written by the restored checkpoint writer
   (`agents/sequencer/moving_heads/stage.py:MovingHeadStage._write_checkpoint`) from the
   plan above, through the real `_handle_state` seam — exactly what a production pipeline
   run writes, not hand-crafted JSON.
2. `report.json` / `report.md` / `plots/*.png` —
   ```
   twinklr eval-report \
     --checkpoint checkpoint.json --audio <regenerated tone.wav> \
     --fixture fixture_config.json --xsq tests/golden/fixtures/minimal.xsq \
     --out .
   ```
   via the bridged CLI command (P1P-T10's CLI-bridge deliverable).
3. `rendered.xsq` — the same plan rendered through the real production
   `RenderingPipeline` (`tests/golden/harness.py:render_rig`) with `.xsq` export, on the
   harness's fixed 120 BPM grid (matching the plan's authored bar numbers exactly, unlike
   the synthetic-audio-derived grid `eval-report` used) — load this into xLights to
   preview the choreography.

## Reading the report

`report.md` documents renderer *self-consistency* only — physics bounds, template
compliance, transition continuity, loop discontinuity. There is still no ground-truth or
aesthetic comparison in this harness (`ComparisonReport`/`ComparisonMetrics` remain
unimplemented — see P6-F4 in
`changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`). The flagged
physics violations and loop discontinuities in `report.md` are the render's actual current
behavior on this plan (11 errors, 12 warnings at this commit), not defects introduced by
this run — they're recorded here as a baseline, not as something P1P-T10 was scoped to fix.

See `judgment.md` for the (pending) human-judgment record.
