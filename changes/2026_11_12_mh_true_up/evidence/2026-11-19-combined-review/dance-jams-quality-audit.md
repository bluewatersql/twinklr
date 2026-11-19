---
type: evidence
status: recorded
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Dance Jams preview quality audit

The owner reported that the delivered show spent too long in darkness, fell out
of sync with the music, and missed transitions. Reviewed sampled frames of the
delivered MP4 against the emitted XSQ, audio waveform, saved planning checkpoint,
and renderer trace from `64a3bd28`. The owner rejected the delivery. This audit
used the saved local artifacts and made no provider requests.

| Observation | Evidence |
|---|---|
| All four moving heads dark from 1:32.180 to 2:07.500 | One continuous rest in the trace, reproduced by replaying the saved macro and beat grid through `moving_head_dark_spans`. |
| House nearly absent over the same passage | House effects occupy only 6.1% and 5.1% of the respective instrumental sections. The audio in both averages about -13 dBFS. Three short intervals contain house effects. |
| A major audible change in that passage has no corresponding lights | The audio's strongest short-window spectral change is near 1:51.6. The closest macro boundary is 1:49.017. There is no house or moving-head cue at 1:51.6. Spectral changes are waveform measurements, with no claim that each one warrants a section break. |
| Two authored entry snaps were missed | At 0:18.06 and 2:59.80, the trace records a zero-ms window after yielding to shutter events. Neither snap played on any head. The requested hit at 1:43.94 also dropped on all four heads because the section was held dark. |
| Export offset is small and consistent | Comparing one-second waveform samples against the source at eight positions from 0:05 to 4:05 found the preview audio 24 ms early at every position. There was no accumulating audio offset at the sampled points. |

## Cause of the long darkness

`coordination_schedule` steps through the layout graph in order for `RIPPLE`
and `SEQUENCED`, even when a section's plan names only a few participating
groups. Dance Jams has 126 graph entries. The moving-head group is 85th, and the
two affected sections have 36 and 40 steps. The ripple never activated either of
its named lead or support groups. The sequence omitted its named spinner support
and gave the named verticals and mega tree only one step apiece. Display effects
outside these windows were clipped after planning, and the renderer commanded the
heads dark for the entire passage. In a schedule-only experiment, changing just
those two modes to `COMPLEMENTARY` removed the 35.32-second rest. That experiment
isolates the scheduling cause and has no revised video or quality verdict.

The saved plans for the other two songs reproduce the same failure. Need A Favor
holds the heads dark through the ripple chorus from 2:40.000 to 3:12.140,
and the house has no cues from 2:41.520 to 3:13.420. This is in addition to the
previously documented beat-grid limit. Hey Come Look At My House holds the heads
dark from 0:46.420 to 1:10.640 under ripple and from 1:57.560 to 2:20.320 under
sequenced coordination. In each of these passages, the house also has a cue gap
longer than 12 seconds. These checks compare the emitted files and saved
schedules. The waveform comparisons above were run on Dance Jams.

## Recovery handoff

1. Reproduce the blackout with a synthetic graph larger than the section's beat
   count. Make the test exercise scheduled targets, the display foundation after
   clipping, and the moving-head rest spans. Preserve the accepted behavior for
   typed call/response pairs and explicit rests.
2. Verify musical anchors against the actual audio for this mix. Include the
   1:51.6 change and the two dropped entry snaps in the replay checks. Distinguish
   a misplaced audio boundary from a cue that vanished after planning.
3. Render and review Dance Jams again against the music in xLights before using
   this path for the other songs. Capture timestamped checks of intended blackouts,
   major transitions, and house and moving-head coverage.

The product and released videos are unchanged by this audit. No replacement
sequence has passed visual or musical review.
