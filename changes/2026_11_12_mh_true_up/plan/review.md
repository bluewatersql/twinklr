# Independent technical-plan review — 2026-11-12

Final verdict after focused re-review: **approved for planning quality**. No material findings remain open. This is not architecture acceptance, implementation authorization, or evidence that code/tests/hardware behavior pass.

Initial verdict: changes requested for the concrete contracts preserved below.
These are design findings, not implementation defects newly introduced by this task.
No implementation tests, live providers, owner data, hardware, or xLights operations
were run. Repository review was read-only. The author is revising concurrently;
locations below identify the reviewed clauses and may shift after edits.

## Focused re-review resolution record

Re-read the current P1, P2, P4 and P5 clauses on November 12, 2026 after author corrections.

| Finding | Status | Verified correction |
|---|---|---|
| Ordinary final-beat/pickup phase domain | Resolved | P1.2 defines MusicalPhaseMap/PhaseKnot, adjacent-interval inference bounded to one interval per edge, explicit provenance and explicit knots for longer gaps; full-duration and delayed-first-beat tests are specified. |
| Physical live-output isolation | Resolved | P4-T3 adds actual full layer/model/group/patch inventory, isolation validation and expanded snapshot hash; unsupported inspection scope aborts mutation. Cross-layer, group, patch and incomplete-inventory tests are explicit. |
| Sparse converter truncation | Resolved | P5 and P4-T6 restrict the recipe to verified nonsparse sources; source metadata/hashes and frame/count/cadence checks are required, sparse or contradictory provenance is rejected, and a high-offset sparse counterexample test is included. The documented read-only -f metadata workaround matches the pinned source's option-branch bug. |
| 8-bit encoding shift | Resolved | P1.3 emits q directly for 8-bit axes and splits only 16-bit axes; endpoint/midpoint and inversion checks are specified. |
| Optional topology denominator clarification | Resolved | P2.2 defines transformed canonical slot count S, denominator S-1, singleton behavior, reverse order and exact five-head phase/sign arrays with subset invariance. |

Also checked the author's related refinements: calibrated mapping endpoints are distinct
from allowed operating limits; initial pose belongs to explicit run configuration;
unknown extinction latency is not zero; complete physical output has declared
resource limits; centered path transforms have a single extent owner. These corrections
close the reviewed ambiguities without broadening the legacy path or claiming empirical
acceptance. P3/P4 dependency separation and the independent frame-oracle direction remain intact.

No new material issue was found in the focused revision. All execution/evidence steps
remain planned. No implementation tests or live experiments were run in this review.

## Initial blocking findings — all resolved in the revised plan

### P1 — Complete the musical-phase domain before requiring full-duration sampling

Location: `plan/phase-1-fixture-fidelity.md:62` (P1.2 musical_phase_at), with the
full-duration sampling obligation at `:78` (P1.3).

The phase function rejects values outside actual beat knots, but existing BeatGrid
contains beat starts, not a guaranteed terminal endpoint. `BeatGrid.from_tempo`
creates `[0,500,1000,1500]` for one 120-BPM four-beat bar with duration 2000 ms
(`packages/twinklr/core/sequencer/timing/beat_grid.py:112`). Full-duration frames
1520 through 1980 cannot be evaluated under the proposed contract. Real detected
beats can also start after zero. Define an explicit bounded boundary policy or
supplied phase sentinels with provenance, retaining exact internal beat knots and
avoiding silent global-average extrapolation. Test normal from_tempo full duration,
a partial terminal beat, delayed first beat and genuinely out-of-song evaluation.

### P1 — Enforce physical isolation before applying a frame-proven live refinement

Location: `plan/phase-4-refinement.md:90`, compared with
`plan/architecture.md:133` (foreign-layer guarantee).

P4 reuses existing collision checks and hashes affected observed signatures, but
`injection.py:299` reads only requested/owned target layers and `:323` rejects only
same-model, same-layer overlaps. A separate user effect/blending layer or group
contribution can alter the actual fixture output while offline locks/darkness still
pass. The architecture's no-foreign-interference requirement has no implementing
preflight task here. Define a bounded isolation/admission check, reject unsupported
external contributions before mutation, and bind relevant observed layers/models/
patch state to the reviewed hash. Test another-layer visibility contribution and
changed physical mapping; do not claim whole-output lock/darkness proof from the
existing reserved-layer collision gate alone.

### P1 — Do not advertise the pinned converter as a general sparse-to-v1 oracle path

Location: `plan/phase-5-evaluation.md:71`–`:81`; repeated command in P4-T6.

The documented `fseq_convert -i ... -o ... -f 1 -n` uses
`src->getChannelCount()` as the default output count (pinned converter lines160–165)
and overrides initializeFromFSEQ's expanded count at lines183–184. For sparse v2,
that is the packed count, whereas `V2FSEQFile::getMaxChannel()` computes the absolute
extent separately (FSEQFile.cpp lines2510–2518). V1 writing emits only output count
bytes (lines819–821). Thus a sparse four-channel fixture patched at absolute indexes
100–103 can be lost/truncated by this command. This makes the proposed evidence
preprocessing unsound for its advertised sparse inputs. Restrict the initial recipe
to verified nonsparse input and reject sparse provenance, or separately prove a
correct full-extent conversion with a high-offset sparse counterexample before
admitting sparse data. Pinning and hashing alone do not prove conversion correctness.

Sources independently inspected:
- [Pinned upstream source](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/fseq_convert/fseq_convert.cpp#L160-L192)
- [Pinned upstream source](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/src-core/render/FSEQFile.cpp#L2510-L2518)

### P1 — 8-bit axis encoding incorrectly shifts away the entire value (corrected during review)

Original location: `plan/phase-1-fixture-fidelity.md:74`; revised clause at `:80`.
The original formula selected q in 0..255 for an 8-bit axis and then always emitted
q>>8 as coarse, yielding zero. Reported to author; re-read revision explicitly emits
coarse=q without a fine channel, and only splits 16-bit axes. This finding is resolved
in the current text; keep the new 8-bit endpoint/midpoint/inversion tests.

## Optional specification clarification

`plan/phase-2-composition.md:49`: give an explicit denominator and an example table
for phase after wing folding, block grouping and modulo groups. “Canonical slot
count” is ambiguous between original fixture count and transformed phase-slot count,
and dividing by N versus N-1 produces different extents. This is a tuning/contract
choice rather than an inherently invalid topology. Record the chosen behavior and
assert numeric phases for an odd-count/block/group case, beyond subset equality.

## Positive checks and limits

The default/explicit schema dispatch, physical versus legacy units, complete-footprint
48-channel transport, preposition failure policy, optical state/latency additions,
P3 macro motif ownership, P4 independence from P3, and independent handwritten/FSEQ
oracle direction are sound. The FSEQ v1 field offsets and 28-byte fixed header agree
with pinned upstream source. Existing named regression paths inspected are real;
new interfaces/test paths are marked proposed. The research phases are covered, with
optional adapters distinct from core exits. Numerical arrangement/resource/study
caps are labeled proposed choices, not measured truths.

No architecture acceptance or product/hardware claim follows from this review.

## Final incremental re-review

Reviewed the final P0/P1/P3 interface changes and task checkpoints. Verdict remains
**approved for planning quality**, with no reopened material findings.

- P0's `ReferenceSelectionResult` owns preference decisions while preserving the
  frozen baseline `SelectorResult`/trace; explicit preference precedence prevents
  implementation-dependent selection.
- P1.6 names a test-only `p1_linear_reveal.json` loaded through existing machinery,
  so P1 integration does not depend on P2 production-family availability.
- P3 cache identity now separates planner-visible semantic admissions from numeric
  render inputs, with tests for calibration changes that do and do not alter admission.
- Explicit P1/P2 commit checkpoints change execution bookkeeping, not the contracts.

The plan remains pinned to `9c55c2e`. Concurrent HEAD `3629fa9` is later repository
work, not an implementation of these plans; the inspected diff concerns audio/layout/
display wiring and related tests. Recheck repository interfaces before execution.
No implementation tests or live validation were performed for this incremental review.
