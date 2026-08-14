"""Minimal client for xLights' HTTP automation API (P1P-T12).

LOCAL-ONLY: this talks to a real, running xLights 2026.15 instance over the
unauthenticated `xlDoAutomation` HTTP endpoint (M6b: "no authentication documented —
flag as a local attack surface"). Nothing here is imported by production code and
nothing in the repository enables the API by default; the operator enables it in
xLights' own preferences for the duration of a local run and disables it afterwards.

Kept deliberately small: just enough to probe reachability and drive the two `xlDo`
commands `test_xlights_acceptance.py` actually calls (`newSequence`,
`importXLightsSequence`) plus `getVersion` for the reachability probe. Stdlib-only
(`urllib`) — no new dependency for a test module that skips itself on every CI
machine.

Deliberately does NOT wrap `checkSequence`, `getModels` or a `save` command: none of
them are called anywhere in this suite (checking/saving happens manually in the
xLights UI per `README.md`'s runbook), and M6b never corroborated an exact command
name for "save" — better to have no method than a guessed one nobody has run against
a real xLights yet. Add it back once a real run confirms the name.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:49913"
"""xLights' default automation port (M6b). The alternate 49914 is the second instance
port xLights uses when more than one copy is running; this suite only ever needs one."""

_PROBE_TIMEOUT_S = 2.0
"""Short on purpose: this fires at test-collection time on every run, including CI,
where the port is never open and every test using it should skip fast, not hang."""

_REQUEST_TIMEOUT_S = 30.0
"""Import/render commands can take real time against a large sequence; the probe
timeout above is intentionally much shorter."""


@dataclass(frozen=True)
class XLightsResponse:
    """One `xlDoAutomation` response."""

    status_code: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return json.loads(self.body)


class XLightsClient:
    """Thin wrapper over `POST {base_url}/xlDoAutomation`."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def send(
        self, payload: dict[str, Any], *, timeout: float = _REQUEST_TIMEOUT_S
    ) -> XLightsResponse:
        """POST one automation command and return the raw response.

        Args:
            payload: The `xlDo` command dict, e.g. `{"cmd": "getVersion"}`.
            timeout: Socket timeout in seconds.

        Returns:
            The response; a non-2xx status or a connection failure is surfaced as a
            `status_code`-carrying `XLightsResponse` where possible, not swallowed.
        """
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/xlDoAutomation",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return XLightsResponse(
                    status_code=response.status, body=response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            return XLightsResponse(
                status_code=exc.code, body=exc.read().decode("utf-8", errors="replace")
            )

    def get_version(self, *, timeout: float = _REQUEST_TIMEOUT_S) -> XLightsResponse:
        return self.send({"cmd": "getVersion"}, timeout=timeout)

    def new_sequence(self) -> XLightsResponse:
        return self.send({"cmd": "newSequence"})

    def import_xlights_sequence(
        self, filename: str, *, mapmethod: str = "file", mapfile: str | None = None
    ) -> XLightsResponse:
        payload: dict[str, Any] = {
            "cmd": "importXLightsSequence",
            "filename": filename,
            "mapmethod": mapmethod,
        }
        if mapfile is not None:
            payload["mapfile"] = mapfile
        return self.send(payload)


def probe_reachable(base_url: str = DEFAULT_BASE_URL) -> bool:
    """True iff an xLights automation API answers at `base_url`.

    Cheap and side-effect-free (a `getVersion` call). Used by the collection-time
    skip so `requires_xlights` tests never hang CI or a developer machine that
    simply doesn't have xLights running.
    """
    try:
        response = XLightsClient(base_url).get_version(timeout=_PROBE_TIMEOUT_S)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        logger.debug("xLights automation API unreachable at %s: %s", base_url, exc)
        return False
    return response.ok
