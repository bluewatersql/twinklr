# Independent template-preservation audit — 2026-11-20

Reviewer: /root/pickup_review. Read-only source audit of historical 0ec65d47^ and current catalog. No renderer changes, providers, UI, Git mutations, or full suite.

## Verdict

The claim “no templates were lost” is false for registered identities and is not established for full arrangements. The restoration reviewed earlier covered movement primitives and selected arrangements; it did not prove preservation of all original templates. Correct the inventory and overbroad coverage wording. This audit does not implement restoration or supply an owner acceptance verdict.

## Independent counts

- Historical Python built-ins contain 37 unique registered template IDs.
- Three historical catalog JSON files reuse built-in IDs: accent_snap_tunnel_hit, ambient_random_wash, figure8_mirror_strobe. They are not three additional identities.
- Seven separate physical-catalog JSON families already existed before deletion.
- Current catalog has 25 JSON template IDs; overlap with the 37 removed built-in IDs is empty. Its composition is seven physical families plus eighteen new authored families.
- Current templates use 24 JOINER contracts and one ONCE; only split_counter_sweep has multiple steps (two simultaneous steps). This difference is evidence to inspect, not automatic proof that every old PING_PONG template lost distinct behavior.

## Confirmed arrangement gaps / incorrect mapping

### 1. INNER-only pendulum is not preserved by changing fan width

Historical packages/twinklr/core/sequencer/moving_heads/templates/builtins/inner_pendulum_breathe.py:51-69 explicitly targets SemanticGroupType.INNER and uses FAN_POSE_NARROW. Current catalog/templates/moving_heads/pendulum_swing.json targets ALL. movement-coverage.md maps it to pendulum_swing and discusses only fan width/reach. The identity of the active fixtures is a distinct arrangement feature, not a speed/reach or static-aim variation. The engine may still support authoring an INNER step, but no current catalog representative restores this authored selection.

### 2. Scattered-wave geometry changes the path, not only the base aim

Historical wave_scattered_fade_in.py and wave_scattered_fade_out.py combine WAVE_HORIZONTAL with SCATTERED_CHAOS (e.g. fade_in lines60-81). Historical libraries/movement.py:402-408 specifies sine pan, hold tilt normally, and PERLIN_NOISE tilt for this geometry. handlers/movement/default.py:161-173 calls resolve_tilt_curve(geometry), so this override reaches actual curve generation. Current horizontal_wave is sine-pan/held-tilt; organic_meander is noise-pan/noise-tilt. Their separate availability does not preserve simultaneous sine-pan/noise-tilt. The coverage map's scattered-aim consolidation hides this concrete path-combination omission.

### 3. Sequential arrangements and their repeat order were replaced by ingredients

Historical crossfade_between_steps.py:45-47,53-112 authors a four-bar PING_PONG cycle: two bars of angular fan sweep with left-to-right phase, then two bars of chevron pendulum with right-to-left phase. The historical scheduler _cycle_order mirrors placements about the cycle midpoint on odd cycles (compile/scheduler.py, function _cycle_order), so this two-step sequence reverses order. Current angular_pan and chevron_pendulum are separate JOINER templates; neither retains that scheduled arrangement. Availability of section transitions is not proof that this within-template arrangement remains.

Similarly build_drop_recover authored a six-bar three-step sweep/hold/organic sequence (2+2+2 bars), and intro_main_outro_phrase authored an eight-bar hold/sweep/hold sequence (2+4+2 bars). Mapping their ingredients to planner composition explicitly changes preservation scope; it is not equivalent template retention.

### 4. Formations and original light programs remain omitted or unproven

Coverage explicitly consolidates wall-wash, scattered, rainbow, spotlight, X and other aim layouts into future rig authoring. Existing per-fixture presets make recreation possible, but absence of shipped matching templates/presets is not preservation evidence. Old pulse, strobe, fade, blackout and light-chase programs are likewise intentionally outside the movement-only sampler. Therefore sampler transport/visibility approval cannot establish full-template preservation.

## Important qualifications

- Do not equate old PING_PONG labels with reversing every motion curve. The scheduler mirrors step placement; a single full-cycle step may be unchanged. Multi-step reversal above is concrete; remaining equivalence requires evidence.
- Many old names truly shared scalar kernels, and some descriptions were misleading. Primitive consolidation can be valid while complete arrangements are still missing.
- The two asymmetric circle built-ins use the same motion/geometry/phase declarations despite left/right names; their visible differences include light programs. Do not invent a left/right path difference from names alone.
- Current polyline/organic kernels, geometry support, and sample byte checks remain useful verified work. These findings concern the stronger preservation claim, not a reversal of their correctness review.

## Required audit reporting

Report identity retention, whole-arrangement retention, primitive coverage, named presets, and video entries separately. Mark the concrete cases above as missing/partial, and all unmeasured equivalence as unproven. Do not silently convert an omitted arrangement into “covered” merely because a planner could re-author it.
