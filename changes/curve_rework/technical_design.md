# Detailed Technical Design

## 1) Design goals
- Points-first, deterministic curve operations.
- Explicit **movement offset-centered** vs **dimmer absolute** semantics.
- Late DMX conversion (only at export time).
- Fixed sampling, resample-based phase shifting (Option B), deterministic simplification.
- Extensible curve catalog with presets and metadata.

## 2) Core data model
### 2.1 Curve primitives (existing)
- `CurvePoint(t, v)` — normalized time/value in `[0,1]`.
- `PointsCurve(points)` — monotonic time list with length ≥ 2.
- `NativeCurve(curve_id, params)` — optional native curve reference.

### 2.2 Curve semantics metadata (new)
Introduce a lightweight metadata layer (kept separate from core math functions):

```python
class CurveSemantics(Enum):
    MOVEMENT_OFFSET = "movement_offset"  # centered around 0.5
    DIMMER_ABSOLUTE = "dimmer_absolute"  # 0..1 absolute

class CurveDescriptor(BaseModel):
    curve_id: str
    curve: PointsCurve | NativeCurve
    semantics: CurveSemantics
    loop_ready: bool
    default_samples: int
    tags: list[str]
```

## 3) Curve operation pipeline (pure)
### 3.1 Sampling
- `sample_uniform_grid(n)` returns `[0, 1/n, ..., (n-1)/n]`.
- Optionally add `sample_uniform_grid_inclusive(n)` for loop-ready generation.

### 3.2 Phase shift (mandatory Option B)
- `apply_phase_shift_samples(points, offset_norm, n_samples, wrap=True)`
- Always resample on fixed grid and use interpolation.

### 3.3 Composition
- `multiply_curves(a, b, n_samples)` (envelopes, modulation).
- Must resample on shared fixed grid.

### 3.4 Simplification
- `simplify_rdp(points, epsilon, scale_t=1.0, scale_v=1.0)`.
- Run only after sampling/phase/composition.

## 4) Movement vs dimmer semantics
### 4.1 Movement offset-centered rules
- Movement curves are centered around `0.5` with range `[0,1]`.
- Export transform: `dmx = base + amplitude * (v - 0.5)`.
- Loop-ready required (`v(0) == v(1)` and optional `C1` check).

### 4.2 Dimmer absolute rules
- Dimmer curves are absolute `[0,1]`.
- Export transform: `dmx = clamp_min + v * (clamp_max - clamp_min)`.

## 5) Generators
### 5.1 Generator registry
```python
class CurveGeneratorSpec(BaseModel):
    curve_id: str
    generator: Callable[..., list[CurvePoint]]
    default_samples: int
    semantics: CurveSemantics
    params_schema: dict[str, Any]
    tags: list[str]
```

- Registry maps curve IDs to specs.
- Movement generators return offset-centered curves (or are centered by wrapper).
- Dimmer generators return absolute curves.

### 5.2 Legacy parity list
Implement these curve families:
- Easing (sine/quad/cubic/expo/back in/out/in-out)
- Bounce / elastic
- Noise (perlin/simplex approximations)
- Lissajous / Bezier
- Anticipate / overshoot

## 6) Presets and library
Introduce a `CurveLibrary` to store definitions:

```python
class CurveDefinition(BaseModel):
    curve_id: str
    base_curve_id: str | None
    params: dict[str, Any]
    modifiers: list[str]
    semantics: CurveSemantics
    description: str | None
```

- Presets resolve `base_curve_id` + `params` + modifiers.
- Modifiers are applied on points after generation.

## 7) Loop readiness utilities
```python
def ensure_loop_ready(points: list[CurvePoint], tolerance: float = 1e-6) -> list[CurvePoint]:
    # Ensure v(0) == v(1); if not, append or adjust endpoint.

def ensure_c1(points: list[CurvePoint], tolerance: float = 1e-3) -> bool:
    # Optional slope continuity check; used as a quality gate.
```

## 8) Export-time DMX conversion
Provide utilities aligned with `curve_approach.md`:

```python
def movement_curve_to_dmx(points, base_dmx, amplitude_dmx, clamp_min, clamp_max):
    # base + amplitude*(v - 0.5)


def dimmer_curve_to_dmx(points, clamp_min, clamp_max):
    # clamp_min + v*(clamp_max-clamp_min)
```

## 9) Testing strategy
- **Property tests**: v range in `[0,1]`, monotonic `t`, deterministic output.
- **Loop-ready tests** for movement generators.
- **Golden tests** for catalog curves to guarantee stable shapes.
- **Performance budget**: < 1–5ms per curve op for 64 samples.

## 10) Migration path
- Keep `core/curves` pure.
- Add a translation layer in the compiler/exporter to map curve descriptors to DMX.
- Migrate legacy curve IDs to new registry with backwards-compatible aliases.
