## Section 1 — Core Concepts / Foundations / Design Concepts

This section defines the **non-negotiable conceptual contracts** the rewrite is built on. These contracts exist
to keep the renderer deterministic, repeat-safe, portable across rigs, and technically reviewable.

### 1.1 Definitions (terms used throughout)

- **Rig profile**: configuration describing real fixtures and their semantics (groups, orders, roles, calibration).
- **Template**: portable choreography described in a **rig-agnostic** way (targets groups/roles, not fixture IDs).
- **Preset**: a named patch applied to a base template (e.g., `ENERGETIC`, `PEAK`).
- **Modifier**: categorical knobs (optional) that apply the same patch mechanism as presets.
- **Step**: a time-bounded unit in a template cycle that defines geometry + movement + dimmer (+ transitions).
- **IR (Intermediate Representation)**: compiled output as **channel segments** (not frames), expressed as static
  DMX values or normalized curves.

### 1.2 Geometry resolution (spatial only; never animated)

**Geometry defines where the rig “is” in space**. It is a static formation used as the baseline for motion.

- **Geometry must not animate**: it should not contain time, cycles, or envelopes.
- **Geometry must be rig-aware** (fixtures/roles/calibration), but **template-portable**.

**Input**
- `fixtures` / `roles` (from rig profile)
- `geometry_id`
- `geometry_params`
- optional “aim context” (e.g., `CROWD`, `SKY`, `HORIZON`, etc.)

**Output**
- Per-fixture **base pose** (targets in your internal units, typically DMX 0–255 or normalized units later mapped)

Conceptually:

```python
base_pose[fixture_id] = (pan_base_dmx, tilt_base_dmx)
```

**Key rule**: Geometry establishes baseline; movement can be “added around” this baseline.

** Pre-Defined AimContext**
```python
class AimZone(str, Enum):
    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"
```


### 1.3 Movement resolution (temporal only; does not decide formation)

**Movement provides motion through/around a formation**, and must not embed the rig’s static layout.

- Movement must not decide “fan vs chevron vs line” (that is geometry).
- Movement should be expressed in a way that composes cleanly with geometry.

**Input**
- `movement_id`
- `movement_params`
- `t_local` (normalized time or absolute time within step)
- `step_duration`

**Output**
- Per-fixture motion as **delta** is preferred (cleaner composition)

Conceptually:

```python
delta[fixture_id] = (pan_delta, tilt_delta)
```

**Why delta is cleaner**
- Keeps geometry and movement separable and testable.
- Makes it explicit where base pose vs motion comes from.
- Allows stable amplitude policies and clamping at a single composition point.

### 1.4 Curves: native vs custom points (and why points-first is normal)

xLights ultimately consumes curves as points over \(t \in [0,1]\). The rewrite treats points as first-class.

#### Native curves
Use native curve IDs only when:
- the shape is one of a small supported set (e.g., `HOLD`, `LINEAR`, optionally `EASE_IN_OUT`, `SINE`)
- you do **not** need compositing (envelopes, blends, modulation)
- you do **not** need precise phase offsets across fixtures

Native curves are limited in configurability and typically do not support composition/blending in a predictable
way across the full pipeline.

#### Custom point curves
Use custom points when:
- you need shapes without native support (sine/triangle/pulse variants)
- you need phase offsets applied cleanly
- you need to combine shapes (movement × envelope, fades, modulation, blending)

**Practical note**: generating custom points “a lot” is normal and expected.

### 1.5 Phase offset in a point-array world (critical)

Because xLights uses normalized time \(t \in [0,1]\), a phase offset is a **time shift in normalized space**.

If:
- the step (or segment) duration is `step_duration_bars`
- you want an offset of `offset_bars`

Then:

\[
offset\_norm = \frac{offset\_bars}{step\_duration\_bars}
\]

For a curve point \((t, v)\), the shifted time is:

\[
t' = (t + offset\_norm) \bmod 1.0 \quad \text{(when wrap is enabled)}
\]

There are two implementation approaches:

#### Option A: apply phase by shifting points
- Shift each point’s \(t\) forward by `offset_norm`
- Wrap around (mod 1.0)
- Re-sort points by \(t\)

This works best when the point set is already dense and uniformly sampled.

#### Option B (mandatory): apply phase by sampling
- Keep the base curve unchanged
- Generate N evenly-spaced samples in [0,1), apply (t + offset) % 1.0, interpolate from base curve
- Generate the final curve by sampling the base curve on a fixed grid and applying the time shift during lookup

This is cleaner when you also want envelopes, blends, or modifiers because it composes without mutating the underlying curve definitions.

### 1.6 Avoiding jitter (and controlling file size)

To avoid zipper/jitter artifacts and keep output predictable:
- Generate points at a **fixed resolution** per segment (e.g., 32 or 64 samples).
- Apply phase offsets, envelopes, and blends on that stable grid.
- Optionally simplify after composition (drop near-collinear points).

#### Why fixed sampling matters
1. **Prevents jitter when combining curves**
   - Different point densities or misaligned time samples can cause subtle stepping artifacts when you phase-shift,
     blend, or repeat.
   - Fixed sampling removes the time-grid mismatch completely.
2. **Makes phase offsets exact and robust**
   - With \(N\) samples, phase offsets can be applied as an index rotation.
   - Example: 32 samples, `offset_norm = 0.25` → shift by \(32 \times 0.25 = 8\) samples.
3. **Keeps output predictable and testable**
   - Fixed \(N\) gives predictable file size and stable diffs in golden tests.

#### Simplification (drop near-collinear points)
Given three consecutive points:
- \(P_0=(t_0,v_0)\)
- \(P_1=(t_1,v_1)\)
- \(P_2=(t_2,v_2)\)

If \(P_1\) lies almost on the straight line from \(P_0 \rightarrow P_2\), it is redundant.

Recommended defaults (practical)
- **Movement curves (pan/tilt)**: sample 64, simplify tolerance \(\varepsilon \approx 0.01\)
- **Dimmer curves**: sample 32, simplify tolerance \(\varepsilon \approx 0.02\)
- **Envelopes (fade in/out)**: usually 3–5 points is sufficient; no oversampling needed

**Ordering rule (do not violate)**
1. Generate dense samples
2. Apply phase shift
3. Apply envelopes / modulation / blends
4. Simplify (optional)

Simplifying earlier distorts timing and breaks repeat-safety.

### Point Simplification

This project uses a **deterministic, tolerance-based polyline simplification** on `(t, v)` points.

#### Scope
Applies to any step represented as an ordered list of control points:
- `P = [(t0,v0), (t1,v1), …, (tn,vn)]`
- `t` is strictly increasing and normalized to `[0,1]`
- `v` is normalized to `[0,1]` (pre-clamp; see clamping contract)

#### Chosen Algorithm
We use **Ramer–Douglas–Peucker (RDP)** on the polyline in the `(t, v)` plane.

**Why RDP:** deterministic, widely used, preserves shape under a clear “max deviation” tolerance, and is easy to validate.

#### Distance Metric (must be consistent)
For a candidate point `Pk` between endpoints `Pi` and `Pj`, compute its perpendicular distance to the segment `Pi→Pj` in a *scaled space*:

- Scale factors (defaults):
  - `st = 1.0` (time weight)
  - `sv = 1.0` (value weight)
- Work in scaled coordinates: `t' = t * st`, `v' = v * sv`
- Distance: Euclidean point-to-segment distance in `(t', v')`

> Note: If you want simplification to prioritize value fidelity over time spacing, set `sv > st` (e.g., `sv=4, st=1`).

#### Tolerance
- `ε = 1/255 ≈ 0.00392` by default (one DMX step in normalized value units)
- If using scaled space, `ε` applies in that space (so choose `st/sv` accordingly)

#### RDP Procedure (deterministic)
1. Always keep the first and last point.
2. For a span `[i..j]`, find point `k` with maximum distance `dmax` to segment `Pi→Pj`.
3. If `dmax > ε`, keep `Pk` and recurse on `[i..k]` and `[k..j]`.
4. Else, drop all interior points `(i+1..j-1)`.

#### Additional Constraints
After RDP, enforce these invariants:
- **Monotonic time:** `t` remains strictly increasing (should hold if input was valid).
- **Minimum time separation (optional):** if `Δt < εt` between adjacent kept points, merge by dropping the interior point that yields lower max error.  
  - Default `εt = 0` (disabled) unless configured.

#### Output Guarantees
- The simplified polyline’s maximum deviation from the original polyline (under the chosen metric) is `≤ ε`.
- Endpoints are preserved exactly.
- Result is deterministic given `(P, st, sv, ε, εt)`.

#### Alternative Algorithms (explicitly not used)
- Douglas–Peucker variant in value-only space: **not used**
- Visvalingam–Whyatt: **not used**
- Custom “near-collinear by slope threshold only”: **not used**

#### Validation
A simplification is valid if:
- endpoints match
- times remain strictly increasing
- the maximum point-to-segment deviation (as defined above) is `≤ ε`


### 1.7 Composition model (how geometry + movement becomes DMX)

The rewrite should treat composition as an explicit step:

- **Movement channels (pan/tilt)** are typically modeled as **offset-centered** normalized curves:
  - normalized value \(v \in [0,1]\) where \(v=0.5\) means “no offset”
  - base pose provides `base_dmx`
  - movement provides `curve` plus an `amplitude_dmx` policy

Example conversion:

\[
value\_{dmx} = base\_{dmx} + (v - 0.5) \times amplitude\_{dmx}
\]

- **Dimmer** is typically modeled as an **absolute normalized curve**:

\[
value\_{dmx} = \mathrm{lerp}(min\_{dmx}, max\_{dmx}, v)
\]

**Safety is not optional**
- Clamp after composition (especially dimmer floor/ceiling).
- Do not “bake safety” into generators (it causes duplication and inconsistent policy).

**Clamping in the “Normalize Early → Offset Late” Pipeline**

In this architecture, the IR does **not** emit per-point DMX instructions. Instead, it stores **normalized curves** `f(t)` (typically `t ∈ [0,1]`, `f(t) ∈ [0,1]`) plus a **transform stack** (e.g., scale/offset) applied later.

**Final value computation (at export/sample time):**

- Apply transforms: `g(t) = f(t) * scale + offset`
- Clamp once, right before materialization: `y(t) = clamp(g(t), 0, 1)`
- Convert to calibrated DMX, and defensively clamp integer output (e.g., `[0..255]`)

**Key rule:** clamping happens at the **export/render sampling boundary** (the first point where discrete values are required), keeping the IR compact and expressive.

**Optional optimization:** store conservative per-segment bounds (`min_f`, `max_f`) to skip clamping when `f(t)*scale+offset` is guaranteed to remain within `[0,1]`.
