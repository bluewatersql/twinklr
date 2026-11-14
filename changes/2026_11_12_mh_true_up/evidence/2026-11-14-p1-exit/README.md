---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-14
updated: 2026-11-14
---

# Phase 1 exit evidence — 2026-11-14

Offline, synthetic evidence for the Phase 1 exit. It shows what the code does under
test; it is not an xLights, hardware or taste result. No provider request, owner-local
data, xLights session or hardware was used.

## Commit and gate

- Branch `feat/mh-true-up-p1`, cut from `main` at `bb78227`. Code commit `b4ed49d0`.
- `make validate` on `b4ed49d0`, clean tree before and after: format, lint and
  type-check passed; **6355 passed, 39 skipped**. The 39 skips are opt-in local-only
  suites.
- `main` at `bb78227`: 5882 passed, 39 skipped. The difference is the 473 tests Phase 1
  added.
- `git diff --stat main..b4ed49d0 -- tests/golden tests/regression` is empty: no golden
  or regression file changed.
- All 16 Phase 0 fingerprints in
  [the Phase 0 record](../2026-11-13-p0-baseline/README.md) still match (checked by
  each task's author and reviewer).

## Tasks

Each task was implemented test-first by one agent and reviewed by a separate one, given
the diff and the acceptance criteria. Review rounds counts the first review and each
re-review.

| Task | Commit | Review rounds | Result |
|---|---|---|---|
| P1.0 reject at job load | `a25ead28` | 2 | Superseded in P1.6 by prerequisite checks |
| P1.1 capabilities and physical values | `ef58696e` | 2 | `FixtureCapabilities`, exact `dmx_word`, `ChannelValue.physical` |
| P1.2 physical compile and musical phase | `e1bffd84` | 2 | Exact phase map, finite linear kernel, frame-grid samples |
| P1.3 frame encoding | `98926f05` | 2 | Complete fixture frames, coalesced runs, output budget |
| P1.4 discrete semantics | `9004ada3`, `eb96b4ff` | 2 | Shutter and wheel states resolved through the profile |
| P1.5 dark reposition transactions | `39be9e19` | 5 | `plan_prepositions` |
| P1.6 pipeline integration and identity | `7e3647a3` | 3 | End-to-end `physical_v2` render, pre-planning gate, trace identity |
| `--layout` for `twinklr run` | `b4ed49d0` | 1 | xLights model check for a physical run |

## Phase-exit conditions

| Condition | Offline evidence | Status |
|---|---|---|
| All task tests and `make validate` pass | Gate above | Met |
| 16-bit frames reconstruct across carries | `tests/unit/sequencer/moving_heads/export/test_frame_encoder.py`; `tests/integration/test_mh_physical_pipeline.py` decodes the written `.xsq` and compares it with the encoded frames | Met offline |
| Supported offsets are 1–48 | Capability validation and encoder tests; channel 17 shutter in the integration test | Met offline |
| Limits, discrete values, phase and initial state work as declared | `tests/unit/config/test_mh_capabilities.py`, `test_musical_phase.py`, `compile/test_physical.py`, `compile/test_physical_discrete.py` | Met offline |
| Insufficient or unknown travel never reports feasible | `compile/test_preposition.py` and `test_preposition_fuzz.py` | Met offline; see below |
| Optical darkness covers travel and settle | Same, checked from encoded bytes by `assert_honest_transactions` | Met offline |
| Legacy regression output unchanged | Goldens and regression untouched; reviewer rendered 40 legacy cases at the previous commit and in the tree and compared `.xsq`, `.xtiming`, `.xmap`, trace and fingerprint | Met |
| Authorized xLights proof | [Request](../2026-11-13-p1-xlights-request/README.md) | PENDING-OWNER |
| Hardware accuracy | — | PENDING-OWNER |
| Changed-look acceptance | — | PENDING-OWNER |

### The reposition planner

Successive review rounds found cases the planner called feasible that were not: a
previous cue's motion not waited out, travel timed in degrees instead of encoded words,
darkness at time zero credited to the wrong mechanism, a wheel turning on the reveal
frame, and a back-to-back cue continuing a substituted predecessor. All are fixed and
tested. At the final round:

- The reviewer's independent fuzz ran 120,000 cases, giving 9,251 plans without error
  and about 30,000 planned cues checked from encoded bytes: 0 violations, 0 raw
  exceptions.
- The in-repo fuzz runs four arms with asserted feasible-fraction floors (measured
  5.2%, 6.2%, 29.9% and 14.9% against floors of 3%, 4%, 17% and 9%). Seven deliberate
  planner mutations each fail the default run.

The head-follow model is a pure delay at the configured speed. Acceleration and
overshoot are not modelled, and nothing here was compared with a real fixture.

## Synthetic physical render

The two-head, variable-tempo, 16-bit, channel-17 sequence the integration test builds
is described frame by frame in the
[xLights request](../2026-11-13-p1-xlights-request/README.md#expected-frames), with the
script that reproduces its fingerprints. The reviewer reran that script and reproduced
both fingerprints and every table value.

## Measured

- Planner-gate dry-compile: 1.66 s for 8 heads and 2 template-and-preset combinations
  on a 4-minute synthetic song (reviewer's measurement).
- Output size: 8 heads for 4 minutes of continuous 16-bit motion is about 95,000
  effects and 9.5 MiB (P1.3 author's measurement). The default limits are 1,000,000
  effects and 128 MiB.
- Phase-map acceptance: a synthetic sweep at 120 BPM with lead-ins of 0–3 s and tails of
  0–6 s accepted 18 of 961 grids (P1.6 author's measurement).

## Known limits at exit

- **`physical_v2` refuses most real audio.** A grid with more than one beat of silence
  or fade at either end is refused before planning. Deferred to Phase 2 by owner
  decision of 2026-11-14.
- **No production template is physical.** Only the test template
  `tests/fixtures/moving_heads/physical_v2/p1_linear_reveal.json` carries physical data,
  so a physical `twinklr run` needs `--template-dir`. Physical families are Phase 2.
- **Plan-dependent failures still come after planning.** The gate cannot know whether
  dark repositioning fits between the cues a planner will choose.
- **Not applied on the physical path:** planner intensity, the `transitions` config,
  the `FADE_OUT` remainder policy, undeclared presets, and reposition fallbacks.

## Not verified

- xLights reading DMX sliders 17–48, reconstructing 16-bit carries, and handling a
  sequence near the effect budget.
- The `DisplayAs`, `StringType` and `parm1` values xLights writes for a DMX model. The
  layout check takes them from this repository's parser.
- Real fixture arrival, settle and optical latency against the profile.
- Real-audio beat grids.
- Emission time on long shows: the per-model overlap scan grows quadratically with
  effect count.

## Owner-gated actions

- Live provider requests: authorized on 2026-11-13; **none were made** in Phase 1.
- Owner-local data, xLights mutation, hardware, taste verdicts: none performed.
