---
type: review
status: proposed
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-13
updated: 2026-11-13
---

# P1 expendable-show xLights render request — 2026-11-13

**Outcome: PENDING-OWNER.** Nothing here has been opened in xLights. This is a request
for an owner-authorized render in an expendable show folder (never a running or
production show), to check that xLights carries the physical renderer's output as
Twinklr encodes it. It is not a transport acceptance, a physical arrival/settle check
or a look judgment; those stay `PENDING-OWNER` until observed.

## What to check

1. **16-bit carries.** Pan is written as a coarse/fine pair (channels 1 and 2). During
   the first cue the coarse byte steps up by one at every listed carry while the fine
   byte wraps, with no frame where the reconstructed word (`coarse * 256 + fine`) jumps
   backwards or by a whole coarse step.
2. **Channel 17.** The shutter is on model channel 17: byte 8 (open) on every cue
   frame, byte 64 (closed) elsewhere. A value of 0 on channel 17 anywhere means xLights
   dropped the slider, which is the failure this checks.
3. **Sliders 17-48.** The second sequence widens each footprint to 48 channels and sets
   channels 19-48 to the marker byte equal to their channel number (19 → 19 … 48 → 48)
   on every frame. Every one of them must arrive unchanged; 0 means xLights fell back to
   its default for an absent or ignored slider.
4. **Effect count.** Each model carries 101 constant DMX effects (202 per sequence), one
   per run of identical 20 ms frames. A different count means xLights merged, split or
   dropped effects on import.

## Setup the owner provides

- An expendable show folder with two DMX models named exactly `Dmx MH1` and `Dmx MH2`,
  each a single-color DMX model (`DisplayAs` starting `Dmx`) with at least 48 channels,
  on start channels that do not overlap.
- Any 3.62-second audio file as the sequence's media (the sequences name
  `silence.wav`); no audio content matters.
- The xLights version used, recorded with the result.

## Producing the sequences

From the repository root at the reviewed P1.6 commit, with the script below saved
outside the repository (it imports the in-repo test support, as P0's collection script
did):

```bash
PYTHONPATH=. uv run python <script> <out_dir>
```

It writes `p1_linear_reveal.xsq` (18-channel footprint) and `p1_linear_reveal_48ch.xsq`
(48-channel footprint), each with its `.xsq.trace.json`, `.xmap`, `.xtiming` and the
exact fixture config it rendered (`<name>.fixtures.json`), and prints the tables below.
The case is synthetic: P0's variable-tempo grid (500 ms beats in bar 1, 400 ms in bar
2) moved 15 ms off the frame grid, the test-only `p1_linear_reveal` template (two dark
beats, then a reveal at full dimmer with the shutter open while pan moves linearly
from -45° toward +45° over two beats), and both heads starting known, settled and dark at pan 0°,
tilt 0°. Run on this worktree before commit, the 18-channel sequence's render
fingerprint was `4bd67b39cc934912847c07d2c109a01c2fd36257d211c34c612e6e2db07f00fc` and
the 48-channel one's `458826581adea7e742598c113a6576ac1f9873caac9e035eded7e1d7834aa2d8`;
re-run the script at the reviewed commit and use its output if they differ.

## Synthetic profiles

`MH1` uses this profile (from `tests/support/mh_physical.py::physical_head_profile`);
`MH2` is identical except `"inverted": true` on `pan` and `tilt`, so its pan/tilt words
are the 16-bit complement of `MH1`'s. Every value is synthetic test input, not a
calibration or manufacturer fact.

```json
{
  "schema_version": "1",
  "profile_id": "synthetic_spot",
  "provenance": "synthetic",
  "footprint": 18,
  "defaults": {
    "1": 128,
    "2": 0,
    "3": 128,
    "4": 0,
    "5": 0,
    "6": 64,
    "7": 0,
    "8": 0,
    "9": 0,
    "10": 0,
    "11": 0,
    "12": 0,
    "13": 0,
    "14": 0,
    "15": 0,
    "16": 0,
    "17": 64,
    "18": 0
  },
  "axes": {
    "pan": {
      "unit": "degree",
      "physical_min": -270.0,
      "physical_max": 270.0,
      "allowed_min": null,
      "allowed_max": null,
      "coarse_offset": 1,
      "fine_offset": 2,
      "inverted": false,
      "travel_speed_per_s": 720.0,
      "latency_ms": 0,
      "settle_ms": 40
    },
    "tilt": {
      "unit": "degree",
      "physical_min": -135.0,
      "physical_max": 135.0,
      "allowed_min": null,
      "allowed_max": null,
      "coarse_offset": 3,
      "fine_offset": 4,
      "inverted": false,
      "travel_speed_per_s": 720.0,
      "latency_ms": 0,
      "settle_ms": 40
    },
    "dimmer": {
      "unit": "normalized",
      "physical_min": 0.0,
      "physical_max": 1.0,
      "allowed_min": null,
      "allowed_max": null,
      "coarse_offset": 5,
      "fine_offset": null,
      "inverted": false,
      "travel_speed_per_s": null,
      "latency_ms": null,
      "settle_ms": null
    }
  },
  "discrete": {
    "shutter": {
      "offset": 17,
      "states": {
        "closed": {
          "range_min": 60,
          "range_max": 95,
          "value": 64,
          "settle_ms": 0
        },
        "open": {
          "range_min": 0,
          "range_max": 31,
          "value": 8,
          "settle_ms": 0
        }
      },
      "default_state": "closed",
      "closed_state": "closed",
      "open_state": "open"
    },
    "color": {
      "offset": 7,
      "states": {
        "white": {
          "range_min": 0,
          "range_max": 9,
          "value": 0,
          "settle_ms": 120
        },
        "red": {
          "range_min": 10,
          "range_max": 19,
          "value": 14,
          "settle_ms": 120
        },
        "blue": {
          "range_min": 20,
          "range_max": 29,
          "value": 26,
          "settle_ms": 140
        }
      },
      "default_state": "white",
      "closed_state": null,
      "open_state": null
    },
    "gobo": {
      "offset": 18,
      "states": {
        "open": {
          "range_min": 0,
          "range_max": 7,
          "value": 0,
          "settle_ms": 150
        },
        "dots": {
          "range_min": 8,
          "range_max": 15,
          "value": 10,
          "settle_ms": 150
        },
        "star": {
          "range_min": 16,
          "range_max": 23,
          "value": 20,
          "settle_ms": 160
        }
      },
      "default_state": "open",
      "closed_state": null,
      "open_state": null
    }
  },
  "visibility": {
    "dimmer_zero_extinguishes": true,
    "extinguishing_shutter_states": [
      "closed"
    ],
    "close_latency_ms": 0,
    "open_latency_ms": 0
  }
}
```

Job policy: schema `3.1`, `moving_heads.mode` `physical_v2`, and for both heads the
initial state `pan_deg 0, tilt_deg 0, dimmer 0, shutter closed, color white, gobo open,
settled, dark`. Budgets at their defaults.

## Expected frames

Bytes at frame starts (ms), identical in both sequences for channels 1-18. Frames
sample `[start, end)`, so +45° is the kernel's value at a cue's end and is never itself
commanded: the first cue's last frame (2000 ms) commands about 43.2°, and the second
cue, cut at 3600 ms, ends lower. Cues are
`[1020, 2020)` and `[2820, 3600)`; `[3600, 3620)` is the final partial frame, parked
dark (the second cue's musical end, 3615 ms, runs past the song's last whole frame and
is truncated at 3600 ms by design).

| Frame | MH1 pan (1,2) | MH1 tilt (3,4) | MH1 dimmer (5) | MH1 ch17 | MH2 pan (1,2) | MH2 tilt (3,4) | MH2 dimmer (5) | MH2 ch17 |
|---|---|---|---|---|---|---|---|---|
| 0 | 122,170 | 130,95 | 0 | 64 | 133,85 | 125,160 | 0 | 64 |
| 1000 | 106,170 | 137,123 | 0 | 64 | 149,85 | 118,132 | 0 | 64 |
| 1020 | 106,170 | 137,123 | 255 | 8 | 149,85 | 118,132 | 255 | 8 |
| 1040 | 107,133 | 137,123 | 255 | 8 | 148,122 | 118,132 | 255 | 8 |
| 2000 | 148,122 | 137,123 | 255 | 8 | 107,133 | 118,132 | 255 | 8 |
| 2020 | 142,128 | 137,123 | 0 | 64 | 113,127 | 118,132 | 0 | 64 |
| 2800 | 106,170 | 137,123 | 0 | 64 | 149,85 | 118,132 | 0 | 64 |
| 2820 | 106,170 | 137,123 | 255 | 8 | 149,85 | 118,132 | 255 | 8 |
| 3580 | 147,51 | 137,123 | 255 | 8 | 108,204 | 118,132 | 255 | 8 |
| 3600 | 147,51 | 137,123 | 0 | 64 | 108,204 | 118,132 | 0 | 64 |

Channel 18 (gobo) is 0 on every frame. In the 48-channel sequence, channel `n` is `n`
for every `n` in 19-48 on every frame.

Coarse-byte carries during the first cue (`MH1`; `MH2` mirrors them downward), as
`frame: previous (coarse,fine) -> (coarse,fine)`, are on every frame from 1040 to 2000
except 1120, 1260, 1400, 1540, 1660, 1800 and 1940, for example
`1520: 127,37 -> 128,0`, `1540: 128,0 -> 128,218` (no carry) and
`1560: 128,218 -> 129,180`. The script prints the full list.

## How to report

Record, in this file or a dated sibling: the commit rendered, the xLights version, how
the per-frame channel values were read (the method is the owner's choice), and for each
of the four checks either the matching values or the first differing frame, model,
channel and value. Until then the outcome above stays `PENDING-OWNER`.

## Script

Kept here as text so the repository's lint and type gates do not treat it as source.

```python
"""Write the P1 expendable-show request sequences and print their check tables."""
import json
import sys
from pathlib import Path

from tests.support.mh_physical import (
    physical_grid, physical_job, physical_plan, physical_rig, physical_test_templates,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)


def rig_48() -> FixtureGroup:
    """The same rig, each footprint widened to 48 with marker defaults 19..48 = offset."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["footprint"] = 48
        profile["defaults"] |= {str(offset): offset for offset in range(19, 49)}
    return FixtureGroup.model_validate(payload)


with physical_test_templates():
    for name, rig in (("p1_linear_reveal", physical_rig()), ("p1_linear_reveal_48ch", rig_48())):
        (out_dir / f"{name}.fixtures.json").write_text(rig.model_dump_json(indent=2))
        pipeline = RenderingPipeline(
            choreography_plan=physical_plan(), beat_grid=physical_grid(), fixture_group=rig,
            job_config=physical_job(), output_path=out_dir / f"{name}.xsq", media_file="silence.wav",
        )
        pipeline.render()
        render = json.loads((out_dir / f"{name}.xsq.trace.json").read_text())["render"]
        print(f"## {name}: fingerprint {render['render_fingerprint']}")
        print(f"effects {render['output']['effect_count']}, bytes {render['output']['xsq_bytes']}")
        frames = {(f.fixture_id, f.time_ms): dict(f.channels) for f in pipeline.frames}
        for fixture_id in ("MH1", "MH2"):
            runs = sum(1 for e in json.loads((out_dir / f"{name}.xsq.trace.json").read_text())["entries"] if e["group_id"] == f"Dmx {fixture_id}")
            print(f"{fixture_id}: {runs} effects")
            previous = None
            for t in range(0, 3620, 20):
                b = frames[(fixture_id, t)]
                if previous is not None and b[1] != previous[1] and 1020 <= t < 2020:
                    print(f"  carry at {t}: prev pan {previous[1]},{previous[2]} -> {b[1]},{b[2]}")
                previous = b
            for t in (0, 980, 1000, 1020, 1040, 2000, 2020, 2800, 2820, 3580, 3600):
                b = frames[(fixture_id, t)]
                print(f"  {t}: pan {b[1]},{b[2]} tilt {b[3]},{b[4]} dimmer {b[5]} ch17 {b[17]} ch18 {b[18]}"
                      + (f" ch19 {b[19]} ch48 {b[48]}" if 48 in b else ""))
```
