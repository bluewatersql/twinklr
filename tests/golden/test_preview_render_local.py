"""LOCAL-ONLY P2P-T5 smoke test for a windowed xLights preview export.

Set ``TWINKLR_XLIGHTS_PREVIEW_SEQUENCE`` to a short, generated ``.xsq`` and run:

    TWINKLR_XLIGHTS_PREVIEW_SEQUENCE=/absolute/path/show.xsq \\
      uv run pytest -m local_only -k preview -q

This is intentionally excluded from CI. It creates a video through a windowed xLights
instance with its HTTP automation API enabled; do not point it at unsaved work.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from twinklr.core.api.xlights import XLightsAutomationClient

pytestmark = pytest.mark.local_only


@pytest.mark.anyio
async def test_live_preview_export() -> None:
    """A real xLights instance exports a non-empty preview video for a short sequence."""
    sequence_value = os.environ.get("TWINKLR_XLIGHTS_PREVIEW_SEQUENCE")
    if sequence_value is None:
        pytest.skip(
            "LOCAL-ONLY: set TWINKLR_XLIGHTS_PREVIEW_SEQUENCE and run with a windowed "
            "xLights 2026.15 instance whose HTTP automation API is enabled."
        )
    sequence_path = Path(sequence_value)
    if not sequence_path.is_file():
        pytest.skip(f"LOCAL-ONLY sequence does not exist: {sequence_path}")

    async with XLightsAutomationClient() as client:
        result = await client.render_preview(sequence_path)

    assert result.video_path.is_file()
    assert result.video_path.stat().st_size > 0
