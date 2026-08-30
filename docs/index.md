---
title: "Twinklr Documentation"
description: "Documentation hub for Twinklr — AI-powered choreography for Christmas light shows."
---

![Twinklr](assets/twinklr_logo_color_light.png)

# Twinklr Documentation

Welcome to the documentation for **Twinklr** — an AI-powered choreography engine that transforms music into coordinated Christmas light shows using audio analysis, template composition, and multi-agent LLM orchestration.

---

## Overview

### [Overview](overview.md)

> What Twinklr is, high-level architecture, major subsystems, and current scope.

---

## User Guide

### [User Guide](user-guide.md)

> Installation, configuration, and step-by-step usage instructions for running Twinklr to generate xLights sequences from audio files.

### [Pipeline Guide](pipeline_guide.md)

> Detailed reference for the build/feature engineering pipeline, feature store, recipe promotion, template/taxonomy flow, configuration, and troubleshooting.

---

## Developer Guide

### [Developer Guide](developer-guide.md)

> Repository structure, architecture details, pipeline framework, configuration models, testing and quality workflows, and extension points for contributors.

### [Vision Evaluation](vision-evaluation.md)

> Local-only preview judging, deterministic beat/effect metrics, enforced cost caps, and the owner-blind calibration protocol.

### [QA Runbook](qa-runbook.md)

> Step-by-step validation: the automated safety net, a bounded live end-to-end show, output-sophistication checks against pinned baselines, and the human-QA checklist (what is automated-covered vs. what needs human eyes).

---

### [From Sound to Show: How Audio Intelligence Drives AI Choreography](audio_profile/)

> You can’t ask an AI to choreograph a Christmas song if all it sees is a pile of sample values. This opener sets up the real problem: turning raw audio into musical facts an LLM can actually reason about without making the show look like the roofline is having a crisis.

**Parts:** 8 posts | **Level:** 200-300

| Part | Title |
|------|-------|
| 0 | [Giving the Robot Ears Before It Touches the Lights](audio_profile/00_overview.md) |
| 1 | [The Pulse: When the Beat Tracker Hears 126 BPM and the Song Swears It’s 63](audio_profile/01_the_pulse.md) |
| 2 | [The Dynamics: Loud Isn’t the Same as Intense, and the Audio Pipeline Learned That the Hard Way](audio_profile/02_the_dynamics.md) |
| 3 | [The Architecture: Section Detection, or How We Stopped Letting the Chorus Start in the Wrong Universe](audio_profile/03_the_architecture.md) |
| 4 | [The Translation: How We Stuffed 100KB of Audio Facts Into 10KB Without Making the LLM Useless](audio_profile/04_the_translation.md) |
| 5 | [The Words: Lyrics, Phonemes, and the Five-Layer Fallback Chain We Built Because Reality Was Rude](audio_profile/05_the_words.md) |
| 6 | [The Thread: Following One Audio Decision All the Way to the Lights on the Roof](audio_profile/06_the_thread.md) |
| 7 | [The Playbook: Things We’d Tell Past Us Before We Let an LLM Choreograph Christmas Lights Again](audio_profile/07_the_playbook.md) |

---

### [The Feature Engineering Pipeline: Teaching Machines to Read Light Shows](feature_engineering/)

> We start with the weirdest premise in the stack: hundreds of human-made Christmas light shows already contain choreographic knowledge, but it's trapped in XML and audio files. This post frames feature engineering as the slightly obsessive process of teaching machines to read that hidden score before any planner gets to be clever.

**Parts:** 8 posts | **Level:** 300-400

| Part | Title |
|------|-------|
| 0 | [The Choreography Was Hiding in the XML the Whole Time](feature_engineering/00_overview.md) |
| 1 | [Know Thy Corpus: XML, Zip Files, and Mildly Hostile Reality](feature_engineering/01_profiling_the_raw_material.md) |
| 2 | [Teaching a WAV File to Admit Where the Chorus Is](feature_engineering/02_audio_feature_extraction.md) |
| 3 | [Two Timelines Walk Into a Bar: Alignment, Phrases, and Finally Some Signal](feature_engineering/03_alignment_and_encoding.md) |
| 4 | [Mining for Choreography Gold, Finding Some Fool's Gold Too](feature_engineering/04_pattern_mining.md) |
| 5 | [From Patterns to Taste: How the Corpus Learns Style, Flow, and Color Drama](feature_engineering/05_knowledge_extraction.md) |
| 6 | [Promoted to Production: When a Mined Pattern Earns the Right to Boss the Lights Around](feature_engineering/06_from_patterns_to_recipes.md) |
| 7 | [The Feedback Loop That Keeps the Lights From Having an Existential Crisis](feature_engineering/07_the_virtuous_loop.md) |

---
