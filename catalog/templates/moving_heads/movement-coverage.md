# Movement coverage after the renderer replacement

The renderer replacement removed movement behaviors along with the old template
implementation. The owner rejected that loss on 2026-11-20. Speed and reach presets
are variations, not additional movement types. This inventory accounts for every
`MovementType` at `0ec65d47^`, based on its actual curve definitions and template use.
It does not claim byte parity with the removed renderer or physical-rig acceptance.

**Preservation audit correction (2026-11-20): this is a representative mapping,
not proof that all historical arrangements survived.** Verified gaps include
inner-only fixture selection, simultaneous sine-pan/noise-tilt scattered waves,
and authored multi-step routines. All seven families in the catalog used for the 62-entry sampler
remain unchanged, but the older 37 templates are not preserved one-for-one.
[Counts, complete ID inventory and source findings](../../../changes/2026_11_12_mh_true_up/evidence/2026-11-20-template-preservation/README.md).

| Original movement | Current representative | Behavior and differences |
|---|---|---|
| SWEEP_LR | `angular_pan` | Constant-speed horizontal triangle with angular reversals. |
| PAN_SHAKE | `angular_pan` | Same old triangle; faster/smaller reach was a variation. |
| SWEEP_UD | `angular_tilt` | Constant-speed vertical triangle. |
| TILT_BOUNCE | `angular_tilt` | Same old vertical triangle. |
| TRAMPOLINE | `angular_tilt` | Same old vertical triangle, different rate/reach. |
| STOMP | `angular_tilt` | Same old vertical triangle, different rate/reach; not a separate downward-hit kernel. |
| BOUNCE | `bounce_fan` | Two-axis triangle about explicit fan aims, odd/even phase. The old description said decay, but its curve had none. |
| LASER_SNAP | `bounce_fan` | Same old two-axis triangle, different rate/reach. |
| ZIGZAG | `zigzag_alternating` | Two-axis triangle about alternating high/low aims with left-to-right phase. |
| RADIAL_FAN | `radial_fan` | Two-axis triangle with opposing mirrored wings about fan aims. |
| RANDOM_WALK | `organic_meander` | Deterministic Perlin movement, now explicitly periodic on musical phase, independent fields per axis. |
| GROOVE_SWAY | `organic_meander` | Same old noise family, with smaller/slower variants. Old noise ignored the frequency setting. |
| POP_LOCK | `pose_pop_lock` | Repeating two-pose hold/travel. Each pose holds 3/8 cycle and each transfer takes 1/8 cycle. |
| HIT | `pose_pop_lock` | The same old square pulse; old hit timing/offset parameters were unread. Finite transfers deliberately replace instantaneous jumps. |
| PENDULUM | `pendulum_swing` | Sine pan about fan aims, in unison. |
| WAVE_HORIZONTAL | `horizontal_wave` | Sine pan with left-to-right phase about fan aims. The old SCATTERED_CHAOS override adds simultaneous Perlin tilt; that combination is missing from the current catalog. |
| TILT_ROCK | `tilt_rock` | Sine tilt, in unison. |
| WAVE_VERTICAL | `vertical_wave` | Sine tilt with center-out phase. |
| DIAGONAL_SWEEP | `diagonal_sweep` | Same sinusoidal phase on both axes. |
| CORNER_TO_CORNER | `diagonal_sweep` | Same old paired sine, different name. |
| DUAL_SWEEP | `diagonal_sweep` | Same old paired sine; authored phase distribution retained. |
| CIRCLE | `target_orbit` | Existing continuous elliptical orbit. |
| FIGURE8 | `target_orbit`; `mirror_wings` | Old phase settings actually produced an ellipse; target orbit covers that. Mirror Wings supplies a real figure eight. |
| INFINITY | `diagonal_sweep`; `mirror_wings` | Old defaults put the same scalar on both axes (diagonal motion). Mirror Wings supplies a real figure eight. |
| SPIRAL | `diagonal_sweep` | Old implementation used the same Lissajous scalar on both axes. A changing-radius spiral was never implemented and is not claimed here. |
| CROSS_PATTERN | `diagonal_sweep` | Identical old scalar path to SPIRAL/INFINITY; no distinct X traversal existed. |
| FAN_IRIS | `fan_iris` | Linear opening/closing with mirrored wings, outside-in phase, fan aims and inner/outer tilt bias. Repeats continuously instead of jumping on reset. |
| HOLD | `static_fan` | Explicit per-head reference aims. Hold's brightness variants are outside movement coverage. |
| ACCENT_SNAP | `static_tunnel`; `finite_snap_hold` | Original kernel was hold at tunnel aims. The current finite snap provides actual travel and destination hold. |
| NONE | `static_fan` | Sentinel for no movement, not another motion pattern. |

The 37 old templates composed these patterns with geometry, phase, light, color and
transitions. They were not 37 extra movement kernels. Original dimmer-only variants
and multi-section narrative templates are not relabeled as new movements. Existing
fly-in/out cascades, finite snap, orbit, mirror wings and masked wheel flick remain.
The movement sample shows one base per routine; it does not repeat the nine preset
combinations as if they were distinct movements.

## Rig geometry

Restored geometry uses the existing `FixtureGroup.presets.positions` contract. A
rig defines the following named presets with `fixtures: {fixture_id: {pan_deg,
tilt_deg}}`. Missing aims fail admission explicitly; there is no fallback to center.

| Position preset | Used by | Required meaning |
|---|---|---|
| `movement_fan` | Bounce Fan, Pendulum, Horizontal Wave, Radial Fan, Static Fan | Fan-spread pan aims at a common tilt. |
| `movement_alternating` | Alternating Zigzag | Fan-spread pan with alternating high/low tilt aims. |
| `movement_fan_bias` | Fan Iris | Fan aims with inner/outer tilt bias. |
| `movement_tunnel` | Static Tunnel | Per-head inward/tunnel aims. |

To use a position preset on a directly aimed template, set its component reference
and clear both explicit movement start angles; otherwise explicit values conflict
with the referenced aim. Angles belong to the rig and must fit its physical ranges. The sampler supplies
explicit synthetic aims; it does not install them on the owner's hardware profile.
Other restored families declare their aim directly, as the original seven do.

## Path contract

`Movement.shape="polyline"` adds `path_knots`, a sequence of `{phase,x,y}` values.
Phase starts at 0, ends at 1 and strictly increases. Displacements are normalized
in [-1,1], then transformed and scaled by the existing degree extents. Identical
consecutive positions hold; differing positions travel linearly. A periodic path
must close exactly. A finite path holds its first/last position outside [0,1].
The normal per-frame range and speed checks reject infeasible travel.

`Movement.shape="organic"` is periodic deterministic Perlin motion evaluated on
musical phase, with eight noise units per cycle, two octaves, repeat 8 and fixed
axis bases 0/17. It has no mutable random state and no sample-count dependence.
It uses the same transforms and physical checks as other relative paths. Extents
scale noise displacement; a noise cycle need not reach its full extent.

## Removed template arrangements

This table accounts for all 37 removed built-ins. Consolidation means their motion
is represented, not that their dimmer/color program or whole-song narrative is
recreated. Aim-only differences remain explicit rig authoring choices; they are not
counted as additional motion kernels. No claim of original-show look parity is made.

| Removed template(s) | Current motion / arrangement |
|---|---|
| `accent_snap_tunnel_hit` | `static_tunnel` retains tunnel aim; actual snap travel is `finite_snap_hold`. Light hits are existing song intent. |
| `ambient_random_wash`, `ballyhoo_chaos`, `groove_sway_rainbow_breathe` | `organic_meander` restores organic motion. Wall-wash, scattered and rainbow base aims are consolidated into rig-authored placement; their old exact aim layouts are not reproduced by the default meander. |
| `bounce_fan_pulse` | `bounce_fan`: explicit fan aims, odd/even phase, angular two-axis movement. |
| `build_drop_recover` | Its sweep → accent hold → organic sway motion is represented by `angular_pan`, `static_tunnel`, `organic_meander`; the three-part musical narrative remains planner composition rather than a new kernel. |
| `cascade_pulse_lr`, `fan_pulse`, `hold_center_out_breathe` | Static aims, with light-only chase/pulse/breathe; `static_fan` is the movement reference. Center-out base aim is a rig position choice, not a movement. |
| `circle_asym_left_strobe`, `circle_asym_right_pulse` | `asymmetric_orbit`: elliptical movement about asymmetric rig aims with left-to-right phase. Their optical difference is excluded. |
| `circle_fan_hold` | `target_orbit` covers the orbit; a fan of base aims is rig authoring, not an additional orbit kernel. |
| `crossfade_between_steps` | `angular_pan` → `chevron_pendulum`; crossfade is already supported by section transitions, not another movement. |
| `dual_sweep_audience_pulse` | `diagonal_sweep`: coordinated two-axis sine with traveling phase. Audience aim belongs to the rig. |
| `fan_iris_tilt_bias_breathe` | `fan_iris`: fan aim, inner/outer tilt bias, mirrored linear opening/closing, outside-in phase. |
| `figure8_mirror_strobe`, `infinity_mirror_chase` | `mirror_wings` supplies mirrored figure-eight choreography; the old misnamed scalar curves are detailed above. |
| `inner_pendulum_breathe` | **Partial:** `pendulum_swing` supplies the sine path but targets ALL; the old template targets INNER only. Fan width/reach cannot replace fixture selection. |
| `intro_main_outro_phrase` | Hold → angular sweep → hold is represented by `static_fan`, `angular_pan`; narrative is planner composition. |
| `lean_right_scan` | Static asymmetric aim, not scanning motion; `static_fan` demonstrates hold, with asymmetric base aims an explicit rig choice. |
| `pendulum_chevron_breathe` | `chevron_pendulum`: V-shaped aims and traveling pendulum phase. |
| `pop_lock_spotlight_blackout` | `pose_pop_lock`: alternating pose switches and dwell. Spotlight aim is a rig choice; blackout is excluded from motion coverage. |
| `spiral_xross_blackout` | Historical scalar path maps to `diagonal_sweep`; no true spiral existed. X base aims and blackout do not create a spiral kernel. |
| `split_lr_sweep_counter` | `split_counter_sweep`: simultaneous LEFT/RIGHT steps with opposing phase orders and fan aims. |
| `stomp_tilt_bias_pulse` | `angular_tilt`: vertical angular movement. Tilt bias and light pulse are separately authored rig/light choices. |
| `sweep_lr_chevron_breathe` | `angular_pan` supplies constant-speed motion; `chevron_pendulum` demonstrates chevron formation with smooth motion. The combination is authored by applying the chevron position preset to angular motion. |
| `sweep_lr_continuous_phase`, `sweep_lr_fan_hold`, `sweep_lr_fan_pulse`, `sweep_lr_pingpong_phase` | `angular_pan` restores the triangle; `horizontal_wave` demonstrates traveling phase and `split_counter_sweep` counterphase. Old light differences and speed/reach do not add movement types. |
| `sweep_ud_chevron_swell` | `angular_tilt` supplies vertical triangle; chevron base aims are rig authoring, swell is light only. |
| `tilt_rock_wall_wash_fade` | `tilt_rock`: smooth vertical oscillation; wall-wash aim is rig authoring, fade is light only. |
| `wave_fan_hold` | `horizontal_wave`: fan aims with traveling sine. |
| `wave_scattered_fade_in`, `wave_scattered_fade_out` | **Missing combination:** old WAVE_HORIZONTAL + SCATTERED_CHAOS renders sine pan and Perlin tilt simultaneously. `horizontal_wave` and `organic_meander` separately do not preserve that path. Scattered aims and fade programs are also not reproduced. |
| `wave_vertical_spotlight_fade` | `vertical_wave`: center-out vertical phase; spotlight base aims are rig authoring, fade is light only. |
| `zigzag_alternating_pulse` | `zigzag_alternating`: alternating high/low aims and left-to-right angular movement. |

`chevron_pendulum` requires `movement_chevron` positions (a V in base aims),
`asymmetric_orbit` requires `movement_asymmetric` positions (uneven audience aims),
and `split_counter_sweep` requires `movement_fan`. They follow the same explicit
per-head position contract and missing-preset refusal above.
