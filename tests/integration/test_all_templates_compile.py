"""Every built-in template compiles, on both tracked rigs, at every energy preset.

Closes review §12 runtime item 7. This is the end-to-end counterpart to the
handler-level matrix in `tests/unit/sequencer/moving_heads/test_movement_intensity.py`.
The movement handler renders every step at `Intensity.SMOOTH` unless the step's
movement params carry an `intensity` key: P1P-T3 reconnected the preset's intensity
(P4-F1), and that was reverted on 2026-11-12 at the owner's request.

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


@pytest.fixture(scope="module")
def template_ids() -> list[str]:
    load_builtin_templates()
    ids = sorted(info.template_id for info in list_templates())
    assert len(ids) == 37, f"expected 37 built-in templates, found {len(ids)}"
    return ids


@pytest.mark.parametrize("rig_id", RIG_IDS)
@pytest.mark.parametrize("preset_id", ENERGY_PRESETS)
def test_all_templates_compile(rig_id: str, preset_id: str, template_ids: list[str]) -> None:
    """No template raises for either rig at any energy preset, and both emit DMX.

    This asserted compilation only for `mh8_reference` until P1P-T5: the 8-head rig
    emitted transitions and no section effects at all, because `_infer_fixture_role`
    gave rigs larger than four positional names matching no template role and the
    role filter then skipped every step in silence (P4-F26). Both rigs now have to
    emit, which is the assertion that would have caught it.
    """
    failures: list[str] = []
    silent: list[str] = []
    for template_id in template_ids:
        try:
            effects = render_single_section(
                RIGS[rig_id], template_id=template_id, preset_id=preset_id
            )
        except Exception as error:
            failures.append(f"{template_id}: {type(error).__name__}: {error}")
            continue
        if not effects:
            silent.append(template_id)

    assert not failures, (
        f"{len(failures)} of {len(template_ids)} templates raised on {rig_id} "
        f"at preset '{preset_id}':\n  " + "\n  ".join(failures)
    )
    assert not silent, f"templates emitted nothing on {rig_id} at preset '{preset_id}': {silent}"


@pytest.mark.parametrize("preset_id", ENERGY_PRESETS)
def test_all_templates_emit_effects_on_the_reference_rig(
    preset_id: str, template_ids: list[str]
) -> None:
    """Compiling without raising is not enough — the 4-head rig must emit DMX."""
    silent = [
        template_id
        for template_id in template_ids
        if not render_single_section(
            RIGS["mh4_minimal"], template_id=template_id, preset_id=preset_id
        )
    ]
    assert not silent, f"templates emitted nothing at preset '{preset_id}': {silent}"


def test_energy_preset_does_not_change_the_emitted_movement() -> None:
    """P4-F1 reverted on 2026-11-12: movement renders the SMOOTH entry at every preset.

    `sweep_lr_fan_hold` holds its dimmer, so the movement curve is the only thing a
    preset could change. The handler reads intensity from the step's movement params,
    which shipped templates never populate, so all four presets emit one payload --
    the look the owner accepted in xLights.
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

    assert len(set(payloads.values())) == 1, (
        f"{len(ENERGY_PRESETS)} energy presets produced "
        f"{len(set(payloads.values()))} distinct payloads"
    )
