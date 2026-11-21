# Dance Jams full-catalog sequencer rerun — 2026-11-20

Owner explicitly requested the rerun with the full catalog. Source `0a29876f`;
scratch/session `dance-full-catalog-2026-11-20` under the owner's `_twinklr_verify`.
No application source changes. Retained authorized audio/features/profile, corrected
macro and beat grid; fresh Claude Opus 5.5 MH and house section planning. New session
cache misses establish fresh planning; successful stages can be reused within this run.

The scratch synthetic viewing rig receives the shipped 18 explicit position presets;
its previous position library was empty. Physical profiles, ranges, speed limits,
channel mappings and discrete states are unchanged. All 62 catalog templates entered
the physical gate; 55 passed. Seven exclusions are recorded in `admission.json`:
prism/fast-shutter/zoom capability omissions exclude accent_snap_tunnel_hit,
figure8_mirror_strobe and zoom_wave; speed checks exclude ballyhoo_chaos,
build_drop_recover, groove_sway_rainbow_breathe and organic_meander.
The roughly ten-minute gate is reused once, with all 67 inputs hashed, same source
and exact TemplateAdmission JSON round-trip checked before reuse.

The fresh MH plan covers the 13 canonical sections through the detected grid and
selects nine restored arrangements: bounce_fan_pulse, circle_asym_left_strobe,
circle_asym_right_pulse, dual_sweep_audience_pulse, pendulum_chevron_breathe,
sweep_lr_chevron_breathe, sweep_lr_continuous_phase, sweep_ud_chevron_swell and
tilt_rock_wall_wash_fade. Independent review confirmed the actual sent prompt
contained all 55 admitted IDs plus descriptions, and the selected IDs/section bounds
are valid. All 14 house plans and the combined render completed successfully.

Coverage boundary: MH render span ends at 253.911 s of 258.533 s. The retained
verse_4 lies past that grid and is not planned for MH; the final 4.622 s remain dark.
Measured final-second mono RMS: 253 s -22.5 dBFS, 254 s -38.4, 255 s -51.1,
256 s -63.5, 257 s -86.4, 258 s silence. This is retained fade coverage, not newly
inferred beats. House planning retains all 14 macro sections.

## Delivered artifacts and verification

All paths below are relative to
`/Users/ondeck/xlights/_twinklr_verify/dance-full-catalog-2026-11-20/`:

- `sequences/dance_jams_final_audio/dance_jams_final_audio_twinklr_show.xsq`
  and adjacent trace/evaluation records.
- `previews/dance-house-preview.mp4`: xLights native 1280×720, 50 fps,
  12,926 frames, 258.52 seconds, song audio muxed without offset.
- `sequence-verification.json`, `video-verification.json`, `provider-usage.json`,
  `input-provenance.json`, `preflight-inputs.json`, `admission.json` and stage plans.

Fresh scratch verification passed: 48,598 timed effects (48,175 MH and 423 house),
four MH models and all nine selected restored IDs present, no dropped cues or
unplayable totals. The final four dark MH effects end at 258,540 ms, seven milliseconds
past media duration, as explicitly allowed by the encoder's 20 ms frame contract;
all house effects are inside media bounds. The initial scratch verifier incorrectly
required a sub-frame end and was corrected against `frame_encoder.frame_times`.
Independent review confirmed those terminal effects have dimmer zero.

Native render/export, full audio/video decode and 255 audio-window comparisons pass:
maximum measured offset 0 ms, minimum correlation 0.993706. Section contact frames
show the entire house; this is a **house-focused preview** retaining the owner layout
and camera. Several beams extend beyond its upper edge, so it is not sufficient to
judge full moving-head trajectories. No camera or physical calibration is claimed.

SHA-256:

- XSQ: `f41bc89e4fd09869ee896f726060057dca66b1cb30066a91401aa85dee31b06c`
- Video: `0be5030d6278fbbe902044d93dfdc3daf939b459c0dc7b270dcd57b3eb16c723`

## Render limitations

Zero dropped cues does not mean every planner embellishment played. The trace records
nine MH diagnostics: the bridge_1 hit moved from 163.080 to 164.060 seconds; entry
snap/morph transitions in chorus_1, instrumental_3 burst and instrumental_4 played
nothing; chorus_2 build snap is partial; bridge_1 snap cannot fit the physical
repositioning window; instrumental_4 exit blackout yields to its closed event; two
instrumental_3 FASTER variations fall back to their source. These remain visible
limitations of this rerun, not fixed defects or owner-approved choices.
Independent inspection found all four house CUT arrivals have immediate BASE effects
at the nearest frame with no incoming/outgoing boundary fade; house effects remain
within section bounds to 20 ms precision. Human musical/taste judgment: PENDING-OWNER.

## Execution record

Fresh Claude Opus 5.5 planning and judging produced 31 persisted call records,
1,724,887 prompt tokens and 136,465 completion tokens (1,861,352 total recorded).
These are logged tokens, not a billed-cost estimate. Retained prefix and completed
physical admission avoided unnecessary repeat provider work. Pipeline success and
cache misses are in `run-result.json`; one section judge schema failure was repaired.

Hardware output stayed off. xLights was closed without saving incidental layout or
preset changes; production layout/network hashes still match. CI/Pages remain paused.
No application source changed; `make validate` was not repeated for artifact/evidence
work. Latest recorded full source gate remains `caafbf9e`, not a new gate claim.
See [independent review](review.md) for the separate artifact pass and limitations.
