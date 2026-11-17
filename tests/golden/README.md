# Golden output pins

| File | Behavior pinned |
|---|---|
| `test_combined_show_golden.py` | One coordinated sequence: the display effects (type, time ranges, settings and palette strings, and their trace entries without shared-table indices) against `fixtures/combined_show_drop.json` and `fixtures/combined_show_drop.trace.json`; the moving heads' render by its fingerprint, effect count and the hash of its effects and trace entries; and the display's call windows equal to the spans the heads rest dark over |
| `test_xsq_round_trip.py` | `parse → export → parse` over the repo's first tracked `.xsq` |
| `test_preview_render_local.py` | LOCAL-ONLY smoke test of a windowed xLights preview export |

Moving-head output of every catalog family is pinned in
`tests/regression/test_mh_pins.py`.

The golden suite of the removed second moving-head renderer (per-rig settings-string
goldens, its harness and its xLights acceptance suite) was deleted with that renderer in
the C1.2 cutover (`changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-2-deletion/`); it
remains in Git history at commit `5d50580c`.

A combined-show golden changes only with an intended output change: regenerate it from
the test's `_build_combined` and `_snapshot`, and say in the commit which change it records.
