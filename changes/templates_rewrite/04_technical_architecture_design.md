## Section 4 — Technical Architecture & Design

This section translates the logical pipeline into a **reviewable technical architecture** that conforms to the
repo’s standards (clean boundaries, DI, strict typing, TDD).

### 4.1 Non-negotiable standards (must pass technical review)

- **No god classes**: small orchestrator + small pure components.
- **Strict separation of concerns**:
  - templates describe choreography only
  - rig describes physical fixture semantics only
  - compiler orchestrates; generators/handlers do not orchestrate
- **Dependency injection** for all services (handlers, registries, exporters, beat mapping, LLM client).
- **Pydantic V2** for all validation models (templates, presets, plans, configs, LLM outputs).
- **Python 3.12**, **Ruff**, **mypy strict**.
- **TDD required**: tests first; target **≥80% coverage** for the rewrite.
- **No relative imports** (hard review fail per guidance).

### 4.2 Target package layout (rewrite structure)

Per the rewrite directive (no backwards compatibility required):

```
packages/blinkb0t/core/
  config/              # existing config (should not need changes for rewrite)
  audio/               # migrated as-is from current core/domains/audio
  curves/              # shared curve engine + curve schema (sequence-workload agnostic)
  sequencer/           # NEW root for all sequencing workloads
    moving_heads/      # moving head sequencing workload
      models/          # Pydantic V2 models: rig, templates, presets, plan, IR
      templates/       # loader + patching + schema validation helpers
      compile/         # TemplateCompiler (orchestrator) + scheduling/repeat logic
      handlers/        # geometry/movement/dimmer handlers + registries
      export/          # xLights/XSQ exporters/adapters (reused where appropriate)
      di/              # wiring/container for the workload
      observability/   # trace_id propagation, token tracking hooks (if needed)
tests/
  core/sequencer/moving_heads/...
core/domains/          # DEPRECATED (delete after acceptance testing)
```

**Hard boundary rule**
- Only `compile/` orchestrates across components.
- `curves/` is pure and shared (no lighting-specific logic).
- handlers are pure/near-pure, deterministic functions with explicit inputs.
- exporters are adapters (side effects/formatting only).

### 4.3 Core component contracts (interfaces)

The compiler depends on injected interfaces (Protocol preferred):

- **Beat mapping**
  - bars/beats → ms conversion
  - single source of truth for timing across workloads

- **Template loader**
  - load TemplateDoc by `template_id`
  - validation via Pydantic

- **Patch engine**
  - apply preset/modifier/per-cycle patches (pure)
  - provides “config provenance” (optional but recommended for debugging)

- **Handlers (preferred approach)**
  - **GeometryHandler**: `apply(...) -> base_pose`
  - **MovementHandler**: `apply(...) -> normalized movement curves`
  - **DimmerHandler**: `apply(...) -> normalized dimmer curve`

This “handlers with apply()” shape is intentional:
- consistent integration points
- easy unit testing
- aligns with separation of concerns

- **Curve provider/engine**
  - uniform sampling, time shifting, multiply/envelopes, simplification
  - pure operations on normalized point arrays

- **Exporter**
  - converts IR segments to xLights/XSQ structures
  - may convert normalized curves to absolute DMX at export time, depending on strategy

### 4.4 IR strategy: where DMX conversion happens

Two valid strategies (choose one; both are reviewable if done cleanly):

1. **Compiler emits absolute DMX point curves** -  (chosen approach)
   - exporter is simpler
   - golden testing is straightforward (compare DMX points)
   - cost: compiler must own DMX conversion policies

2. **Compiler emits offset-centered curves + base/amplitude**
   - keeps movement “purely normalized” longer
   - exporter must compose into absolute DMX for xLights
   - cost: exporter is more complex and must replicate clamp policies carefully

- **IR Schema**

```python
class CurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    t: float = Field(..., ge=0.0, le=1.0, description="Normalized time")
    v: float = Field(..., ge=0.0, le=1.0, description="Normalized value")


class PointsCurve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["POINTS"] = "POINTS"
    points: list[CurvePoint] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _validate_monotonic_t(self) -> PointsCurve:
        # xLights-style point arrays typically assume non-decreasing t.
        last_t = -1.0
        for p in self.points:
            if p.t < last_t:
                raise ValueError("PointsCurve.points must have non-decreasing t")
            last_t = p.t
        # Encourage 0 and 1 endpoints (not strictly required, but helpful).
        return self


class NativeCurve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["NATIVE"] = "NATIVE"
    curve_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


BaseCurve = PointsCurve | NativeCurve


class ChannelSegment(BaseModel):
    """IR segment for a single fixture + channel over a time range.

    Either `static_dmx` is set OR `curve` is set.

    For PAN/TILT movement curves, you can optionally encode them as
    *offset-centered* curves (v centered at 0.5) with `base_dmx` and
    `amplitude_dmx`, or you can export absolute DMX points downstream.

    MVP-friendly fields included to support both approaches.
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)
    channel: ChannelName

    t0_ms: int = Field(..., ge=0)
    t1_ms: int = Field(..., ge=0)

    # Option A: static
    static_dmx: int | None = Field(default=None, ge=0, le=255)

    # Option B: curve
    curve: BaseCurve | None = Field(default=None)

    # Composition hints (primarily for movement offset curves)
    base_dmx: int | None = Field(default=None, ge=0, le=255)
    amplitude_dmx: int | None = Field(default=None, ge=0, le=255)
    offset_centered: bool = Field(
        default=False,
        description="If true, interpret curve values as offset around 0.5",
    )

    blend_mode: BlendMode = Field(default=BlendMode.OVERRIDE)

    clamp_min: int = Field(default=0, ge=0, le=255)
    clamp_max: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def _validate_static_vs_curve(self) -> ChannelSegment:
        if self.t1_ms < self.t0_ms:
            raise ValueError("t1_ms must be >= t0_ms")

        if self.static_dmx is None and self.curve is None:
            raise ValueError("ChannelSegment must set either static_dmx or curve")
        if self.static_dmx is not None and self.curve is not None:
            raise ValueError("ChannelSegment cannot set both static_dmx and curve")

        if self.clamp_max < self.clamp_min:
            raise ValueError("clamp_max must be >= clamp_min")

        # For offset-centered curves, base/amplitude must exist
        if self.curve is not None and self.offset_centered:
            if self.base_dmx is None or self.amplitude_dmx is None:
                raise ValueError("offset_centered curves require base_dmx and amplitude_dmx")

        return self
```


### 4.5 Registries and extensibility

All template-referenced IDs map through registries:
- `GeometryID -> GeometryHandler`
- `MovementID -> MovementHandler`
- `DimmerID -> DimmerHandler`

**Rules**
- adding a new movement/geometry/dimmer is a new handler + tests + registry entry
- the compiler does not need edits for new IDs (open/closed principle)

### 4.6 Observability and debuggability

The rewrite must be debuggable under real usage:
- propagate a `trace_id` from CLI / orchestrator into compilation and export
- log at key milestones:
  - template load + selected preset/modifiers
  - computed repeat/cycle plan
  - step schedule per cycle
  - clamp pass summaries (how many clamped, min/max encountered)
- token tracking belongs in the LLM adapter layer, not the renderer

### 4.7 Testing strategy (TDD) and golden outputs

#### Unit tests (fast, deterministic)
- Curve engine:
  - sampling uniformity
  - phase shift correctness (grid rotation)
  - envelope multiplication
  - simplification (near-collinear) invariants
- Patch engine:
  - precedence correctness
  - immutability (no mutation of base docs)
- Repeat scheduling:
  - cycle counts
  - remainder policy behavior
  - ping-pong iteration rules
- Handlers:
  - geometry returns stable base poses
  - movement produces loop-safe curves
  - dimmer respects normalization and stays within bounds before clamp

#### Integration tests
- “Compile a real template for a real rig” yields stable IR:
  - correct number of segments
  - per-fixture phase offsets differ as expected
  - loop boundary is safe
  - clamp rules are applied at the final pass

#### Golden tests
Maintain at least one golden test per “hero template”:
- compare compiled segments (and/or exported xLights output) against a committed baseline
- use stable sampling resolution to make diffs meaningful

### 4.8 What not to do (immediate review failures)

- Do not thread new architecture through `core/domains/*` “just to reuse wiring”.
- Do not introduce backwards compatibility shims that leak old concepts into the new API.
- Do not put orchestration logic into handlers.
- Do not allow templates to name fixtures or DMX channels directly.
- Do not embed mutable global registries/singletons; always inject registries.

