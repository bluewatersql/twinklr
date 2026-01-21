## Section 5 — Current System Migration (and Implementation Plan)

This section describes how to migrate from the current moving head sequencer to the rewrite with **no backward
compatibility requirements** and with strict engineering standards.

### 5.1 Migration principles (hard rules)

- **No backwards compatibility**: do not preserve legacy APIs or legacy internal representations.
- **Rewrite what must be rewritten; reuse what can be reused** — but only if it meets standards or is brought to
  standard as part of the migration.
- **Do not adapt the new system to the old system**. If a reusable component forces that adaptation, it is not
  reusable as-is.
- **Separate codebases**:
  - the new sequencer must live under `core/sequencer/`
  - it must be possible to delete the old sequencing code (`core/domains/...sequencing...`) after acceptance
    testing without dependency breaks

### 5.2 LLM migration (major simplification)

Rewrite the LLM interaction contract to a minimal, categorical response:

- LLM selects:
  - `template_id`
  - `preset_id`
  - optional categorical modifiers (small enums)

**Removed from the new contract**
- semantic group targeting by the LLM
- channel selection semantics
- multi-stage raw plan → implementation expansion pipeline

**Why**
- templates already encode choreography; LLM should select among validated assets, not author motion
- the engine remains deterministic and testable

### 5.3 Audio migration (reuse)

Reuse the existing audio analysis components:
- audio profile extraction
- beat mapping / beat grid

**Constraint**
- beat mapping becomes a shared service used by the new compiler; do not fork time conversion logic.

### 5.4 Rig configuration migration (FixtureGroup → RigProfile)

The rewrite requires a first-class `RigProfile` that describes:
- real fixture IDs
- semantic groups (ALL/LEFT/RIGHT/INNER/OUTER/…)
- chase orders (LEFT_TO_RIGHT/OUTSIDE_IN/…)
- role bindings (optional)
- calibration/safety defaults (e.g., dimmer floor)

Migration guidance:
- **Prefer adapting existing rig config** (e.g., `FixtureGroup` / fixture definitions) into `RigProfile` via a
  dedicated adapter module under `core/sequencer/moving_heads/`.
- Keep the adapter as a boundary:
  - input: current config objects / JSON
  - output: validated `RigProfile`
- Do not allow templates to depend on legacy config types; templates should only see `RigProfile` semantics.

### 5.5 Reuse existing libraries (movement, geometry, dimmer)

Reuse is encouraged, but only through **handler adapters** and only if the code meets the rewrite’s standards.

Preferred approach:
- create **GeometryHandler**, **MovementHandler**, **DimmerHandler** adapters with:
  - `apply(...) -> outputs`
- treat old implementations as internal helpers or port them cleanly into the new module layout

**Key**
- The rewrite owns the contracts and boundaries; reused code must conform to them (not the other way around).

### 5.6 Curve system migration (adapt and simplify)

The rewrite’s curve system must:
- standardize curve schema (native vs points)
- prioritize points-first operations (sampling, time shift, multiply, simplify)
- support fixed-grid sampling to avoid jitter and enable exact phase offsets

Migration actions:
- keep existing curve ideas that match this model
- drop or rework anything that couples curve logic to the legacy renderer or channel semantics

### 5.7 xLights adapter migration (reuse with clean boundary)

Reuse the existing xLights/XSQ export adapters where possible, but enforce a strict boundary:
- exporter consumes the new IR and nothing else
- exporter does not perform orchestration (no template logic, no rig logic beyond conversion needs)

If the existing exporter expects legacy structures, implement a new exporter for the rewrite; do not contort the
rewrite IR to fit legacy exporter expectations.

### 5.8 Template migration and library strategy

Current system issue:
- many templates with small variations

Rewrite strategy:
- fewer base templates + more presets
- deduplicate variations into preset patches
- keep categorical modifiers optional (and bounded)

Migration approach options:
- **Heuristic deduplication**:
  - cluster existing templates by movement/geometry/dimmer IDs + timing structure
  - promote the “centroid” as the base template
  - encode differences as presets
- **LLM-assisted rewrite** (bounded, supervised):
  - LLM proposes preset patches and metadata tags
  - human review required before acceptance

### 5.9 Implementation plan (phased, parallel where safe)

This is the recommended execution plan to land the rewrite safely while supporting a POC/demo.

#### Phase 0 — Foundations (models + contracts)
- Create new package roots:
  - `core/curves/`
  - `core/sequencer/moving_heads/`
- Implement Pydantic models:
  - rig profile
  - TemplateDoc (template + presets)
  - PlaybackPlan
  - IR segments
- Establish strict type checking + Ruff formatting for new modules.

#### Phase 1 — Curve provider (shared)
- Implement fixed-grid sampling, phase shifting, envelope multiplication, simplification.
- Add unit tests for all curve operations.

#### Phase 2 — Handlers (dimmer, geometry, movement)
- Implement handlers with `apply()`.
- Port or adapt existing libraries behind these handlers if they meet standards.
- Add unit tests for each handler contract (pure outputs).

#### Phase 3 — Template patching and rendering
- Implement patch engine:
  - preset patch
  - modifier patch
  - per-cycle patch
  - immutable application + validation
- Implement compiler orchestration:
  - repeat scheduling
  - step compilation
  - phase offset mapping via rig orders
  - compose curves and emit IR segments
- Add integration tests for at least one “hero” template.

#### Phase 4 — Export pipeline
- Implement/exporter adapter consuming IR and producing xLights output.
- Add at least one golden test comparing exported output for stability.

#### Phase 5 — LLM integration (minimal)
- Implement the simplified prompt and response schema:
  - choose template + preset + categorical modifiers
- Add validation and heuristics (guardrails) but keep them minimal.

#### Phase 6 — Acceptance testing and deletion readiness
- Run acceptance testing using real show configs.
- Ensure the new sequencer has no dependencies on `core/domains` sequencing.
- Delete legacy sequencing code after sign-off.

### 5.10 Immediate review fail checklist (migration-specific)

- Any dependency from `core/sequencer/` into `core/domains/...sequencing...`
- Any “compat layer” that forces old plan/expander flows into the rewrite
- Any template schema that allows fixture IDs or channel addresses
- Any orchestration logic in handlers or exporters
- Any new code without strict typing/tests

