## Example: Pan Sine Curve (Normalized → Degrees → DMX at Export)

This pipeline keeps **movement as a normalized curve** (shape) and delays **DMX encoding** until the very end.

### Assumptions (example numbers)
- Channel: **PAN**
- Pose + Geometry resolves the step’s base pan to: **base_pan_deg = 45°**
- Movement: sine “around base” (offset-style), unit curve: **x(t) ∈ [-1..1]**
- Amplitude chosen by template/intensity: **amp_deg = 30°**
- Fixture mechanical pan range: **pan_min = -270°**, **pan_max = +270°** (total span = 540°)
- DMX output: **16-bit** (0..65535)

---

### 1) Generate the *unit* movement curve (no degrees, no DMX)
Offset-style sine (one cycle over the step):
- `x(t) = sin(2πt)` where `t ∈ [0..1]` across the step duration
- `x(t)` is unitless in **[-1..1]**

---

### 2) Bind the unit curve to physical space (degrees) using pose + amplitude
- `pan_deg(t) = base_pan_deg + amp_deg * x(t)`
- Here: `pan_deg(t) = 45 + 30 * x(t)`

This is where “the start point is 45°” comes from:
- If `x(0) = 0`, then `pan_deg(0) = 45°`

---

### 3) Apply constraints & calibration (still not DMX)
Clamp to fixture limits (and apply any calibration/inversion/offsets if needed):
- `pan_deg_clamped(t) = clamp(pan_deg(t), pan_min, pan_max)`

---

### 4) Convert degrees → normalized channel value [0..1]
Map the clamped pan angle into the fixture’s pan range:
- `v(t) = (pan_deg_clamped(t) - pan_min) / (pan_max - pan_min)`
- With `pan_min=-270`, `pan_max=+270`:
  - `v(t) = (pan_deg_clamped(t) + 270) / 540`

---

### 5) Export-time packing to DMX (16-bit)
- `dmx16(t) = round(v(t) * 65535)`
- Split into MSB/LSB:
  - `msb = dmx16 >> 8`
  - `lsb = dmx16 & 0xFF`

---

### Worked sample points (quarter cycle)
| Step fraction t | x(t)=sin(2πt) | pan_deg(t)=45+30x | v(t)=(deg+270)/540 | DMX16 | MSB | LSB |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.000 | 45° | 0.583333 | 38229 | 149 | 85 |
| 0.25 | 1.000 | 75° | 0.638889 | 41870 | 163 | 142 |
| 0.50 | 0.000 | 45° | 0.583333 | 38229 | 149 | 85 |
| 0.75 | -1.000 | 15° | 0.527778 | 34588 | 135 | 28 |
| 1.00 | 0.000 | 45° | 0.583333 | 38229 | 149 | 85 |

---

### Key takeaway
The movement curve is **not “45° in DMX form.”**  
It’s a **unit shape** `x(t)` that gets **anchored** by `base_pan_deg` (from Pose + Geometry) and **scaled** by `amp_deg`, then only at export time becomes a real channel value and finally DMX.
