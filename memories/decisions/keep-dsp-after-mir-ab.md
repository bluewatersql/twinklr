---
type: decision
status: active
created: 2026-08-14
updated: 2026-08-14
confidence: confirmed
tags: [audio, mir, beat-grid, evaluation]
---

# Keep the Current DSP as the MIR Default After P2P-T8

_Pending the owner's required review of the gate outcome. Provenance: the accepted
[P2P-T8 specification](../../changes/twinklr-reactivation-review/build/specs/phase-2p-creative-quality/P2P-T8-mir-ab-and-adoption.md),
the committed fixture manifest at `tests/fixtures/mir/manifest.json`, and the offline
harness `python -m twinklr.core.audio.mir.benchmark --report` on 2026-08-14._

## Decision

Keep Twinklr's `dsp` implementation as the default for both beats/downbeats and
labeled structure. Reject adoption of `beat-this` 1.1.0 and `all-in-one-mlx` 1.0.6
in this task because neither produced the complete five-fixture, two-run result that
the pre-committed gate requires. Do not interpret unavailable candidate metrics as
zero scores or as an empirical loss.

## Pre-committed gate

- Beat/downbeat matching: one-to-one F1 at ±70 ms.
- Structure: annotated functional-transition hit rate at ±0.5 s, with ±3 s secondary.
- `beat-this` must improve mean downbeat F1 by at least 0.05, lose no more than 0.02
  mean beat F1, lose no more than 0.02 beat F1 on any fixture, and be identical across
  two runs.
- All-In-One must improve the strict structure-boundary hit rate by at least 0.10 and
  be identical across two runs.
- Each side of either comparison must contain exactly the five unique fixture IDs
  from the committed manifest. Reported fixture counts are not accepted as evidence
  without those matching identities.
- The ±3 s structure figure is secondary reporting only; it is not a loose-rate
  nonregression rule.

## Fixture set and measured DSP baseline

The five audio excerpts are synthesized deterministically from tracked annotations;
no audio blob, network fetch, or paid service is involved. Beat annotations begin
after t=0 so the known onset-rise blind spot does not lower recall mechanically.

| Fixture | Required coverage | Beat F1 | Downbeat F1 | Section hit ±0.5 s | Section hit ±3 s | Signed beat offset |
|---|---|---:|---:|---:|---:|---:|
| `steady_4_4_pop` | steady 4/4 | 1.000000 | 1.000000 | 0.000000 | 0.333333 | +0.019206 s |
| `waltz_3_4` | non-4/4 | 1.000000 | 0.666667 | 0.000000 | 0.333333 | +0.020363 s |
| `tempo_change_4_4` | tempo-varying | 0.655172 | 0.476190 | 0.000000 | 0.333333 | -0.021409 s |
| `sparse_ambient` | sparse/ambient | 1.000000 | 0.666667 | 0.000000 | 0.000000 | +0.020021 s |
| `syncopated_4_4` | syncopated | 1.000000 | 1.000000 | 0.000000 | 0.333333 | +0.019639 s |
| **Unweighted mean** | 5 fixtures | **0.931034** | **0.761905** | **0.000000** | **0.266667** | — |

The DSP emitted byte-for-byte-equivalent normalized rhythm and structure results on
both harness runs. The ~+20 ms offsets on four steady-tempo fixtures remeasure the
P1P-T8 one-frame onset bias at the app's 512-sample hop; the tempo-changing fixture
does not share that constant bias.

## Candidate limitations and gate outcome

### `beat-this` 1.1.0 — reject for this adoption gate

The optional `mir` / `mir-beats` extra resolves on Python 3.12.13 with the repository's
existing torch/torchaudio 2.4.0 pins. The package does not bundle its ~77 MB `final0`
checkpoint. No complete local checkpoint was present, and the owner prohibited live
calls; Twinklr therefore refuses to auto-download weights and gives an actionable
`TWINKLR_BEAT_THIS_CHECKPOINT` error. Candidate beat/downbeat F1 and determinism are
**not measured**, so the required +0.05 downbeat margin was not demonstrated.
The report represents these unavailable metric means as `null`, not numeric zero.

### `all-in-one-mlx` 1.0.6 — reject for this adoption gate

Official PyPI metadata rechecked 2026-08-14 declares `librosa>=0.11.0`, while
Twinklr pins `librosa>=0.10.2,<0.11.0`. The current machine satisfies the advertised
Apple Silicon/macOS/Python platform requirements, but the dependency set cannot
resolve without widening the core DSP dependency, which this task is not authorized
to do. The adapter remains available for an isolated compatible environment and fails
loudly in the project environment. Candidate boundary metrics and determinism are
**not measured**, so the required +0.10 strict-boundary improvement was not
demonstrated.
The report represents these unavailable metric means as `null`, not numeric zero.

## Consequences

- `AudioProcessingConfig.rhythm_source` and `.structure_source` select independent
  producers; both default to `dsp`.
- Every successful selection writes one `beats_s` / `bars_s` / `structure` truth.
  Builds/drops, tension, timeline, planners, renderers, timing tracks, and other
  consumers continue through that truth and the unchanged `BeatGrid` shape.
- Explicitly selecting an unavailable model fails with installation/checkpoint or
  dependency-conflict guidance, including on audio shorter than ten seconds; it never
  silently falls back or downloads weights. The DSP short-audio result records the
  truthful DSP source and adapter version.
- Audio-feature cache identity is version 5 and includes both selected source names
  and adapter versions, preventing cross-source stale hits.
- Custom energy/multiscale, builds/drops, tension, and timeline analysis remains in
  place regardless of source selection.

## Open items carried forward

1. `beat-this` inference on Python 3.13 remains unverified; package metadata alone is
   not an inference test. Phase 4 owns the coordinated Python/ML-chain move.
2. `all-in-one-mlx` remains a single-maintainer dependency and its model weights were
   not available locally.
3. `all-in-one-fix` PyPI presence remains unverified; its torch ≤2.7 constraint was
   not substituted into this task.
4. `beat-this` still depends on torchaudio, which remains in maintenance wind-down;
   Twinklr adds no torchaudio API usage.

## Related

- [Pipeline architecture](../../context/architecture/pipeline.md)
- [P2P-T8 specification and implementation handoff](../../changes/twinklr-reactivation-review/build/specs/phase-2p-creative-quality/P2P-T8-mir-ab-and-adoption.md)
- [Python 3.12 constraint](../constraints/python-3.12-only.md)
- [Reactivation proposal D10](../../changes/twinklr-reactivation-review/reviews/reactivation-proposal.md)
