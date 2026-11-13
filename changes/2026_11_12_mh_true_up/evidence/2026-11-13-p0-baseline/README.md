---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-13
updated: 2026-11-13
---

# Phase 0 baseline evidence — 2026-11-13

Offline, synthetic evidence for the Phase 0 exit. It records what the legacy renderer
does today; it is not a physical, xLights or taste result. No provider, owner-local
data, xLights session or hardware was used.

## Commit and gate

- Branch `feat/mh-true-up-p0`, code commit `1631679` (P0-T1 `4c608ac`, P0-T2 `1631679`,
  P0-T3 `afbe160`, P0-T4 `2617525`), cut from `main` at `b498ed9`.
- `make validate` on `1631679`, clean tree before and after: format, lint and type-check
  passed; **5882 passed, 39 skipped**. The 39 skips are opt-in local-only suites.
- Baseline `make validate` on the untouched worktree (`577bf06`): 5763 passed, 39
  skipped. The difference is the 119 tests Phase 0 added.
- `git diff --stat main..1631679 -- tests/golden tests/regression` is empty: no golden
  or regression file changed.
- Environment note: the worktree needed the optional `anthropic` extra installed by
  hand, because `make install` did not include it and one provider test imports it at
  collection. The fix is on `fix/install-anthropic-extra` (`6e9a8cb`), not yet merged.

## How the tables were produced

`PYTHONPATH=. uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-13-p0-baseline/collect.py`
from the worktree root, at `1631679`. The script builds each pipeline with a default
`JobConfig`, reads `RenderingPipeline.diagnostics` and `RenderingPipeline.fingerprint()`,
and renders nothing. Diagnostic counts are per `LegacyControl`.

## Effective-control status: golden rigs

The golden plan on each of the five golden rigs. Every diagnostic is `legacy_ignored`:
the control was requested and the legacy renderer does not apply it.

| Rig | Ignored controls (count) | Fingerprint |
|---|---|---|
| `mh4_minimal` | movement_intensity=5, template_dimmer_floor=2 | `e7b54bfa284ca24f053bb3c3fa313b7162d358e23352174cccf662c8903c236e` |
| `mh4_shutter_in_window` | movement_intensity=5, template_dimmer_floor=2 | `9d1fc7ac9071fef5b882269979ec3f9740a884dd4c695973183babf63654c499` |
| `mh4_shutter_out_of_window` | movement_intensity=5, template_dimmer_floor=2 | `bf745aee715bdf61fab3f98ed0c85aacf23d04f1ea003b7c3ab46bfa20a72808` |
| `mh8_reference` | movement_intensity=5, template_dimmer_floor=2 | `a85517909f36d8458ea0e6987a14f15b9d37a40b62bd5a51b02b7d03d6221de5` |
| `mh4_narrow_calibration` | movement_intensity=5, movement_limits=4, template_dimmer_floor=2 | `26344ee0e31c68d38d4b9ca60fc908a59b2ac2a0ff634ee264a3b482aa9e2ec3` |

`mh4_shutter_out_of_window` maps shutter on channel 17 but the golden plan carries no
shutter intent, so it correctly reports no `shutter_channel_scope`.

## Effective-control status: synthetic cases

| Case | Heads | Legacy outcome | Ignored controls (count) | Fingerprint |
|---|---|---|---|---|
| `counts` | 1 | unsupported_rig_shape | template_dimmer_floor=1 | `4bc2ae27f25ceaf7e80f27119ecb55eec87874d969fd9db790ad49f6c4b1c392` |
| `counts` | 2 | rendered | template_dimmer_floor=1 | `965634f1a43b94e43b65f0fabe032e1e08aadc38322cf8b2219fecd06ead2205` |
| `counts` | 3 | rendered | template_dimmer_floor=1 | `f5b86e203372c7452829c6c0d97faab5bd3095e720863adc87fc821dd3e0bcfa` |
| `counts` | 4 | rendered | template_dimmer_floor=1 | `3166043f6a5575ad9a35631f07f3e0a46c506348120b3d1cca981e69d4a22477` |
| `counts` | 6 | rendered | template_dimmer_floor=1 | `b71cd60e2a2734d19351feb86d0e42507976fc2b47cbcb97773093717cfc7f64` |
| `counts` | 8 | rendered | template_dimmer_floor=1 | `4483db3cdfe2dcc2c34dc02ab2c58a388135a8d6610760320e4a462f068e8786` |
| `fine_carry` | 2 | rendered | pan_tilt_fine=4 | `c0c94adba40c4acbdbe325974e3d93087a442ea919003407c7da5f21f2d29fb7` |
| `channel_edges` | 4 | rendered | shutter_channel_scope=4 | `3e20df6e0eb6cada70adc34026dd10aa81958ffd5924581abc415d100cc2d0c8` |
| `tempo` | 4 | rendered | movement_intensity=1 | `23a5b62bc4ef50cc1cec3c2858a78a9398509939de9b1a9bf29842d3bc3937d9` |
| `meter3` | 4 | rendered | movement_intensity=1 | `a46fa0c1a1d12fe737bec661f0f511ade51c01063f576b21620f6104049cb605` |
| `finite` | 4 | rendered | template_dimmer_floor=1 | `84346ce8cb3dc43f926a8713ab12f8b8a12b3c1215daab270856d153eba2b37d` |
| `state` | input only | - | - | - |
| `locks` | input only | - | - | - |

The 1-head `counts` rig is rejected by the legacy compiler with
`UnsupportedRigShapeError` (the template addresses LEFT and RIGHT). That is the recorded
baseline, not a defect Phase 0 repairs. `state` and `locks` are input definitions for
later phases and are not rendered.

## Reference arm decisions

`build_reference_plan` with seed 41 and every registered template admitted, on a
seven-section synthetic song.

| Section | Role | Energy | Frozen selector's choice | Preferred | Selected | Reason |
|---|---|---|---|---|---|---|
| `intro_1` | intro | 20 | `ambient_random_wash` | `hold_center_out_breathe` | `hold_center_out_breathe` | preferred |
| `verse_2` | verse | 45 | `wave_fan_hold` | `None` | `wave_fan_hold` | baseline |
| `build_3` | build | 60 | `sweep_lr_fan_pulse` | `sweep_lr_fan_hold` | `sweep_lr_fan_hold` | preferred |
| `chorus_4` | chorus | 80 | `build_drop_recover` | `sweep_lr_pingpong_phase` | `sweep_lr_pingpong_phase` | preferred |
| `verse_5` | verse | 45 | `sweep_lr_chevron_breathe` | `None` | `sweep_lr_chevron_breathe` | baseline |
| `chorus_6` | chorus | 85 | `build_drop_recover` | `sweep_lr_pingpong_phase` | `sweep_lr_pingpong_phase` | preferred |
| `outro_7` | outro | 30 | `wave_vertical_spotlight_fade` | `wave_scattered_fade_out` | `wave_scattered_fade_out` | preferred |

## What this does not establish

Fingerprints identify inputs; they are not a hash of rendered output. Nothing here was
opened in xLights, played on a fixture or judged by a person. Physical correctness and
any visual verdict remain `PENDING-OWNER` and belong to later phases.
