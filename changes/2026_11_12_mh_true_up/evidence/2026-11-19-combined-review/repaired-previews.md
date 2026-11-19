---
type: evidence
status: recorded
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Repaired house and moving-head previews

The owner requested a repair after rejecting the first three previews. The
[original Dance Jams audit](dance-jams-quality-audit.md) records the failed run.
The three replacement sequences and 1280×720 xLights 2026.20 previews are under
`/Users/ondeck/xlights/_twinklr_verify/combined-repair-2026-11-19.LPLhDFZV`.
Each sequence includes its trace, evaluation manifest, and moving-head checkpoint.
The local `plans/` directory retains the typed macro, display, moving-head
plans and beat grids used to render the replacements.

| Song | Preview | House cue coverage | Visual check of the old dark passage |
|---|---|---:|---|
| Dance Jams Final Audio | `dance-house-preview.mp4` | 256.86 s | 1:32.180 to 2:07.500. House cues cover the full passage. At least one moving head emits light on 69.4% of frames. |
| Need A Favor | `favor-house-preview.mp4` | 194.08 s | 2:41.520 to 3:12.140. The house and moving heads visibly return through the former chorus blackout. |
| Hey Come Look At My House | `hey-house-preview.mp4` | 138.98 s | 0:46.420 to 1:10.640 and 1:57.560 to 2:20.320. Both former dark sections show house effects and moving-head beams. |

The emitted sequences have no four-second interval with both branches inactive,
counting timed house effects and visible moving-head DMX. In the measured dark
passage for each song, the share of sampled xLights frames showing house activity
rose from 0% to 97.2%, 98.7%, and 95.9% respectively. The comparison samples five
frames per second, crops the house and yard, and checks for at least 50 pixels
35 intensity values above the old dark reference. It measures visibility in these
previews. It does not grade color, brightness on real fixtures, or creative taste.

## Dance Jams cue checks

| Cue time | Replacement result |
|---|---|
| 0:18.060 | All four heads finish the entry snap on its boundary frame. The house accent starts on the same frame. |
| 1:43.940 | The original requested hit is visible on all four heads. |
| 1:51.600 | A coordinated house accent and all-four-head hit land on the measured musical change, at bar 60 beat 3. |
| 2:59.800 | All four heads finish the entry snap on its boundary frame. The tree-group accent starts on the same frame. |

Compared timestamped frames of the old and replacement Dance Jams previews at
these cues and across the former blackout. The verified audio came from the
original source MP3, remuxed starting at zero to correct the native export's
24 ms audio advance. Waveform cross-correlation returned 0 ms at all ten
sampled Dance Jams positions and all three sampled positions per other song.
FFmpeg decoded both streams in full for each preview. The scratch xLights
instance was closed, fixture output stayed off, and production layout and network
checksums matched their starting values.

## Repair scope

- The combined scheduler steps through the macro plan's named lead and support
  teams. It preserves the house foundation and background coverage, fits short
  sections to their available beats, and gives ripple teams a half-beat overlap.
  Typed call/response requires a renderable frame on each side. Coordinated
  slices share endpoints with the xLights frame grid, so a sub-frame fragment
  cannot displace an adjacent cue. The first surviving call/response window
  remains the call. The final schedule matches the emitted runs' schedule across
  all 680 windows in the three saved plans.
- An entry snap can use an already-closed shutter hold for preparation. The
  renderer still requires the move and wheel change to fit the available time.
  The original Dance Jams snap requests gave one beat, shorter than the
  renderer's estimated preparation time on this rig even after the zero-window
  bug was fixed. The replacement uses half a bar within the existing holds.
- The three replacements use saved plans from authorized live replanning. The
  original Dance Jams moving-head plan was reused to verify the repaired cues
  against the failure. Scratch plans preserve explicit focal intent where the
  new macro assigns conflicting group and zone roles. The Dance Jams plan also
  includes house accents at the two snaps and a coordinated accent at 1:51.600.
  These three-song edits are recorded with the local plans.
- Recovered ending beats for these renditions with the untrimmed tracker, after
  checking that its trailing detected beats agreed with the originals. The
  resulting moving-head output reaches 4:13.440 in Dance Jams, 3:11.100 in
  Need A Favor, and 2:19.100 in Hey Come Look At My House. House effects cover
  the last passages. No general beat-tracker settings changed.

Owner look judgment and physical fixture verification remain open.
