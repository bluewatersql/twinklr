---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# Beat-grid fix: meter, tempo octave and downbeats — 2026-11-16

Local DSP measurements and review results for the audio change the owner directed
after the [first real-audio gate](../2026-11-16-p3-real-audio-gate/README.md). No
provider request was made. No bar placement has been checked by ear; where a bar
starts on any owner song is `PENDING-OWNER`.

## What changed

Commits `5145fb3d`, `8b23a36d`, `16b3e170`, `3431c7ba` on `feat/mh-true-up-p3`
(written on a separate branch, cherry-picked). One implementing agent; two review
rounds by separate agents (each approve with fixes, no critical or high finding) and
a final verification of the last commit by a third.

- **Meter.** Each bar grouping is scored at its best phase, minus the same statistic
  on shuffled beats. 4/4 unless a triple meter beats the best duple by more than 0.10.
  2/4 is no longer reported; duple songs are 4/4. Confidence is the share of shuffles
  the detected accent beats.
- **Tempo octave.** The tracker's tempo is halved only when the loud beats sit exactly
  two tracker beats from the chord changes, both significant against shuffles (a
  backbeat counted as eighth notes), with at least 32 beats and a tracker tempo of at
  least 120 BPM. Never doubled. The decision and its evidence are recorded under
  `time_signature["tempo_octave"]`.
- **Downbeats.** Bars are placed by per-bar votes: chord change first, onset accent as
  the tie-break between two chord beats half a bar apart, and a labelled fallback
  (loudest phase, confidence 0) when nothing is decisive. Chord evidence comes from
  the harmonic component of the audio.
- **Tempo curve.** Derived from the resolved beats. The `tempo_changes` and `is_stable`
  outputs are removed: nothing read them and they no longer described anything on the
  default source (integrator decision; the owner was told and can reverse it).
- **Planner prompt.** The audio profile states meter confidence and bar-placement
  confidence with its method, flags uncertain bar placement in words, and says when a
  tempo was halved. A hard-coded "Tempo Confidence: 1.0" line is removed.
- Audio feature cache version 5 → 7; DSP adapter version `twinklr-dsp-v2`.

Key, chords and structure still read full-mix chroma. Switching them would change the
key on one of ten owner songs and 23–57% of chord labels, with no ground truth to say
whether that is better; left for a separate change.

## Measured

MIR fixtures (five): meter 5 of 5 correct (was 2 of 5); beat F1 0.931 unchanged;
downbeat F1 0.933 (was 0.762). All five still place downbeats by fallback, being too
short to vote; the chord path is covered by synthesized-audio tests.

Owner's `data/music`, before → after:

| Song | Tempo | Meter | Bars | Bar placement after (confidence, method) |
|---|---|---|---|---|
| Need A Favor | 156.6 → 78.3 | 3/4 → 4/4 | 164 → 61 | 0.98, chord change + onset |
| Nuttin' For Christmas | 147.7 | 2/4 → 4/4 | 179 → 90 | 0.98, chord change |
| Wizards in Winter | 147.7 | 2/4 → 4/4 | 199 → 99 | 0.995, chord change |
| Frosty The Snowman | 89.1 | 2/4 → 4/4 | 132 → 66 | 0.0, fallback |
| The Little Drummer Boy | 103.4 | 2/4 → 4/4 | 172 → 86 | 0.995, chord change |
| Happy Holidays (remix) | 95.7 | 2/4 → 4/4 | 123 → 61 | 0.995, chord change |
| Hey Come Look At My House | 147.7 | 2/4 → 4/4 | 167 → 83 | 0.0, fallback |
| fantasmic-edit | 126.0 | 3/4 → 4/4 | 105 → 78 | 0.57, chord change + onset |
| Party Rock Anthem | 129.2 | 4/4 | 140 | 0.0, fallback |
| Dance Jams Final Audio | 129.2 | 4/4 | 135 | 0.0, fallback |

The owner states Need A Favor is 79 BPM in 4/4. Results were identical on repeated
runs by the author and both reviewers. The rhythm step takes 0.5–1.1 s per song (was
0.1–0.25 s).

## Known limits

- Where chords change equally on beats 1 and 3, the louder kick decides which is beat
  1; this is how Need A Favor's bar start is chosen.
- Half-time-feel material at a fast nominal tempo is reported at the felt half tempo.
- A slow song the tracker reads at under 120 BPM is not halved; a fast song the
  tracker itself reads at half tempo stays halved.
- 6/8, 12/8 shuffles and 2/4 are not read correctly; a weakly accented 3/4 can read as
  4/4.
- Bar-placement confidence assumes the tempo is right.
- The thresholds (0.10 meter margin, 8 deciding bars, 32 beats, 0.05 chord-change
  floor) are priors pinned by tests, not calibrated on annotated music.

## Consequences

- Every pipeline sees new bars on real audio where the meter changed: moving heads,
  display sequencing, section boundaries, builds and drops, planner context. No golden
  or regression file changed; they use synthetic grids.
- Every song's cached analysis and plans are invalid; the next run of a song pays for
  its planning calls again.
- The beat-this adoption bar in
  [keep-dsp-after-mir-ab](../../../../memories/decisions/keep-dsp-after-mir-ab.md) moved
  with the downbeat baseline.
- The first real-audio gate result is stale and is rerun on the corrected grid.

## Not verified

Bar placement by ear on any owner song; the three songs left at 147.7 BPM; real-music
accuracy beyond five synthetic fixtures; any effect of the prompt change on live
planning.
