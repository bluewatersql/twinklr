---
type: evidence
status: recorded
area: moving-heads
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Three-song house and moving-head previews

**Quality review failed.** The owner reported long dark stretches, poor sync, and
missed transitions. The original verification checked export and playback.
The [Dance Jams audit](dance-jams-quality-audit.md) confirms those failures in
the sequence itself. The clips remain evidence of that run. The
[repair record](repaired-previews.md) links the checked replacement results.

On 2026-11-19, `twinklr show` completed for three songs using Claude Opus 5.5 and
the owner's four-head fixture config. Need A Favor and Dance Jams were named in
current test evidence. Hey Come Look At My House was chosen based on its earlier
house preview. All sequences parsed and contained timed effects for house targets
and each of the four heads. Checked that effect starts and ends were ordered.

| Song | House targets | House effects | Moving-head effects | Preview |
|---|---:|---:|---:|---|
| Need A Favor | 25 | 149 | 25,571 | `need-a-favor-house-preview.mp4`, 197.40 s |
| Dance Jams Final Audio | 40 | 327 | 35,585 | `dance-jams-house-preview.mp4`, 258.52 s |
| Hey Come Look At My House | 20 | 186 | 18,722 | `hey-come-look-house-preview.mp4`, 140.92 s |

The owner-local output folder is
`/Users/ondeck/xlights/_twinklr_verify/combined-review-2026-11-19.K7zqs48A`.
The `sequences/` folder contains the combined `*_twinklr_show.xsq` files and
their manifests. The `previews/` folder contains the 1280×720 H.264 MP4s with
AAC audio exported from xLights 2026.20. FFmpeg decoded both streams in full for
all three files. The xLights instance was closed after export, and SHA-256 checks
confirmed the production layout and network XML files matched their starting
hashes. No fixture output was enabled.

## Run corrections and limitations

- Combined preflight rejected seven overlapping control aliases in the copied
  layout. The scratch layout retains `90 - Moving Heads` as sole owner of four
  physical fixtures and preserves the house display models.
- On the first Need A Favor attempt, aggregation passed 15 distinct narrative
  asset directives into a song-level field that accepts four. Commit `52ef1a10`
  shares the model's cap with aggregation and extraction, applies it after
  deduplication, and retains references to the selected assets from later sections.
  The completed run retained four of 18 directives. Some retry stages re-ran live
  because their cache keys changed.
- The provider returned contradictory macro assignments. Before rendering,
  the scratch runner preserved explicit group roles on overlaps and kept the
  broad role for the other groups. It did so in Need A Favor's intro
  (mega-tree star and house floods), first chorus (mega tree), and third verse
  (mega-tree star), in Dance Jams' fourth verse (mega-tree star), and in Hey Come
  Look At My House's first verse (matrices). In the latter song's bridge, it
  removed a call/response pair that conflicted with the declared `SEQUENCED`
  mode. All adjusted plans passed the existing strict coordination validator.
  The product validator and the original provider output were preserved.
- Need A Favor's moving-head beat grid ended at 187.3 s, 10.1 s before the audio
  ended, leaving the final moving-head verse unplanned. The house sequence and
  the preview reached the end of the audio.

## Validation and cleanup

The aggregation regression reproduced the original stage failure before the
fix. The focused group-planner checks passed 48 tests after the fix, and an
independent reviewer approved the change. A clean detached checkout at
`52ef1a10` passed `make validate` on 2026-11-19 using six Pytest workers and
the Anthropic dependencies. Format, lint, and mypy passed. Pytest reported
7,787 passed, 30 skipped, 49 warnings, and 91% coverage.

Eleven retired worktrees and obsolete generated logs, preview renders, and test
artifacts went to Trash. Six exact historical tips are retained in the local
`refs/archive/twinklr-cleanup-2026-11-19/` namespace. The requested sequences,
videos, and scratch show inputs remain available.

[Scope and authorization](../../plan/combined-review-2026-11-19.md)
