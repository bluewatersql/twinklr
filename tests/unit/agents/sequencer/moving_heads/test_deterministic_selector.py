"""P2P-T13 deterministic selector: projecting the planning context onto its sections.

Selection over the admitted families is tested in `test_deterministic_selector_admission.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from twinklr.core.agents.sequencer.moving_heads.deterministic_selector import (
    SelectorSection,
    selector_sections_from_context,
)


def test_selector_context_projection_converts_fractional_energy_and_uses_resolved_bars() -> None:
    context = SimpleNamespace(
        audio_profile=SimpleNamespace(
            energy_profile=SimpleNamespace(
                section_profiles=[SimpleNamespace(section_id="chorus_1", mean_energy=0.704)]
            )
        ),
        for_prompt=lambda: {
            "song_structure": {
                "sections": [
                    {
                        "section_id": "chorus_1",
                        "name": "chorus",
                        "start_bar": 9,
                        "end_bar": 16,
                    }
                ]
            }
        },
    )

    assert selector_sections_from_context(context) == [
        SelectorSection(section_id="chorus_1", role="chorus", start_bar=9, end_bar=16, energy=70)
    ]
