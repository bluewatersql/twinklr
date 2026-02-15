---
title: "Twinklr Documentation"
description: "Documentation hub for Twinklr — AI-powered choreography for Christmas light shows."
---

![Twinklr](assets/twinklr_logo_light.png)

# Twinklr Documentation

Welcome to the documentation for **Twinklr** — an AI-powered choreography engine that transforms music into coordinated Christmas light shows using audio analysis, template composition, and multi-agent LLM orchestration.

---

## Developer Docs

Technical references for contributors and developers working on the Twinklr codebase.

- **[CLAUDE.md](../CLAUDE.md)** — Architecture overview, commands, key patterns, and debugging guide

_More developer docs coming soon — implementation roadmap, architecture decision records, and design specs._

---

## User Docs

_Coming soon — setup guides, configuration reference, and usage tutorials._

### [Inside the Template Engine: How Moving Heads Learn to Dance](mh_templates/)

> The planner says “use sweep_lr_chevron_breathe.” Cool. Now we have to turn that sentence into 0–255 DMX values that make real motors move without blasting the neighbor’s driveway.

**Parts:** 11 posts | **Level:** 400-500

| Part | Title |
|------|-------|
| 0 | [The LLM Clocked Out. The Math Punched In.](mh_templates/00_overview.md) |
| 1 | [One Python Function, 40 Decisions: Dissecting a Template Without Crying](mh_templates/01_template_anatomy.md) |
| 2 | [Point the Beams in a V, They Said. It’ll Be Easy, They Said.](mh_templates/02_geometry.md) |
| 3 | [Waveforms: Because ‘Wiggle It’ Isn’t a Compiler Option](mh_templates/03_curves_generation.md) |
| 4 | [Curve Semantics: The Part Where 0.5 Means ‘Don’t Move’ (And 0.5 Also Means ‘Half Bright’)](mh_templates/04_curves_semantics.md) |
| 5 | [Movement: How to Sweep Without Slamming the Pan Into 0 Like a Roomba](mh_templates/05_movement.md) |
| 6 | [Dimmer: Teaching LEDs to Breathe Instead of Blink](mh_templates/06_dimmer.md) |
| 7 | [Timing & Phase: Making Four Fixtures Stop Acting Like One Big Nervous Fixture](mh_templates/07_timing_phase.md) |
| 8 | [Transitions: Hiding the Crime Scene Between Two Templates](mh_templates/08_transitions.md) |
| 9 | [Compilation Day: Following One Template All the Way to an .xsq File](mh_templates/09_compilation.md) |
| 10 | [We’ve Got Pan/Tilt/Dimmer. The Fixture Has Six Channels. Uh Oh.](mh_templates/10_whats_next.md) |

---
