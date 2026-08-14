"""Typed, local-only integration with xLights' HTTP automation API."""

from twinklr.core.api.xlights.client import XLightsAutomationClient
from twinklr.core.api.xlights.errors import (
    XLightsAutomationError,
    XLightsClientClosedError,
    XLightsCommandError,
    XLightsInstanceUnavailableError,
    XLightsTimeoutError,
)
from twinklr.core.api.xlights.fseq import FseqComparison, compare_fseqs
from twinklr.core.api.xlights.models import (
    CheckSequenceRequest,
    CheckSequenceResult,
    CloseSequenceRequest,
    CommandResult,
    ExportVideoPreviewRequest,
    ExportVideoPreviewResult,
    GetModelsRequest,
    GetModelsResult,
    LoadSequenceRequest,
    LoadSequenceResult,
    PreviewResult,
    RenderAllRequest,
)

__all__ = [
    "CheckSequenceRequest",
    "CheckSequenceResult",
    "CloseSequenceRequest",
    "CommandResult",
    "ExportVideoPreviewRequest",
    "ExportVideoPreviewResult",
    "FseqComparison",
    "GetModelsRequest",
    "GetModelsResult",
    "LoadSequenceRequest",
    "LoadSequenceResult",
    "PreviewResult",
    "RenderAllRequest",
    "XLightsAutomationClient",
    "XLightsAutomationError",
    "XLightsClientClosedError",
    "XLightsCommandError",
    "XLightsInstanceUnavailableError",
    "XLightsTimeoutError",
    "compare_fseqs",
]
