---
title: "Vision Evaluation and Deterministic Grid Metrics"
description: "Local-only preview judging, cost controls, and owner calibration protocol."
---

# Vision evaluation

Twinklr evaluates a rendered xLights preview in two deliberately separate halves:

- A configured mini-tier vision agent scores musicality-by-proxy, fixture coordination,
  palette coherence, and variety/pacing from labeled still frames plus Twinklr's
  timestamped section intent.
- Deterministic code compares every rendered effect boundary with the delivered beat,
  downbeat, and section grids and reports per-section effect density. The vision agent
  never assesses beat placement.

The vision score is **uncalibrated** until the owner protocol below has been completed.
It may be recorded and inspected before calibration, but it must not gate changes or
support trend claims.

## Cost and request controls

The default local run samples 1280×720 frames at 2 fps. Optional contact sheets contain
9–16 timestamp-labeled frames. Before the request, the harness estimates image cost from
the actual image dimensions and a configured per-megapixel price, adds a bounded output
allowance, then checks both caps:

- $0.20 per song
- $2.00 across a multi-song run

The vision role allows one logical call, one provider attempt, no strict-schema
compatibility fallback, and no repair call. A strict-format capability rejection is
therefore one HTTP request, not a hidden second `json_object` request. The preflight also
rejects more than 1,500 images or an encoded request above 512 MiB. A cap failure happens
before the provider is invoked. An override exists only as an explicit caller argument;
normal commands never infer it from frame count or model output.

Each ffmpeg invocation writes to a unique sampling directory, so a shorter rerun cannot
inherit stale frames or sheets from an earlier run. Sampling has a bounded, configurable
timeout and reports an actionable error if ffmpeg exceeds it.

The ledger reserves estimated spend before the request, then replaces that reservation
with exact priced usage as soon as an `AgentResult` arrives, including a failed result.
Run-cap projections are actual settled spend plus still-outstanding estimates. The
combined success record stores the configured model, rubric version, estimate, exact
per-call input/reasoning/completion usage, token-priced actual cost, preview and rendered
artifact SHA-256 values, plan identity, evaluation-config identity, and deterministic
metrics. Pricing is configuration because provider prices change; update it from the
current provider price sheet before an owner run.

## Local-only one-song proof

First export a real preview through the P2P-T5 windowed xLights workflow. Then run the
bounded judge explicitly:

```bash
TWINKLR_RUN_LIVE_VISION_TESTS=1 \
TWINKLR_VISION_PREVIEW=/absolute/path/preview.mp4 \
TWINKLR_VISION_XSQ=/absolute/path/show.xsq \
TWINKLR_VISION_CHECKPOINT=/absolute/path/checkpoints/plans/final.json \
OPENAI_API_KEY=... \
uv run pytest tests/local_only/test_vision_evaluation.py \
  -m local_only -k score_one_song -q
```

This makes exactly one vision request and refuses an estimate above $0.20. It does not
start, stop, or drive xLights. Preserve the generated `vision_evaluation.json` with the
owner's dated evaluation artifact; do not put preview videos or credentials in Git.

## Owner calibration protocol

Use at least five current-schema shows. More is better, but all shows in one calibration
batch must use the same rubric version and sampling configuration.

1. Assign opaque identifiers and randomize presentation order. Do not show the owner any
   vision score, justification, filename that identifies an experimental arm, or model.
2. The owner watches the complete previews, ranks them 1 through N with no ties, and gives
   0–10 scores for the same four visual categories.
3. Only after the owner record is frozen, join it to each `VisionRubricResponse` by opaque
   identifier and validate it as a `CalibrationBatch`.
4. Run `calculate_calibration`. It uses average ranks for tied vision scores and reports a
   deterministic two-sided permutation p-value together with Spearman rank correlation
   and mean absolute error for every category.
5. Freeze an `OwnerCalibrationArtifact` containing N≥5 artifact/preview hashes, rubric
   version, sampling settings, actual costs, date, owner identity, evidence, calculated
   report, and the owner's explicit accepted/rejected decision. Pin the artifact SHA-256
   in any result that claims calibrated status. Missing, changed, rejected, invalid, or
   mismatched records are rejected. Every evidence row must identify a distinct immutable
   sequence: artifact SHA-256 values and preview SHA-256 values are each independently
   unique, even when opaque sequence identifiers and owner ranks differ.
6. Review disagreements frame-by-frame. Do not tune the rubric on the same batch and then
   report that batch as validation; use a new blinded batch after a rubric revision.
7. An owner decides whether agreement is adequate and changes the result's calibration
   status. The code deliberately sets no automatic acceptance threshold.

No calibration was executed during implementation: doing so would require real previews,
paid calls, and owner judgments. Until a dated N≥5 record exists, every generated result
must remain `uncalibrated`.
