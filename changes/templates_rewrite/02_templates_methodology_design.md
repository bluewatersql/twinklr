## Section 2 — Templates, Template Methodology & Design

This section describes the **template system as a product surface**: how choreography is authored, patched, and
rendered — without leaking rig details or engine internals into templates.

### 2.1 Goals and non-goals

- **Goals**
  - Templates are **portable**: no fixture IDs, no DMX addresses, no calibration numbers.
  - Templates are **repeat-ready**: safe to loop to fill an arbitrary playback window.
  - Templates are **patchable**: presets and modifiers use the same patch mechanism.
  - Templates remain **categorical**: LLM chooses `template_id`, `preset_id`, optional categorical modifiers.

- **Non-goals**
  - Templates do not encode per-frame animation, nor do they output frames.
  - Templates do not embed channel semantics beyond naming channels (PAN/TILT/DIMMER etc.).
  - Templates do not embed “rig formation logic” beyond role/group semantics.

### 2.2 Template orchestration model

Templates are compiled by an orchestrator (compiler) that applies patches in a strict precedence order:

1. **Base template**
2. **Preset patch** (named, curated)
3. **Modifier patch** (categorical knobs, optional)
4. **Per-cycle patch** (optional, from playback plan)
5. **Safety clamps** (final, absolute end)

The engine must keep patching **pure and deterministic** (no mutation of source documents).

### 2.3 Design methodology: templates vs presets vs modifiers

#### Templates
Templates define:
- the step choreography structure (what steps exist, where they fall in the cycle, what they target)
- the “default” movement/geometry/dimmer IDs and their baseline params
- repeat contract and loop safety

Templates should be **few and composable**: one template can cover many variations via presets.

#### Presets
Presets are **curated named variants** (e.g., `ENERGETIC`, `PEAK`) that patch:
- intensities - by well-defined IntensityLevel (`SMOOTH`, `DRAMATIC`, etc.)
- cycles / tempo coupling
- phase offset ordering/spread
- dimmer range (min/max) and policies
- optional geometry tokens (if allowed by schema)

Presets must remain safe and predictable; they are excellent for “show control knobs”.

#### Modifiers
Modifiers are optional categorical knobs (e.g., `ENERGY=HIGH`, `VARIATION=B`, `DENSITY=SPARSE`) that apply patch
objects using the same patching rules as presets.

**Rule**: modifiers are categorical (small enums), not raw numbers or free-form text.

### 2.4 Template capabilities (what a template can express)

#### Roles / groups
Templates target **semantic groups**, not fixtures. They may define:
- **roles**: role names such as `OUTER_LEFT`, `INNER_LEFT`, etc.
- **template groups**: group name → list of roles

At compile time, roles/groups are mapped to real fixtures via the rig profile.

#### Timing and repeatability
Templates are built around a **cycle** and a repeat contract:
- `cycle_bars`: canonical length of the template’s loop cycle
- `loop_step_ids`: which steps form the loop body
- `repeat_mode`: e.g., `PING_PONG` or `JOINER`
- `remainder_policy`: how to handle playback windows that end mid-cycle

**Repeat-safety rule**
- Loop steps must be authored so the loop boundary does not jump (start/end continuity).
- If a loop is not naturally continuous, explicitly encode a boundary transition policy (or joiner step).

#### Phase offsets
Phase offsets replace any “per-fixture offsets[] arrays” with a deterministic, rig-config-driven spec:
- **mode**: `NONE` or `GROUP_ORDER`
- **group**: which target group the spread applies across
- **order**: ordering key (e.g. `LEFT_TO_RIGHT`, `OUTSIDE_IN`)
- **spread**: total spread duration (bars, for musical domain)
- **distribution**: `LINEAR` (MVP), later potentially eased distributions
- **wrap**: whether time wraps within the step

This keeps templates portable and lets the rig define chase semantics.

#### Steps: multi-step choreography
Templates are expressed as steps; each step defines:
- **target**: a group name
- **base timing**: musical start offset + duration
- **geometry**: formation baseline (role pose, fan, etc.)
- **movement**: temporal pan/tilt motion around geometry
- **dimmer**: temporal intensity curve (absolute)
- **entry/exit transitions**: typically dimmer envelopes (and optionally movement envelopes)


### 2.5 Repeatability / Loop-Continuity Contract

This section defines *what* continuity means, *how* it is validated, and *what happens* on failure.

#### Definitions
A looped step defines a normalized curve `y(t)` over `t ∈ [0,1]`.

- **C0 (value) continuity:** the loop closes in value.
  - Requirement: `|y(0) - y(1)| ≤ ε0`
- **C1 (slope) continuity (optional, curve-type dependent):** the loop closes in first derivative.
  - Requirement: `|y'(0) - y'(1)| ≤ ε1`
  - Only evaluated when the curve representation provides a meaningful derivative (e.g., piecewise linear: use end segment slope; splines: use analytic derivative; “preset curves” may opt out).

#### Tolerances
- **Default value tolerance:** `ε0 = 1/255 ≈ 0.00392` (one DMX step in normalized space)
- **Default slope tolerance:** `ε1 = 2 * ε0` (pragmatic default; may be tuned per movement type)
- Implementations MAY override tolerances per channel family (pan/tilt vs dimmer) but must document the override.

#### Validation Procedure (C0 required, C1 optional)
1. Evaluate `y(0)` and `y(1)` after applying the step’s transform stack (scale/offset) but before output quantization.
2. Check C0: fail if `|y(0)-y(1)| > ε0`.
3. If C1 enabled and supported by the curve type, evaluate `y'(0)` and `y'(1)` and check `|y'(0)-y'(1)| ≤ ε1`.

#### Failure Handling Policy (choose one per project; default recommended)
- **WARNING + auto-fix**
  - If C0 fails, auto-insert a short “closure transition” at the loop boundary (e.g., linear ramp) with duration `min(1/16 bar, 100ms)` (or project default).
  - Record a validation warning describing the delta and the inserted fix.

> Note: Auto-fix applies at export/render time (materialization boundary) to avoid mutating the authored template data.

#### Ping-Pong Loop Validation
Ping-pong repeats the curve forward then backward.

- Validate **turnaround continuity** at the reversal point:
  - **Value:** `y(1)` equals itself by construction; C0 is inherently satisfied at the turn.
  - **Slope:** requires **sign-reversal consistency** at the turn:
    - Requirement (if C1 enabled): `|y'(1) + y'(1)| ≤ ε1` → effectively `|y'(1)| ≤ ε1`
    - i.e., the curve should approach a “flat” turnaround; otherwise the reversal creates a visible cusp.
- Also validate the overall cycle closure (end of backward pass to start of forward pass):
  - C0: `|y(0) - y(0)| = 0` by construction
  - C1 (optional): `|y'(0) + y'(0)| ≤ ε1` → `|y'(0)| ≤ ε1`

If C1 fails in ping-pong mode, apply the same failure policy as above (warning/auto-fix/strict).

#### Notes / Rationale
- `ε0 = 1/255` aligns loop validation with the smallest visible DMX quantization step.
- C1 is treated as **quality** (optional) because some curve sources do not expose reliable derivatives.


### 2.6 Template schema (conceptual)

The exact schema will be Pydantic V2 models (strict, `extra="forbid"`). At a conceptual level:

- `Template`
  - identity: `template_id`, `version`, `name`, `category`
  - semantics: `roles[]`, `groups{}` (role-space)
  - repeat: `repeat` (cycle contract)
  - defaults: safety defaults (e.g., dimmer floor/ceiling)
  - steps: `steps[]`
  - metadata: descriptive fields for selection

- `TemplatePreset`
  - identity: `preset_id`, `name`
  - patches:
    - template defaults patch
    - per-step patches keyed by `step_id`

### 2.7 Template document packaging

For author ergonomics and portability, store a unified document per template:
- `TemplateDoc = { template: Template, presets: list[TemplatePreset] }`

This avoids scattering presets in separate registries and makes migration/validation easier.

### 2.8 JSON example (illustrative)

This example is intentionally minimal; it shows the *shape* and constraints (no fixture IDs).

```json
{
  "template": {
    "template_id": "fan_pulse",
    "version": 1,
    "name": "Fan Pulse",
    "category": "HIGH_ENERGY",
    "roles": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
    "groups": {
      "ALL": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
      "OUTER": ["OUTER_LEFT", "OUTER_RIGHT"],
      "INNER": ["INNER_LEFT", "INNER_RIGHT"]
    },
    "repeat": {
      "repeatable": true,
      "mode": "PING_PONG",
      "cycle_bars": 4.0,
      "loop_step_ids": ["main"],
      "remainder_policy": "HOLD_LAST_POSE"
    },
    "defaults": { "dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255 },
    "steps": [
      {
        "step_id": "intro",
        "target": "ALL",
        "timing": {
          "base_timing": { "start_offset_bars": 0.0, "duration_bars": 1.0 },
          "phase_offset": {
            "mode": "GROUP_ORDER",
            "group": "ALL",
            "order": "LEFT_TO_RIGHT",
            "spread_bars": 0.5,
            "distribution": "LINEAR",
            "wrap": true
          }
        },
        "geometry": {
          "geometry_id": "ROLE_POSE",
          "pan_pose_by_role": {
            "OUTER_LEFT": "WIDE_LEFT",
            "INNER_LEFT": "MID_LEFT",
            "INNER_RIGHT": "MID_RIGHT",
            "OUTER_RIGHT": "WIDE_RIGHT"
          },
          "tilt_pose": "HORIZON"
        },
        "movement": { "movement_id": "SWEEP_LR", "intensity": "SMOOTH", "cycles": 0.5 },
        "dimmer": { "dimmer_id": "FADE_IN", "intensity": "DRAMATIC", "min_norm": 0.0, "max_norm": 1.0, "cycles": 1.0 }
      },
      {
        "step_id": "main",
        "target": "ALL",
        "timing": { "base_timing": { "start_offset_bars": 1.0, "duration_bars": 3.0 } },
        "geometry": { "geometry_id": "ROLE_POSE", "pan_pose_by_role": { "...": "..." }, "tilt_pose": "HORIZON" },
        "movement": { "movement_id": "SWEEP_LR", "intensity": "DRAMATIC", "cycles": 1.0 },
        "dimmer": { "dimmer_id": "PULSE", "intensity": "DRAMATIC", "min_norm": 0.2, "max_norm": 1.0, "cycles": 2.0 }
      }
    ],
    "metadata": { "tags": ["fan", "pulse"], "energy_range": [75, 100] }
  },
  "presets": [
    {
      "preset_id": "ENERGETIC",
      "name": "Energetic",
      "defaults": { "dimmer_floor_dmx": 70 },
      "step_patches": {
        "main": {
          "movement": { "intensity": "DRAMATIC" },
          "dimmer": { "min_norm": 0.3, "max_norm": 1.0, "cycles": 2.0 }
        }
      }
    }
  ]
}
```

### 2.9 Authoring hints (practical)

- **Design one “base” template per concept**, not per variation.
  - Use presets for energy/style variations.
- **Make loop steps continuous**:
  - movement curves should be loop-ready (value at \(t=0\) equals \(t=1\))
  - dimmer curves should be loop-ready unless intentionally discontinuous
- **Prefer phase spreading** via `GROUP_ORDER` rather than hand-authored per-fixture offsets.
- **Keep geometry tokens semantic** (pose tokens) and resolve them in a geometry handler.
- **Avoid embedding safety in templates**:
  - templates may declare defaults (like dimmer floor), but the engine must enforce final clamps.

