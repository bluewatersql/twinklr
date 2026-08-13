# Phase 1P — Render Truth (Track P / M1)

_Goal: part 1 becomes TRUE — the moving-heads path renders what the plan intends,
delivers without touching the user's master file, and the system records its first
real evaluation. Proposal M1; the verified render-defect cluster CF-1/2/6/7 +
SF-1/2/3/4 + CC-4/5._

**Exit criteria:** a song renders to a correct MH show that imports into xLights
2026.15; golden render suite green in CI; first committed evaluation result + a
recorded human judgment; CLI takes the user's fixture config (no hardcoded rig);
`.xtiming` + fresh-`.xsq`+`.xmap` delivery shipped; template-merge retired.

## Lanes

- **Lane G (golden first)**: T1 → T2 (harness before any render change; everything in
  Lane R diffs against it).
- **Lane R (render repair, serial — shared files in `sequencer/moving_heads/` + `curves/`)**:
  T3 → T4 → T5 → T6.
- **Lane A (audio truth, parallel to R — files in `core/audio/` + `api/`)**: T7 → T8.
- **Lane I (instrumentation/cache, parallel — `agents/`, `caching/`, `pipeline/`)**: T9 → T10.
- **Lane D (delivery, after T2; touches `formats/`, `cli/`)**: T11 → T12.

Merge order at phase end: G → R → A → I → D (D rebases on R for exporter touches).

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P1P-T1 | Golden render harness | Wire the existing 587-LOC `scripts/validation/_core/mh_xsq_validation.py` into pytest/CI (it already parses `E_SLIDER_DMX` settings, flags all-zero effects CRITICAL, cross-checks shutter/color/gobo); pin golden settings-strings for 2–3 fixture rigs; add the shutter-channel=6 vs =17 emitted-bytes test (spec in verification.md); add one XSQ parse→export round-trip test (first in repo history). | ST-7, P4-M8, P5-V1, CC-7 | P0-T4 | opus | opus |
| P1P-T2 | Fixture-rig test configs | Create the 2–3 tracked fixture configs (a 4-head rig matching the author's, an 8-head rig, a shutter>16-channel rig) + a tiny deterministic plan fixture so golden diffs are stable without audio or LLM calls. | P4 census, P7-M1 | P1P-T1 | sonnet | sonnet |
| P1P-T3 | Intensity + movement-library repair | Fix the unconditional intensity overwrite (`handlers/movement/default.py`); fill the categorical-params gaps across the movement library (10 single-entry patterns; naive fix KeyErrors 27/29); fix P4-M6 frequency-amplitude inversion (center_curve renormalization makes freq 0.5 double excursion + park at extremes) IN THE SAME CHANGE; fix P4-M5 loop-anchor snap-back; correct the defect-pinning integration test to production's real call shape. | P4-F1/F1a/M4/M5/M6 (CRITICAL cluster) | P1P-T1,T2 | opus | opus |
| P1P-T4 | One time grid | Replace the three grids with the real BeatGrid everywhere: renderer placement (uniform-average `ms_per_bar` → beat-grid lookups; `snap_to_nearest_bar` currently has zero callers), AND the planner-side `_ms_to_bar` nominal-tempo floor in `agents/sequencer/moving_heads/context.py` (both halves in one task — cross-phase constraint). Timing tracks already use the real grid; after this task all three agree. NOTE: P2P-T8 (MIR adoption) upgrades the grid's SOURCE; this task fixes the CONSUMERS. | P4-F2 + P4-M3 (CRITICAL) | P1P-T3 | opus | opus |
| P1P-T5 | Scheduler + preset + calibration truth | Sections shorter than cycle_bars render scaled/truncated instances instead of nothing (34/1/2 census; 1-bar sections currently render NOTHING for all 37); narrative templates play all steps (not just loop steps); fix the 2× overrun (no clipping template uses TRUNCATE/FADE_OUT); fix P4-M2 BLACKOUT full-brightness inversion (fallback + the ×255 unit bug); fix P4-F9 annihilated calibration (center_offset always 0.5 → emitted DMX can exceed calibrated mechanical range); wire `Template.defaults` dimmer floors (P4-M1). | P4-F4/F5/F6/F8/F9/M1/M2 | P1P-T3 | opus | opus |
| P1P-T6 | Channel-default policy | Unwritten channels emit the fixture's DECLARED defaults (`shutter_default=255` "usually open", color/gobo maps) instead of zero-fill; wire `is_channel_enabled`/`ChannelDefaults` or delete them explicitly per rig-config design; golden-diff shows shutter open. | CF-7, P4-F3/F16, P5-V1 | P1P-T5 | sonnet | opus |
| P1P-T7 | Metadata clients + lyrics order | Fix BOTH metadata clients (httpx.Response fed to dict parsers → 100% failure; `json(response)` decode step exists unused) + add the MusicBrainz 1 req/s limiter IN THE SAME CHANGE (fixing AcoustID alone makes the latent ToS violation live); fix the lyrics gating inversion (analyzer passes metadata=None on first pass → LRCLib/Genius structurally skipped, ASR outranks synced lyrics; also double-resolution when WhisperX off); fix the counterfactual client tests (mock dicts where prod gets Response objects). | SF-2/SF-3, P1-F1/F2, P2-M1/M3/F13 | P0-T4 | opus | opus |
| P1P-T8 | Audio DSP correctness fixes | Vocal-detector hop-length reconstruction (rounded-timestamp inversion → ~6–8s drift/4-min song, 3% truncation); builds-merge time-order violation (energy-sorted merge silently drops builds); trim-offset guard for `rms_for_energy` (leading-silence tracks shift section energies; fade-out offset applied twice); thread detected beats_per_bar into builds/drops (hardcoded 4); spectral_flatness hop alignment; HPSS fallback gets a log + status flag; retire-or-wire the decorative validator (results currently discarded at DEBUG with one spurious warning every run); add the repo's FIRST ground-truth assertions (click-track tempo/beats, known key). | SF-1, P2-M2/M4/M5/M6/M7/M8, P2-F1..F3/F24 | P0-T4 | opus | opus |
| P1P-T9 | Cache identity + token truth | ONE change: deterministic session-ID at the CLI (capability exists, documented, unused), cache-root anchoring (currently CWD-relative), prompt-content hashing into agent-stage cache keys (model IDs already present; without this, cross-run reuse serves stale plans after any prompt edit); PLUS per-call token attribution fix (thread `LLMResponse` usage out of the runner; the shared-provider delta race corrupts every shipped run's stage tokens via the profile∥lyrics wave). | CC-4/CC-5, P1-F4/F27/M3, P3-F24, fingerprint addendum | P0-T4 | opus | opus |
| P1P-T10 | Evaluation writer + bridge | Restore the checkpoint writer (~10 lines at the MH orchestrator seam, serializing TODAY'S `PlanSection` — historical artifacts are not replayable) + bridge the existing `eval-report` CLI into `twinklr` (the click command exists; zero writers exist today); commit the first evaluation result + a recorded human judgment (repo history's first). | SF-4, P6-F3 (corrected) | P1P-T4,T5 (eval something true) | sonnet | opus |
| P1P-T11 | Delivery v1: .xtiming + fresh .xsq + .xmap | Ship `.xtiming` export (timeline code is CLI-reachable, correct, best-tested — smallest real deliverable); implement fresh minimal `.xsq` emission (the never-executed branch is self-fatal: `media_file=""` rejected by its own parser) + `.xmap` mapping-hint generation; retire `--xsq` template-merge input ⚖ (unconditional content-loss defect disappears by construction; parser stays for corpus reading). CLI: fixture config becomes the input (kills hardcoded `fixture_count=4`, `min_pass_score`, display graph). | CF-5, P5 V-contract (corrected), ST-8, P7-M1/F8 | P1P-T6 | opus | opus |
| P1P-T12 | xLights acceptance test | LOCAL-ONLY empirical suite against xLights 2026.15 via the automation API: import the fresh `.xsq` (with and without rgbeffects.xml — the one unresolved contract question), verify stamp acceptance, verify shutter-open output on the >16-channel rig config, document results in the golden suite. | M6/M6b unknowns, P1P-T1 spec items | P1P-T11 | sonnet | opus |

## Notes for spec authors

- Lane R tasks must each show golden-diff BEFORE/AFTER blocks in acceptance criteria.
- T3/T4/T5 are the review's CRITICALs: verifier is opus, and acceptance criteria must
  quote the verified defect mechanics (from `reviews/phases/moving-heads-rendering.md`)
  so the executor cannot "fix" a different reading of the bug.
- T11 is ⚖ (user-facing input change) — the spec must include the CLI migration notes
  and is the one task in this phase whose merge the owner reviews directly.

## Execution learnings (mid-phase, binding for remaining tasks)

- **State acceptance criteria at the discriminating seam.** T3 proved the spec's
  handler-level M6 metric passed on unfixed code (the rescale masked the coupling);
  the real pin lived at the curve-generator seam. Verifiers for T4/T5/T6: before
  trusting a spec's acceptance metric, check it FAILS on the pre-fix code.
- Worker discipline recap: no staging; orchestrator commits via pathspec after a
  format-check of the set; worktree verification requires an own-synced venv via
  `python -m pytest`.
