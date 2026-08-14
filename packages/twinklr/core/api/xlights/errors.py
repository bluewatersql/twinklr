"""Typed failures for xLights' local-only HTTP automation endpoint."""

from __future__ import annotations


class XLightsAutomationError(RuntimeError):
    """Base class for an xLights automation failure."""


class XLightsInstanceUnavailableError(XLightsAutomationError):
    """Raised when no reachable, windowed xLights instance exposes the API."""


class XLightsTimeoutError(XLightsAutomationError):
    """Raised when xLights does not answer a command before its explicit timeout."""


class XLightsCommandError(XLightsAutomationError):
    """Raised when xLights rejects a command or returns an invalid response."""


class XLightsClientClosedError(XLightsAutomationError):
    """Raised when a caller attempts to reuse a closed client."""
