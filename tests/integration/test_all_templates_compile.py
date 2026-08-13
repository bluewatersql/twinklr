"""Every built-in template compiles, on both tracked rigs, at every energy preset.

Closes review §12 runtime item 7. This is the end-to-end counterpart to the
handler-level matrix in `tests/unit/sequencer/moving_heads/test_movement_intensity.py`:
before P1P-T3 the movement handler pinned every step to `Intensity.SMOOTH`, so the
non-SMOOTH entries of the movement library were never exercised by a render — and
27 of the 29 patterns had no such entries to exercise. Any preset other than
`moderate` would have raised `KeyError` the moment intensity was reconnected.

Rigs and the deterministic single-section render come from the P1P-T1 golden
harness, so this test and the goldens describe the same pipeline.
"""

from __future__ import annotations

import pytest

from tests.golden.harness import RIGS, render_single_section
from twinklr.core.sequencer.moving_heads.pipeline import ENERGY_TO_INTENSITY
from twinklr.core.sequencer.moving_heads.templates import (
    list_templates,
    load_builtin_templates,
)

# Preset ids the pipeline maps onto the movement intensity ladder, lower-cased
# because that is how plans name them.
ENERGY_PRESETS = sorted(keyword.lower() for keyword in ENERGY_TO_INTENSITY)

RIG_IDS = ["mh4_minimal", "mh8_reference"]

# `render_single_section` renders a 4-bar window; this template's cycle is 8 bars,
# so the scheduler emits nothing for it ("Section window shorter than cycle").
# That is a scheduler/time-grid concern, not a compile failure — recorded here,
# owned by the scheduler tasks.
LONGER_THAN_THE_WINDOW = {"ambient_random_wash"}


@pytest.fixture(scope="module")
def template_ids() -> list[str]:
    load_builtin_templates()
    ids = sorted(info.template_id for info in list_templates())
    assert len(ids) == 37, f"expected 37 built-in templates, found {len(ids)}"
    return ids


@pytest.mark.parametrize("rig_id", RIG_IDS)
@pytest.mark.parametrize("preset_id", ENERGY_PRESETS)
def test_all_templates_compile(rig_id: str, preset_id: str, template_ids: list[str]) -> None:
    """No template raises for either rig at any energy preset.

    Only compilation is asserted for `mh8_reference`: the 8-head rig emits
    transitions but no section effects at all, which is why its committed goldens
    contain only transition files. That is pre-existing at the P1P baseline and
    tracked as P4-F26 (the chase ordering is hard-coded for 11 roles / 4 fixtures).
    """
    failures: list[str] = []
    for template_id in template_ids:
        try:
            render_single_section(RIGS[rig_id], template_id=template_id, preset_id=preset_id)
        except Exception as error:
            failures.append(f"{template_id}: {type(error).__name__}: {error}")

    assert not failures, (
        f"{len(failures)} of {len(template_ids)} templates raised on {rig_id} "
        f"at preset '{preset_id}':\n  " + "\n  ".join(failures)
    )


@pytest.mark.parametrize("preset_id", ENERGY_PRESETS)
def test_all_templates_emit_effects_on_the_reference_rig(
    preset_id: str, template_ids: list[str]
) -> None:
    """Compiling without raising is not enough — the 4-head rig must emit DMX."""
    silent = [
        template_id
        for template_id in template_ids
        if template_id not in LONGER_THAN_THE_WINDOW
        and not render_single_section(
            RIGS["mh4_minimal"], template_id=template_id, preset_id=preset_id
        )
    ]
    assert not silent, f"templates emitted nothing at preset '{preset_id}': {silent}"


def test_energy_preset_reaches_the_emitted_movement() -> None:
    """P4-F1 end to end: the plan's energy changes the DMX that leaves the exporter.

    `sweep_lr` carries no `categorical_params` of its own, so it resolves through
    `DEFAULT_MOVEMENT_PARAMS` — the path that used to be pinned to SMOOTH for every
    preset alike. Four distinct payloads mean intensity survives from the plan to
    the wire.
    """
    payloads = {
        preset_id: tuple(
            effect.settings
            for effect in render_single_section(
                RIGS["mh4_minimal"], template_id="sweep_lr_fan_hold", preset_id=preset_id
            )
        )
        for preset_id in ENERGY_PRESETS
    }

    assert len(set(payloads.values())) == len(ENERGY_PRESETS), (
        f"{len(ENERGY_PRESETS)} energy presets collapsed to "
        f"{len(set(payloads.values()))} distinct payloads — intensity is not "
        "reaching the movement curve"
    )
