---
type: context
area: product
updated: 2026-08-26
---

# Product Overview

Twinklr transforms music into coordinated Christmas light shows, producing native `.xsq`
files that users can import and refine in the standard xLights editor. It automates
repeatable analysis, planning, and rendering work, but end-to-end authoring-time savings
have not yet been measured. That measurement remains part of the owner-gated evaluation
protocol in
[P2P-T6](../../changes/twinklr-reactivation-review/build/specs/phase-2p-creative-quality/P2P-T6-vision-judge-and-sync-metrics.md).

## Goals

- Beat-aligned, musically coherent choreography derived from each song's structure and energy.
- Native xLights output — no proprietary player or runtime.
- Reliability through separation of concerns: the LLM never touches DMX values directly.

## Current scope

- **Moving head fixtures** — pan, tilt, dimmer, and optional mapped shutter, color, and
  gobo output (primary CLI workflow).
- **Display sequencer** — RGB/pixel effects for outline, tree, and other display elements.
- **Feature engineering** — offline corpus analysis feeding style profiles and recipes
  into generation.

## Deep reference

- [docs/overview.md](../../docs/overview.md) — full overview and subsystem descriptions
- [docs/user-guide.md](../../docs/user-guide.md) — installation, configuration, usage
