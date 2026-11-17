"""An in-memory stand-in for the xLights automation client, for offline live-injection tests.

It answers the six commands the live workflow sends (`getModels`, `getOpenSequence`,
`getEffectIDs`, `getEffectSettings`, `addEffect`, `deleteEffect`) as the typed client
does, keeps every effect by model, layer and id, and logs each command. Lookups are by
id, so it stays fast at tens of thousands of effects. It never contacts xLights.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from twinklr.core.api.xlights.models import (
    AddEffectRequest,
    CommandResult,
    DeleteEffectRequest,
    EffectIdsResult,
    EffectSettingsResult,
    GetEffectIdsRequest,
    GetEffectSettingsRequest,
    GetModelsRequest,
    GetModelsResult,
    OpenSequenceResult,
)

SCRATCH_SEQUENCE = Path("/tmp/scratch.xsq")


class FakeLiveXLights:
    """The open scratch sequence of one windowed xLights, held in memory."""

    def __init__(self, models: tuple[str, ...] = (), groups: tuple[str, ...] = ()) -> None:
        self.models = models
        self.groups = groups
        self.layers: dict[str, list[dict[str, dict[str, Any]]]] = {}
        self.requests: list[str] = []
        self._next_id = 1

    async def __aenter__(self) -> FakeLiveXLights:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get_models(self, request: GetModelsRequest | None = None) -> GetModelsResult:
        self.requests.append("getModels")
        names = (self.models if request is None or request.include_models else ()) + (
            self.groups if request is not None and request.include_groups else ()
        )
        return GetModelsResult(200, models=names)

    async def get_open_sequence(self, request: object = None) -> OpenSequenceResult:
        self.requests.append("getOpenSequence")
        return OpenSequenceResult(
            200, sequence_name=SCRATCH_SEQUENCE.name, sequence_path=SCRATCH_SEQUENCE
        )

    async def get_effect_ids(self, request: GetEffectIdsRequest) -> EffectIdsResult:
        self.requests.append("getEffectIDs")
        layers = self.layers.get(request.model, [])
        return EffectIdsResult(200, layers=tuple(tuple(layer) for layer in layers))

    async def get_effect_settings(self, request: GetEffectSettingsRequest) -> EffectSettingsResult:
        self.requests.append("getEffectSettings")
        effect = self.layers[request.model][request.layer][request.effect_id]
        return EffectSettingsResult(
            200,
            model=request.model,
            layer=request.layer,
            effect_id=request.effect_id,
            name=effect["name"],
            settings=effect["settings"],
            palette=effect["palette"],
            start_ms=effect["start_ms"],
            end_ms=effect["end_ms"],
        )

    async def add_effect(self, request: AddEffectRequest) -> CommandResult:
        self.requests.append("addEffect")
        layers = self.layers.setdefault(request.target, [])
        while len(layers) <= request.layer:
            layers.append({})
        layers[request.layer][str(self._next_id)] = {
            "name": request.effect,
            "settings": request.settings,
            "palette": request.palette,
            "start_ms": request.start_ms,
            "end_ms": request.end_ms,
        }
        self._next_id += 1
        return CommandResult(200, "Added Effects.")

    async def delete_effect(self, request: DeleteEffectRequest) -> CommandResult:
        self.requests.append("deleteEffect")
        del self.layers[request.model][request.layer][request.effect_id]
        return CommandResult(200, "Deleted Effect.")

    def placed(self) -> list[tuple[str, int, str, str, str, int, int]]:
        """Every effect in the sequence: model, layer, effect, settings, palette, times."""
        return sorted(
            (model, layer, e["name"], e["settings"], e["palette"], e["start_ms"], e["end_ms"])
            for model, layers in self.layers.items()
            for layer, effects in enumerate(layers)
            for e in effects.values()
        )
