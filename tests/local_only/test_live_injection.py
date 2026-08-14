"""Owner-only xLights 2026.15 live-injection round trip.

This test is intentionally inert unless every opt-in variable is present. Open a scratch
sequence that you are willing to discard, enable xLights' unauthenticated automation API,
and run:

    TWINKLR_RUN_LIVE_XLIGHTS_INJECTION=1 \
    TWINKLR_XLIGHTS_SCRATCH_SEQUENCE=/absolute/path/scratch.xsq \
    TWINKLR_XLIGHTS_SCRATCH_MODEL='Dmx MH1' \
      uv run pytest tests/local_only/test_live_injection.py -m local_only -q

Never point this at a sequence you care about. Twinklr does not save, but this test
deliberately mutates the open scratch sequence and leaves the injected effect visible.
Disable the unauthenticated API when finished.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from twinklr.core.api.xlights import (
    CheckSequenceRequest,
    LiveEffect,
    LiveInjectionWorkflow,
    MemoryOwnershipStore,
    RenderAllRequest,
    XLightsAutomationClient,
)


@pytest.mark.local_only
@pytest.mark.anyio
async def test_live_injection_round_trip() -> None:
    """Inject one effect only into the explicitly named, already-open scratch sequence."""
    if os.getenv("TWINKLR_RUN_LIVE_XLIGHTS_INJECTION") != "1":
        pytest.skip("set TWINKLR_RUN_LIVE_XLIGHTS_INJECTION=1 for the owner-local run")
    expected_path = os.getenv("TWINKLR_XLIGHTS_SCRATCH_SEQUENCE")
    target = os.getenv("TWINKLR_XLIGHTS_SCRATCH_MODEL")
    if not expected_path or not target:
        pytest.skip("scratch sequence path and model must both be explicit")

    async with XLightsAutomationClient() as client:
        opened = await client.get_open_sequence()
        assert opened.sequence_path.resolve() == Path(expected_path).resolve(), (
            "Refusing to mutate a sequence other than TWINKLR_XLIGHTS_SCRATCH_SEQUENCE"
        )
        workflow = LiveInjectionWorkflow(client, ownership=MemoryOwnershipStore())
        effect = LiveEffect(
            target=target,
            effect="DMX",
            settings="E_SLIDER_DMX1=128",
            palette="",
            start_ms=0,
            end_ms=500,
            section_id="local_smoke",
        )
        result = await workflow.inject((effect,))
        assert result.complete and result.injected == (effect,)
        await client.render_all(RenderAllRequest())
        checked = await client.check_sequence(CheckSequenceRequest(opened.sequence_path))
        assert checked.result_code == 200
