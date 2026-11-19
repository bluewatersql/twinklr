---
type: evidence
status: active
area: display-rendering
updated: 2026-11-19
---

# House musical synchronization repair

The owner rejected the recovered house previews: unrelated flashes and missing
musical transitions, while the moving heads looked closer to sync. This overrides
any implication that waveform alignment or whole-song light coverage established
musical quality. The rejected artifacts remain under
`~/xlights/_twinklr_verify/recovery-review-2026-11-19/`.

## Reproduced causes

- A declared RHYTHM PULSE compiled to the same free-running effect without the
  detected grid or lane timing driver. BEATS and BARS produced the same output.
- Coordination reapplied the 300 ms rhythmic fade to short beat windows. In the
  rejected XSQ, a 300 ms fade was written into each short rhythmic window.
  The first pixel audit also included diagnostic moving-head dots; its peak-delay
  numbers are not accepted as isolated house timing evidence.
- The macro CUT at 18.065 s retained a one-second BASE fade in the rejected XSQ.
  A replay assertion failed on that exported fade.
- House planning manufactured bars from nominal tempo, while composition used
  detected bars/beats. The planner also lost lyric timestamps and MomentCues and
  did not receive audio-profile musical objectives. Moving-head planning already
  consumed richer musical evidence.

## Repair and regressions

`ec0ffb6e`, `10b90aa5`, and `3ed4f234` carry the repair. Only explicit PULSE, or
SPARKLE tagged beat/offbeat, gets a detected-clock brightness envelope in RHYTHM.
BEATS and BARS use their own clocks; half-time and offbeat tags retain their
cadence. Ordinary spatial/decorative layers keep their motion. The absolute
envelope survives coordination slicing and is clipped into each emitted xLights
brightness curve. The effect's intensity and focal-role brightness still apply.

CUT removes incoming and outgoing section fades, including a floored outgoing
end at a non-frame-aligned boundary. Sliced effects no longer restart arrival
fades. Planner timing uses the renderer's detected references. Planning,
refinement and section judging receive timestamped cues, profile objectives,
section dynamics, nearest-beat offsets and the section's detected beat table.
No planner-output schema or moving-head implementation changes.

Red-to-green regressions cover irregular beats, BARS, half-time, offbeat,
untimed sparkle, preservation of rolling layers, absolute-phase slicing, CUT,
timed cue retention and shared planning/judge evidence. Review added cases with
CUT at 2,211 ms, a bar at 2,005 ms beside beat 2,000 ms, and a section/bar at
2,011 ms beside beat 2,000 ms. Live planning exposed the related false rejection
of a frame-rounded first beat at 18,060 ms against raw section start 18,065 ms.
Those failures are repaired without asking the LLM to move the mandatory base.

## Independent review

`/root/pickup_review` reviewed immutable commits independently, read-only.
Initial verdict: changes requested for the outgoing CUT frame and pulse anchor.
Second verdict: changes requested for admissible first-beat bounds.
Final verdict at `3ed4f234`: approved for code correctness; all nine stage-pipeline
regressions passed independently. Earlier independent narrow suites passed 418
and 423 tests. This is not a rendered look verdict.

## Scratch replay and live planning

Scratch root: `~/xlights/_twinklr_verify/house-sync-2026-11-19/`.
`rerender.py`, `replan.py`, `export-wide.py`, measurement scripts, saved plans,
source-input references, and generated outputs remain local and untracked.
The original moving-head XML and existing EffectDB/ColorPalettes prefixes are
preserved exactly. The production layout/network hashes are checked after
xLights export. Physical fixture output stays disabled.

A saved-plan diagnostic replay precedes fresh planning, so its difference is the
renderer repair. In Dance Jams, 39/40 strongest masked house-region brightness rises
were within 40 ms of a detected beat (rejected replay: 23/40). It does not prove
all light changes are musical: textures can move independently, an offbeat can be
intentional, and Strobe still selects pixels randomly. The mask excludes both moving heads and their indicator dots. The saved-plan diagnostic
is retained separately under `saved-plan-diagnostic/`.

Fresh house-only planning uses the three authorized cached song analyses, audio
profiles, macro plans and grids. Favor also has a retained lyric-analysis model.
Dance and Hey have no retained lyric-analysis model in this run, so their musical
context uses the audio profile. Provider purpose: exercise the repaired musical
context and choose responses, not rerun audio/MH analysis. Approval is recorded
in the implementation brief (2026-11-13 and 2026-11-19 rows). Completed sections
are retained; failed validation is investigated before retrying. Two planner
iterations per section attempt. Early failed attempts encountered the frame-bound
bug above. Favor's old cached SongBundle has a retired `coverage_pct` lyric-quality
key, removed only in the scratch replay reader; the cached file is unchanged.

## Final verification

All 28 fresh sections planned successfully (Dance 14, Favor 7, Hey 7), and all three
sequences exported and decoded. Verification retained exact MH XML/DB prefixes,
29,842 decoded frames and 588 audio windows with zero offset. Frame comparisons
show visible house changes at Dance 18.06, 23.64, 31.62, 44.04 seconds and Hey 93.32,
107.06,107.48 seconds. These are timing observations, not a taste verdict.

The same check found Favor verse_1's particle hits at 43.04, 45.32, 54.40 barely
changed the house. xLights Meteors builds a particle population; its native
warmup experiment improved pixel activity slightly but did not make those
reliable impacts. It is not being added to production. Source:
[xLights Meteors](https://raw.githubusercontent.com/xLightsSequencer/xLights/master/src-core/effects/MeteorsEffect.cpp).
The recipe construction was already shaped but absent from the prompts. A narrow
follow-up displays ACCENT constructions and instructs planning/judging to use an
available solid-fill HIT (On or Color Wash) for an indispensable immediate arrival, with motif textures
as companions. Only the failed Favor verse was replanned; its first plan and video remain retained.
The replacement explicitly holds the 43.04 s energy sag instead of claiming a particle
hit there, starts a sustained call/response at 45.32 s, and places a visible windows
impact at 54.40 s. In a house-only ROI, that 54.40 s boundary changed 155 pixels by at
least 20 levels, versus zero in the first attempt. The 32.42 s arrival and 96.20 s chorus
also change visibly. `final-verification.json` and cue contact sheets retain the
frame comparisons. This establishes those selected responses, not every possible
musical event or a human taste verdict.

The first complete full gate at `3ed4f234` reported 4 failures, 7811 passes and 30 skips:
three old populated-prompt contexts lacked the new optional musical_context field,
and the current display replay's EffectDB count changed 30→32. Optional guards are
fixed. A hermetic control with the new pulse compiler disabled restores exactly 30;
with it enabled, four unfaded settings variants replace two old variants (net+2).
All other replay metrics are identical. Only that current replay metric is updated;
the historical XSQ, original metrics and recipe snapshot remain unchanged.
The follow-up targeted suite passed 479 tests. Independent follow-up review approved
519037b2 plus the solid-fill wording correction, with 48 independently passing
prompt/context/replay checks and 7 passing corrected-wording prompt tests.
The all-CUT audit then found Favor's final verse at 192.133 s had no incoming
foundation until 193.400 s. `bf52c987` makes BASE/SECTION placements starting at
bar 1 beat 1 cover the audio section's actual edges; explicit later placements and
other lanes keep their detected references. Independent review caught a 20 ms gap
when the outgoing edge floored but the incoming edge rounded upward. `a5e52265`
quantizes shared foundation edges consistently, retaining the song-duration cap.
The reviewer approved the final delta after 237 independent composition,
coordination and replay tests. All 11 requested CUT starts now have immediate
unfaded house events (Dance 4, Favor 4, Hey 3), including Favor at 192.140 s.
No fallback substitutions were used. Final full-gate result follows below.

Prior gate attempts: a sequential run was interrupted to use parallel workers;
the first parallel command failed before tests because `uv sync` had pruned the
local pytest-xdist installation. Restoring xdist in the local environment and
using `UV_NO_SYNC=1 UV_OFFLINE=1` resolved that environment issue. Intermediate gates were explicitly stopped when rendered CUT audits and
independent review found the partial-bar and shared-frame foundation defects.
These interrupted runs are not passing validation evidence. The final command uses `PYTEST_ADDOPTS='-n 8 --dist loadfile' make validate`;
its final snapshot and result are recorded below.

## Final artifacts and render checks

Final render source: `a5e52265`. All three saved new plans were replayed after
that commit and exported through xLights 2026.20. The 11 CUT starts were checked
against the final trace and native effect settings; all have incoming events and
no incoming fade. Favor's final verse now changes 1,168 house pixels at 192.140 s,
instead of waiting until 193.400 s. Contact sheets were inspected for each song.
The final videos retain 29,842 frames; 588 half-second audio windows sampled
throughout the songs all measure 0 ms offset (minimum correlation 0.978).
Moving-head XML and existing effect/palette prefixes match the original exactly.
The full videos and comparison clip decode without errors.

Local artifacts beneath the scratch root:

- `previews/dance-before-after.mp4`: 36-second comparison, song time 16–52 s;
  rejected render left, repaired render right, current source audio.
- `previews/dance-house-preview.mp4`
- `previews/favor-house-preview.mp4`
- `previews/hey-house-preview.mp4`
- `sequences/`: three corresponding XSQs with trace/evaluation sidecars.
- `final-verification.json`, `cut-verification.json`, `*-cue-contact.png`:
  final technical observations, not owner look judgments.
- `export-final.log`, `verify-final.log`, `rerender-final.log`: final run logs.
- `delivery-manifest.json`: source commit, artifact sizes and SHA-256 hashes.

xLights fixture output stayed off. The widened preview pane was restored after
export through CUA (divider 1450→513, followed by an accessibility-state read).
The automation API returned `xLights closed.`. A later process check confirmed
xLights absent (`post-close-verification.log`), and SHA-256 checks of the production
`xlights_rgbeffects.xml` and `xlights_networks.xml` both passed again after close.

## Completion gate

PASS: clean-tree source snapshot `a5e52265`, command
`UV_NO_SYNC=1 UV_OFFLINE=1 PYTEST_ADDOPTS='-n 8 --dist loadfile' make validate`.
Result: 7,818 passed, 30 skipped, 43 warnings in 737.29 seconds; 91% coverage.
Formatting left all 1,321 files unchanged; lint passed; mypy passed 661 source files.
Exit status 0. Full log retained at the scratch root as
`make-validate-a5e52265.log`. No source edits followed this gate; final changes are
documentation only. Generated root test/lint/type/coverage caches were moved to
Trash afterward (`cleanup.json`); deliverables and reproducibility evidence remain.
The prior recovery branch was already merged and removed. Integration follows the
owner's recorded commit/merge/sync instruction; the completed feature branch is
removed after the fast-forward to `main`.

## Limits and owner verdict

The previous previews remain **REJECTED**. New previews need an owner look
judgment; none is fabricated here. No hardware run or new sealed proof.
Placement timing_hint and recipe timing_offset_beats are outside this repair;
the rejected saved placements all used ON_BEAT. Untimed decorative effects are
not made beat-synchronous by this change. The detected clock itself is retained;
this repair does not claim a new beat-tracking or calibration result.
