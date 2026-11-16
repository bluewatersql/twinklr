---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# Viewing render and old-renderer reference, Need A Favor — 2026-11-16

Two renders of one song for the owner to look at before the single-path cutover
(P3-C0): the physical renderer on the owner's rig, and the old renderer, both on the
corrected beat grid. This is a transport result and a set of files. It makes no
judgment of how either looks, and no real fixture was driven.

**Look acceptance: given by the owner on 2026-11-16.** After watching the side-by-side
preview video, the owner answered "approved" and, asked what that covered, chose "Look
accepted, start the cutover"; asked whether bars and phrases started where they hear
them, chose "Yes, they line up". The verdict covers this song, this rig and the house
preview. It is not a hardware result: no real fixture was driven, and the profile's
timings are still chosen, not measured.

## Inputs and authorization

Authorized by the owner on 2026-11-16 (the brief's approvals table):
`data/music/11 - Need A Favor.mp3`; the owner-rig fixture and job configs under
`artifacts/live-validation/`; the layout of `~/xlights`, read only. Code at `dcc14ddf`,
run from an export. The expendable show is `~/xlights/_twinklr_verify/p3_view/`; the
owner's show folder was not written and its layout and network files have the same
hashes as before.

The rig's physical profile is synthetic. Chosen, not measured: travel 150°/s (the
layout's limit, confirmed by the owner), axis latency 20 ms, settle 60 ms, colour and
gobo settle 150 ms, visibility latency 20 ms, pan not inverted, and initial states
centred, dark and settled.

## Offline gate

| Fact | Result |
|---|---|
| Beat grid | 78.30 BPM, 4/4, 61 bars, 246 beats; intervals 697 / 755 / 836 ms |
| Tempo | Halved from the tracker's 156.6 BPM on backbeat evidence |
| Meter confidence | 0.99 |
| Bar placement | 0.98, chord change with onset tie-break (beat 1 against beat 3 decided by kick loudness) |
| Covered span | 0–187,337 ms of 197,400 ms; the last 10.1 s held dark |
| Admitted | Six families, each on its base variant, both presets also admitted |
| Excluded | `zoom_wave`: no zoom axis |
| Entry dips | 740–900 ms, two beats |
| Gate time | 4.6 s |

The first attempt, on the old grid and before the families adapted, admitted one
family ([record](../2026-11-16-p3-real-audio-gate/README.md)).

## Renders

One `twinklr run` each, one attempt each, sharing a session so the audio profile and
macro plan were paid for once.

| | Physical | Old renderer |
|---|---|---|
| Templates used | orbit, wheel flick, mirror wings, fly-out, fly-in, snap-hold | 11 built-in templates |
| Effects | 29,631 | 124 |
| `.xsq` size | 13.8 MB | 0.38 MB |
| Dropped or unplayable cues | None | n/a |
| Render fingerprint | `3c330256…5215` | None (the old renderer writes none) |

Physical plan by section: intro `target_orbit`; verse 1 `masked_wheel_flick`; verse 2
`mirror_wings`; chorus 1 `mirror_wings` then `fly_out_cascade`; break `target_orbit`
then `fly_in_cascade`; chorus 2 `mirror_wings` then `finite_snap_hold`; outro
`finite_snap_hold`. No section named a preset. Sixteen head entries were cut by entry
windows of 745–774 ms; 24 started as authored. Each head is lit in about 79% of
frames, first at 2.0 s.

The physical trace carries ten warnings, one per section and segment: planner
intensity, colour and events are not applied on the physical path, as documented.

## xLights

xLights 2026.20, headless render in the expendable show. For the physical render,
631,680 moving-head bytes compared with Twinklr's encoded frames: **0 mismatches**
(9,870 frames, four heads, 16 channels). House-preview videos were exported through the
automation interface, with the song audio.

Files, local and not committed, in `~/xlights/_twinklr_verify/p3_view/out/`:

- `side_by_side_old_left_physical_right.mp4` — old renderer left, physical right
- `side_by_side_zoom_old_left_physical_right.mp4` — the same, cropped and enlarged
- `physical_need_a_favor_preview.mp4`, `legacy_need_a_favor_preview.mp4` and their
  `_zoom` copies
- `physical_need_a_favor.xsq`, `legacy_need_a_favor.xsq` and the two `.fseq` files

The heads sit small at the top of the house-preview frame and beams aimed upward leave
it; that is the saved xLights camera view. The layout's models ignore the shutter in
preview, so darkness shows through the dimmer; every dark physical frame has the dimmer
at zero.

Starting the xLights UI changed one window-layout settings key, restored from a backup
taken beforehand.

## Provider requests

All `claude-opus-5-5`; the logs show tokens, not cost.

| Run | Requests | Tokens |
|---|---|---|
| Physical | Audio profile 1; macro planner 2 and judge 1; moving-head planner 1 and judge 1 | 119,582 |
| Old renderer | Moving-head planner 1 and judge 1 (profile and macro from cache) | 52,566 |

Each moving-head planning call also had one request rejected by the provider before
the client's fallback succeeded (finding 1).

## Findings, recorded and not fixed

1. **The moving-head plan schema is rejected by the provider** ("compiled grammar is
   too large", HTTP 400). The client falls back to carrying the schema in the prompt
   and both runs succeeded that way. One wasted request per planning call.
2. **xLights automation sometimes splits a request:** two of four `loadSequence` calls
   failed with a parse error and succeeded on retry.
3. **Per-call LLM log files are named by session, iteration and call number,** so two
   runs sharing a session overwrite each other's logs.
4. **The first macro plan used 18 theme tags the code does not know;** the second
   iteration was accepted.

## Not verified

Any real fixture; any other song or rig; a literal screen recording (not made).
