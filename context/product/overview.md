---
type: context
area: product
updated: 2026-08-13
---

# Product Overview

Twinklr transforms music into coordinated Christmas light shows. It replaces dozens of
hours of manual xLights programming (pan angles, tilt curves, dimmer patterns) with
minutes of automated generation, producing native `.xsq` files that users can import and
refine in the standard xLights editor.

## Goals

- Beat-aligned, musically coherent choreography derived from each song's structure and energy.
- Native xLights output — no proprietary player or runtime.
- Reliability through separation of concerns: the LLM never touches DMX values directly.

## Current scope

- **Moving head fixtures** — pan, tilt, dimmer, shutter, color, gobo (primary CLI workflow).
- **Display sequencer** — RGB/pixel effects for outline, tree, and other display elements.
- **Feature engineering** — offline corpus analysis feeding style profiles and recipes
  into generation.

## Deep reference

- [docs/overview.md](../../docs/overview.md) — full overview and subsystem descriptions
- [docs/user-guide.md](../../docs/user-guide.md) — installation, configuration, usage
