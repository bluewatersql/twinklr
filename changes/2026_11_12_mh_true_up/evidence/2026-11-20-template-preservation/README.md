# Template preservation audit — 2026-11-20

**Result: no catalog loss since the 62-entry sampler; historical template parity
fails validation.** The earlier statement that fewer video entries only removed
repeated variants was true of that recent catalog, but not sufficient to establish
preservation of the older template arrangements. Restoring representative motion
paths did not preserve every authored combination of path, fixture selection,
formation, phase, repeat and multi-step timing.

Audit source: `ff2f8d28`. Historical boundary: `0ec65d47^` = `5d50580c`.
Recent comparison: `e0376f66`, source of the 62-entry sampler.
No source changes, provider calls or show mutations. CI remains paused.

## Counts reconciled

| What is counted | Count | Verified meaning |
|---|---:|---|
| Historical registered Python templates | 37 | Counted factories and checked all imports in historical builtins registry. |
| Historical legacy JSON files | 3 | Same IDs as three of the 37; not three additional templates. |
| Separate physical-family catalog at the historical boundary | 7 | Predecessor of the current seven original families; separate from the 37 legacy arrangements. |
| Catalog at the 62-entry sample | 7 | Six non-zoom families plus Zoom Wave. |
| Prior video entries | 62 | Eight standalone shape demos + six families × (base + eight presets). |
| Current catalog | 25 | All seven recent families retained + eighteen additions. |
| Current video entries | 24 | One base per family, excluding Zoom Wave; includes two static references. |
| Current declared base/preset combinations | 209 | 23 families × nine + two static references. Excluding Zoom Wave: 200. These are not 209 different movements or proof all variants pass on every rig. |
| Legacy IDs still registered | 0 / 37 | They were replaced; name mapping alone cannot prove behavior preservation. |

All seven JSON documents from `e0376f66` are **byte-for-byte unchanged**, including
all eight presets per family: `finite_snap_hold`, `fly_in_cascade`,
`fly_out_cascade`, `masked_wheel_flick`, `mirror_wings`, `target_orbit`, `zoom_wave`.
All 25 current documents load through the production loader into a fresh registry.
Every old video family/preset still exists. All eight standalone demonstration
documents still validate against current schema and registry rules; this is a
schema check, not a fresh render of those eight demos.

## Confirmed arrangement gaps

1. **Inner-only pendulum:** historical `inner_pendulum_breathe.py` targets
   `SemanticGroupType.INNER`; current `pendulum_swing.json` targets `ALL`.
   Narrowing reach or fan aims does not preserve fixture selection. A current authored
   inner-only replacement is missing.
2. **Scattered wave hybrid:** `wave_scattered_fade_in.py` and
   `wave_scattered_fade_out.py` combine `WAVE_HORIZONTAL` with `SCATTERED_CHAOS`.
   Historical `libraries/movement.py` maps that combination to sine pan plus Perlin
   tilt through `geometry_modifiers`; the movement handler applies the override.
   Current `horizontal_wave` has sine pan and held tilt; `organic_meander` has noise
   on both axes. Separate representatives do not reproduce this simultaneous path.
3. **Multi-step choreography:** `build_drop_recover`, `intro_main_outro_phrase`
   and `crossfade_between_steps` contain scheduled sequences of distinct steps.
   Current catalog has no sequential multi-step routine: its only two-step family,
   `split_counter_sweep`, runs both steps simultaneously. The mapped primitives and
   planner's ability to compose do not retain these authored arrangements.
4. **Formation combinations:** the existing coverage table explicitly leaves
   wall-wash, scattered, rainbow, spotlight and X base aims to rig authoring. Examples
   include `ambient_random_wash`, `groove_sway_rainbow_breathe`,
   `pop_lock_spotlight_blackout` and `spiral_xross_blackout`. General ability to author
   a preset is not a shipped equivalent. Their complete looks remain unverified.

Repeat is also different: 31 historical templates declare `PING_PONG`, six `JOINER`;
current catalog declares 24 `JOINER`, one `ONCE`. Some symmetric paths may have the
same output, but this audit does not establish repeat parity. This is not a claim
that all 31 were distinct missing motions. Dimmer/color programs were also outside
the motion restoration, so full-template look parity was never demonstrated.

## Complete historical ID inventory

The source table below is checked against all 37 historical registration imports
and all 37 names in the existing mapping. Every ID is accounted for; **accounted for
does not mean preserved**. Movement/formation combinations and step count are from
historical factory source, not inferred from display names. See the
[current representative mapping](../../../../catalog/templates/moving_heads/movement-coverage.md)
for destinations and disclosed consolidations.

| Historical template | Movement(s) | Formation(s) | Steps |
|---|---|---|---:|
| `accent_snap_tunnel_hit` | ACCENT_SNAP | TUNNEL_CONE | 1 |
| `ambient_random_wash` | RANDOM_WALK | WALL_WASH | 1 |
| `ballyhoo_chaos` | RANDOM_WALK | SCATTERED_CHAOS | 1 |
| `bounce_fan_pulse` | BOUNCE | ROLE_POSE | 1 |
| `build_drop_recover` | SWEEP_LR, ACCENT_SNAP, GROOVE_SWAY | ROLE_POSE, TUNNEL_CONE, ROLE_POSE | 3 |
| `cascade_pulse_lr` | HOLD | ROLE_POSE | 1 |
| `circle_asym_left_strobe` | CIRCLE | AUDIENCE_SCAN_ASYM | 1 |
| `circle_asym_right_pulse` | CIRCLE | AUDIENCE_SCAN_ASYM | 1 |
| `circle_fan_hold` | CIRCLE | ROLE_POSE | 1 |
| `crossfade_between_steps` | SWEEP_LR, PENDULUM | FAN, CHEVRON_V | 2 |
| `dual_sweep_audience_pulse` | DUAL_SWEEP | AUDIENCE_SCAN | 1 |
| `fan_iris_tilt_bias_breathe` | FAN_IRIS | ROLE_POSE_TILT_BIAS | 1 |
| `fan_pulse` | HOLD | FAN | 1 |
| `figure8_mirror_strobe` | FIGURE8 | MIRROR_LR | 1 |
| `groove_sway_rainbow_breathe` | GROOVE_SWAY | RAINBOW_ARC | 1 |
| `hold_center_out_breathe` | HOLD | CENTER_OUT | 1 |
| `infinity_mirror_chase` | INFINITY | MIRROR_LR | 1 |
| `inner_pendulum_breathe` | PENDULUM | ROLE_POSE | 1 |
| `intro_main_outro_phrase` | HOLD, SWEEP_LR, HOLD | ROLE_POSE, ROLE_POSE, ROLE_POSE | 3 |
| `lean_right_scan` | HOLD | AUDIENCE_SCAN_ASYM | 1 |
| `pendulum_chevron_breathe` | PENDULUM | CHEVRON_V | 1 |
| `pop_lock_spotlight_blackout` | POP_LOCK | SPOTLIGHT_CLUSTER | 1 |
| `spiral_xross_blackout` | SPIRAL | X_CROSS | 1 |
| `split_lr_sweep_counter` | SWEEP_LR, SWEEP_LR | WAVE_LR, WAVE_LR | 2 |
| `stomp_tilt_bias_pulse` | STOMP | TILT_BIAS_BY_GROUP | 1 |
| `sweep_lr_chevron_breathe` | SWEEP_LR | CHEVRON_V | 1 |
| `sweep_lr_continuous_phase` | SWEEP_LR | ROLE_POSE | 1 |
| `sweep_lr_fan_hold` | SWEEP_LR | ROLE_POSE | 1 |
| `sweep_lr_fan_pulse` | SWEEP_LR | ROLE_POSE | 1 |
| `sweep_lr_pingpong_phase` | SWEEP_LR | ROLE_POSE | 1 |
| `sweep_ud_chevron_swell` | SWEEP_UD | CHEVRON_V | 1 |
| `tilt_rock_wall_wash_fade` | TILT_ROCK | WALL_WASH | 1 |
| `wave_fan_hold` | WAVE_HORIZONTAL | FAN | 1 |
| `wave_scattered_fade_in` | WAVE_HORIZONTAL | SCATTERED_CHAOS | 1 |
| `wave_scattered_fade_out` | WAVE_HORIZONTAL | SCATTERED_CHAOS | 1 |
| `wave_vertical_spotlight_fade` | WAVE_VERTICAL | SPOTLIGHT_CLUSTER | 1 |
| `zigzag_alternating_pulse` | ZIGZAG | ALTERNATING_UPDOWN | 1 |

## Validation and limits

- Static inventory: historical `git ls-tree`/`git show` plus AST extraction of all
  factories, registry imports and movement/geometry calls. Parsed current JSON and
  loaded it with `load_templates_from_directory` / fresh `TemplateRegistry`.
- Compared original seven files directly to `git show e0376f66:<path>`; identical.
- Checked both authorized local sample manifests, current template/preset membership,
  and the eight former standalone shape documents against `TemplateDoc` plus
  `validate_template_document`.
- Fresh focused checks: `UV_NO_SYNC=1 UV_OFFLINE=1 uv run pytest
  tests/integration/test_mh_restored_movements.py
  tests/unit/sequencer/moving_heads/compile/test_restored_paths.py -q --no-cov`:
  **40 passed in 3.30 s**. These prove current behavior, not old/new arrangement parity.
- Local reproduction script, extracted inventory and test log:
  `/tmp/twinklr-template-audit/`. No owner data is committed.
- Full `make validate` **not rerun**: audit/documentation only, no application edits.
  Prior source gate remains documented separately; it does not close these coverage gaps.
- Independent source audit by `/root/pickup_review` confirms the counts and gaps;
  [review saved here](independent-review.md). Final documentation review also passed,
  with the six-video-families/seven-catalog-families wording corrected. The audit conclusion
  is approved; historical full-template preservation is **not** approved.
  No human taste or hardware acceptance asserted.

Required follow-up to claim preservation: explicitly author the missing fixture
selection, simultaneous hybrid paths, formations and multi-step routines on the
single current renderer, then compare their movement/coordination to historical
source behavior. Do not equate primitive availability with arrangement preservation.
This audit does not implement that follow-up.
