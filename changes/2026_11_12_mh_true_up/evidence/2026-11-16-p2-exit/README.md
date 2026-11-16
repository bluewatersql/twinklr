---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# Phase 2 exit evidence — 2026-11-16

Offline, synthetic evidence for the Phase 2 exit, plus a pointer to the one authorized
xLights run. It shows what the code does under test. It is not a hardware or taste
result.

## Commit and gate

- Branch `feat/mh-true-up-p2`, cut from `main` at `d6096254`. Last code commit
  `6c8bcd33`.
- `make validate` on `9d0fb9ce` (that code plus a documentation commit), clean tree
  before and after: format, lint and type-check passed; **6800 passed, 39 skipped**.
  The 39 skips are opt-in local-only suites. `main` at `d6096254` had 6355 passed.
- `git diff --stat d6096254..HEAD -- tests/golden tests/regression` is empty.
- The 16 Phase 0 fingerprints and both Phase 1 request fingerprints
  (`4bd67b39…00fc`, `45882658…a2d8`) match, with byte-identical `.xsq` files, checked
  by each task's author and reviewer. `PHYSICAL_RENDERER_REVISION` is still "1".

## Tasks

Each task was implemented by one agent and reviewed by a separate one given the diff
and the acceptance criteria. Review rounds counts the first review and each re-review.

| Task | Commit | Review rounds | Result |
|---|---|---|---|
| P2.0 silent song edges | `43b5adbd` | 2 | Covered span; dark outside it; 961 of 961 sweep grids build |
| P2.4a section entry and fallbacks | `ad6b610b`, `0b60ddfc` | 3, then 2 | Per-fixture entry window, kept-as-authored probe, declared fallbacks, whole-song gate |
| P2.1 named components | `bdca7ade` | 2 | Rig preset library, position and attribute references, provenance |
| P2.2 topology and phase | `efdb4f0d` | 2 | Declared or derived topology, independent phase domains |
| P2.3 paths and finite motion | `5989f96f` | 2 | Circle, lissajous, sweep; transforms; `ONCE` |
| P2.4b visibility and overlays | `00ff28f9` | 2 | Lit windows, masked temporary attributes |
| Gate-coverage follow-up | `5844117b` | 3 | `on_unplayable`; a planned show always renders |
| P2.4c catalog admission and families | `ec30c1e9` | 2 | Six families, rig-aware offer, entry-dip report |
| P2.5 zoom pilot | `6c8bcd33` | 2 | Zoom axis with DMX subrange, `zoom_wave`, 16-channel pilot profile |

Test-first was followed except in the gate-coverage follow-up, whose author wrote
production code before tests and showed by mutation that the tests catch it.

Decisions, deviations and measurements for every task are in the
[plan's execution record](../../plan/phase-2-composition.md#decisions-and-carry-forwards-recorded-during-execution).

## Phase-exit conditions

| Condition | Evidence | Status |
|---|---|---|
| Silent edges accepted, dark outside the covered span, tempo never inferred | P2.0 record; `test_physical_edges.py` | Met offline |
| A grid Phase 1 accepted renders the same frames and fingerprint | Invariance anchors above | Met |
| Legacy output, session ids, registry of 37 unchanged | Goldens and regression untouched; admission tests | Met |
| Six families compile deterministically, offered only under `physical_v2` and only where the rig can render them | `tests/integration/test_mh_physical_families.py`; P2.4c record | Met offline |
| Independent phase domains; missing heads keep ranks | P2.2 record. Ranks hold with a declared topology; a derived topology can shift phases when the highest-index head is removed (documented) | Met with the stated limit |
| Preset overrides have explicit scope | P2.1 record | Met offline |
| `ONCE` hold is one cue per fixture held to the section end | P2.3 record; snap-hold frame test | Met offline |
| Fly-in and fly-out lit directions and dark returns are frame-proven | Family frame tests | Met offline |
| Flicks settle while dark and resume the base | P2.4b record; flick frame test | Met offline |
| Section-entry repositioning fits by construction; dip skipped where eligible | P2.4a records and fuzz | Met offline |
| Zoom pilot is synthetic-proven | `test_optical_axis.py`; P2.5 record | Met offline |
| Pre-planning gate time recorded | Below | Recorded; over target |
| xLights transport of the families | [Result](../2026-11-16-p2-xlights-result/README.md): 376,384 bytes, 0 mismatches | Met for six families; `zoom_wave` not run |
| Hardware accuracy | — | PENDING-OWNER |
| Zoom pilot on a real fixture profile | — | PENDING-OWNER |
| Changed-look acceptance, including entry dips and dark-dropped cues | — | PENDING-OWNER |

## Measured

- **Pre-planning gate, 8 heads, 4-minute song (reviewers' measurements, machine under
  load).** Six families with presets, 18 combinations: 36.1 s steady, 51.4 s variable
  tempo. With `zoom_wave` on a zoom rig, 21 combinations: 56.0 s and 61.6 s. Zoomless
  rig after P2.5: 40.8 s. The plan's target is 20 s. Phase 1 measured about 0.8 s per
  combination on one simple template; the families are costlier (exact-fraction path
  evaluation and the planner's per-frame follow each take about half).
- **Entry dips.** Under one bar in every measured case; one to two beats on profiles
  from 180 to 720°/s at 60–180 BPM.
- **Unplayable cues under the default policy.** Reviewer fuzz over arbitrary admitted
  templates: about 3.0% of authored cue frames kept dark, 99% of them `ONCE` cycles too
  long for their section. Over the six shipped families: none dropped as unplayable;
  0.07% of cue frames dropped by entry windows.
- **Output.** An 8-head, 4-minute family render is about 52,600 effects and 5.9 MB;
  emission takes 2.4 s.
- **Test suite.** 266 s (138 s at the Phase 1 exit).

## Decisions made by the integrator without the owner

Made under the owner's run-to-completion instruction of 2026-11-15; each can be
reversed.

1. `on_unplayable` defaults to `"dark"`: a cue that cannot be played honestly after
   planning renders dark and is recorded, instead of failing the run. `"error"`
   restores fail-fast.
2. An unknown entry bound fails any template: a catalog family is excluded, a user
   template refuses the run before planning.
3. Families are authored for 4/4 only. In 3/4 and 6/8 the orbit, wings and zoom wave
   are left out of the offer.
4. Family ranges were not narrowed, since every measured entry dip is under a bar.
5. The gate-time target was not met and is carried forward, not blocked on.

## Known limits at exit

- **The gate is slow.** 36–62 s before planning on an 8-head rig. A known safe cut
  (caching path and phase values for periodic kernels) is not done.
- **Families are 4/4 only,** and each is admitted or excluded whole with its presets.
- **Planner intensity is still not applied** on the physical path (P3-T3).
- **A derived topology** cannot keep phases when its highest-index head is removed.
- **A legacy run in the same process after a physical one** keeps any user
  `--template-dir` template registered, as before Phase 2.
- **Low, untested:** the CLI print of the unplayable warning; `_predecessor`'s
  unknown-follow return for a plan that skips the gate.

## Not verified

- Real fixture arrival, settle, zoom and wheel timing against any profile. Every
  timing in the profiles used is chosen, not measured.
- Real-audio beat grids, and a full `twinklr run` with a live planner on the physical
  path.
- How any family, entry dip, dark edge or dark-dropped cue looks.
- `zoom_wave` in xLights.

## Owner-gated actions

- Live provider requests: authorized 2026-11-13; **none were made** in Phase 2.
- xLights: one scratch-show run on 2026-11-16, authorized that day.
- Owner-local data, hardware, taste verdicts: none.
