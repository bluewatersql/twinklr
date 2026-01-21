# Moving Head Sequencer Rewrite — Templates & Rendering (POC → Rewrite Docs)

This folder is the **POC/demo documentation set** for the moving head sequencer rewrite.

**Critical constraints**
- This is a rewrite spec, **not** a refactor plan. It must **not** “adapt the new approach to the old way”.
- The POC proved out concepts; it does **not** dictate production implementation. Production must follow
  project standards: separation of concerns, dependency injection, Pydantic V2 models, strict typing, and TDD.

**POC reference code**
- `packages/blinkb0t/core/domains/sequencer/` (concept proof)

**Related prior notes**
- `changes/templates/` (research/MVP notes used as inputs, not constraints)

## Document map (expected organization)

### Section 1 — Core Concepts / Foundations / Design Concepts
- `01_core_concepts_foundations.md`

### Section 2 — Templates, Template Methodology & Design
- `02_templates_methodology_design.md`

### Section 3 — Logical Architecture and Process
- `03_logical_architecture_process.md`

### Section 4 — Technical Architecture & Design
- `04_technical_architecture_design.md`

### Section 5 — Current System Migration (and implementation plan)
- `05_current_system_migration.md`

## Who this is for
- **Template authors**: how templates/presets/modifiers are designed and validated.
- **Engine implementers**: what the contracts are (geometry/movement/dimmer/curves), what the pipeline outputs,
  and what “repeat-safe” means.
- **Reviewers**: the target architecture and non-negotiable engineering standards for acceptance.

