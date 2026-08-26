"""Safe live-effect injection for an already-open xLights sequence.

xLights exposes this surface on an unauthenticated local HTTP port. Any local process
can drive the open sequence while it is enabled. Twinklr never saves the sequence and
never enables or exposes the port. Effects preserve the exporter's relative topology in
reserved layers starting at 99, and a local ownership manifest is required before an
existing effect on those layers may be replaced.

The upstream API is not transactional and ``addEffect`` returns no effect ID. Therefore
an ambiguous timeout/read failure is never replayed: the result reports the confirmed
prefix and tells the operator to inspect and idempotently re-run.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from twinklr.core.api.xlights.client import XLightsAutomationClient
from twinklr.core.api.xlights.errors import XLightsAutomationError
from twinklr.core.api.xlights.models import (
    AddEffectRequest,
    DeleteEffectRequest,
    EffectSettingsResult,
    GetEffectIdsRequest,
    GetEffectSettingsRequest,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.formats.xlights.sequence.fresh import build_fresh_sequence
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import XsqAdapter

TWINKLR_LAYER_BASE = 99
"""First xLights layer in Twinklr's identifiable live-injection namespace."""

# Compatibility name for callers that only need the namespace's first layer.
TWINKLR_LAYER = TWINKLR_LAYER_BASE


class InjectionError(RuntimeError):
    """Base class for failures that preserve non-Twinklr user effects."""


class InjectionCollisionError(InjectionError):
    """A non-owned effect occupies Twinklr's reserved target range."""


class InjectionPartialError(InjectionError):
    """Some mutations were confirmed before a later command failed."""

    def __init__(self, result: InjectionResult) -> None:
        self.result = result
        super().__init__(result.recovery)


@dataclass(frozen=True, order=True)
class LiveEffect:
    """One exact ``addEffect`` payload in the reserved live layer namespace."""

    target: str
    effect: str
    settings: str
    palette: str
    start_ms: int
    end_ms: int
    section_id: str
    layer: int = TWINKLR_LAYER_BASE

    def __post_init__(self) -> None:
        if not self.target or not self.effect or not self.section_id:
            raise ValueError("LiveEffect target, effect, and section_id must be non-empty")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("LiveEffect requires 0 <= start_ms < end_ms")
        if self.layer < TWINKLR_LAYER_BASE:
            raise ValueError(
                f"LiveEffect layer must be in the reserved namespace starting at "
                f"{TWINKLR_LAYER_BASE}"
            )

    def request(self) -> AddEffectRequest:
        return AddEffectRequest(
            target=self.target,
            effect=self.effect,
            settings=self.settings,
            palette=self.palette,
            layer=self.layer,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
        )

    @property
    def signature(self) -> tuple[object, ...]:
        return (
            self.target,
            self.layer,
            self.effect,
            _canonical_settings(self.settings),
            _canonical_settings(self.palette),
            self.start_ms,
            self.end_ms,
        )


@dataclass(frozen=True)
class LayoutDivergenceReport:
    configured_only_models: tuple[str, ...]
    live_only_models: tuple[str, ...]
    missing_configured_groups: tuple[str, ...]

    @property
    def has_divergence(self) -> bool:
        return bool(
            self.configured_only_models or self.live_only_models or self.missing_configured_groups
        )


@dataclass(frozen=True)
class LiveLayoutReconciliation:
    rig: FixtureGroup
    report: LayoutDivergenceReport
    model_names: tuple[str, ...]
    group_names: tuple[str, ...]


def reconcile_live_layout(
    configured: FixtureGroup,
    *,
    model_names: tuple[str, ...],
    group_names: tuple[str, ...],
) -> LiveLayoutReconciliation:
    """Make the live model list authoritative without inventing DMX channel maps.

    ``getModels`` exposes names, not moving-head channel semantics. Matching live names
    retain their configured DMX/calibration data; configured fixtures absent from the
    live layout are removed. Unconfigured live models are reported and never guessed.
    """
    live_models = set(model_names)
    live_groups = set(group_names)
    configured_fixtures = configured.expand_fixtures()
    matched_names = {
        fixture.xlights_model_name
        for fixture in configured_fixtures
        if fixture.xlights_model_name in live_models
    }
    configured_names = {fixture.xlights_model_name for fixture in configured_fixtures}
    missing_groups = tuple(
        sorted(
            name
            for name in (
                *((configured.xlights_group,) if configured.xlights_group else ()),
                *configured.xlights_semantic_groups.values(),
            )
            if name not in live_groups
        )
    )
    rig = configured.model_copy(deep=True)
    rig.fixtures = [
        fixture for fixture in configured.fixtures if fixture.xlights_model_name in matched_names
    ]
    rig.xlights_group = (
        configured.xlights_group if configured.xlights_group in live_groups else None
    )
    rig.xlights_semantic_groups = {
        key: value
        for key, value in configured.xlights_semantic_groups.items()
        if value in live_groups
    }
    return LiveLayoutReconciliation(
        rig=rig,
        report=LayoutDivergenceReport(
            configured_only_models=tuple(sorted(configured_names - live_models)),
            live_only_models=tuple(sorted(live_models - configured_names)),
            missing_configured_groups=missing_groups,
        ),
        model_names=tuple(model_names),
        group_names=tuple(group_names),
    )


class OwnershipStore(Protocol):
    def load(self, sequence_path: Path) -> tuple[LiveEffect, ...]: ...

    def save(self, sequence_path: Path, effects: tuple[LiveEffect, ...]) -> None: ...


class MemoryOwnershipStore:
    def __init__(self) -> None:
        self._effects: dict[str, tuple[LiveEffect, ...]] = {}

    def load(self, sequence_path: Path) -> tuple[LiveEffect, ...]:
        return self._effects.get(str(sequence_path), ())

    def save(self, sequence_path: Path, effects: tuple[LiveEffect, ...]) -> None:
        self._effects[str(sequence_path)] = effects


class JsonOwnershipStore:
    """Atomic local manifest; it never writes to or saves the user's sequence."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, sequence_path: Path) -> tuple[LiveEffect, ...]:
        if not self.path.exists():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get(str(sequence_path), [])
        return tuple(LiveEffect(**row) for row in rows)

    def save(self, sequence_path: Path, effects: tuple[LiveEffect, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {}
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload[str(sequence_path)] = [asdict(effect) for effect in effects]
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(self.path)


@dataclass(frozen=True)
class _ObservedEffect:
    effect_id: str
    model: str
    layer: int
    name: str
    settings: str | dict[str, str]
    palette: str | dict[str, str]
    start_ms: int
    end_ms: int

    @property
    def signature(self) -> tuple[object, ...]:
        return (
            self.model,
            self.layer,
            self.name,
            _canonical_settings(self.settings),
            _canonical_settings(self.palette),
            self.start_ms,
            self.end_ms,
        )


@dataclass(frozen=True)
class InjectionResult:
    complete: bool
    dry_run: bool
    sequence_path: Path
    commands: tuple[dict[str, str], ...]
    injected: tuple[LiveEffect, ...]
    deleted: tuple[LiveEffect, ...]
    unchanged: tuple[LiveEffect, ...]
    failed_command: dict[str, str] | None = None
    error: str | None = None
    recovery: str = ""


class LiveInjectionWorkflow:
    """Preflight, collision-check, replace, and report one live injection."""

    def __init__(
        self,
        client: XLightsAutomationClient,
        *,
        ownership: OwnershipStore,
    ) -> None:
        self.client = client
        self.ownership = ownership

    async def inject(
        self,
        effects: tuple[LiveEffect, ...],
        *,
        dry_run: bool = False,
        replace_sections: frozenset[str] | None = None,
        raise_on_partial: bool = True,
    ) -> InjectionResult:
        desired = tuple(sorted(effects))
        _validate_desired_no_overlap(desired)
        sequence = await self.client.get_open_sequence()
        owned = self.ownership.load(sequence.sequence_path)
        sections = (
            replace_sections
            if replace_sections is not None
            else frozenset(effect.section_id for effect in (*owned, *desired))
        )
        if any(effect.section_id not in sections for effect in desired):
            raise ValueError("Every desired effect must belong to a replaced section")

        target_layers = tuple(
            sorted(
                {(effect.target, effect.layer) for effect in desired}
                | {
                    (effect.target, effect.layer)
                    for effect in owned
                    if effect.section_id in sections
                }
            )
        )
        observed = await self._read_targets(target_layers)
        owned_by_signature: dict[tuple[object, ...], list[LiveEffect]] = {}
        for effect in owned:
            owned_by_signature.setdefault(effect.signature, []).append(effect)

        classified_owned: list[tuple[_ObservedEffect, LiveEffect]] = []
        unowned: list[_ObservedEffect] = []
        for item in observed:
            candidates = owned_by_signature.get(item.signature, [])
            if candidates:
                classified_owned.append((item, candidates.pop(0)))
            else:
                unowned.append(item)

        for item in unowned:
            if any(
                item.model == effect.target
                and item.layer == effect.layer
                and _overlaps(item.start_ms, item.end_ms, effect.start_ms, effect.end_ms)
                for effect in desired
            ):
                raise InjectionCollisionError(
                    f"User-owned effect collision on {item.model!r}, layer {item.layer}, "
                    f"{item.start_ms}-{item.end_ms}ms. No writes were issued."
                )

        current_counter = Counter(item.signature for item, _ in classified_owned)
        unchanged: list[LiveEffect] = []
        to_add: list[LiveEffect] = []
        for effect in desired:
            if current_counter[effect.signature] > 0:
                current_counter[effect.signature] -= 1
                unchanged.append(effect)
            else:
                to_add.append(effect)

        keep_counts = Counter(effect.signature for effect in unchanged)
        to_delete: list[tuple[_ObservedEffect, LiveEffect]] = []
        for item, effect in classified_owned:
            if effect.section_id not in sections:
                continue
            if keep_counts[item.signature] > 0:
                keep_counts[item.signature] -= 1
            else:
                to_delete.append((item, effect))
        commands = tuple(
            [
                DeleteEffectRequest(item.model, item.layer, item.effect_id).to_wire()
                for item, _ in to_delete
            ]
            + [effect.request().to_wire() for effect in to_add]
        )
        if dry_run:
            return InjectionResult(
                complete=True,
                dry_run=True,
                sequence_path=sequence.sequence_path,
                commands=commands,
                injected=(),
                deleted=tuple(effect for _, effect in to_delete),
                unchanged=tuple(unchanged),
                recovery="Dry run only; the open sequence was not modified.",
            )

        retained = [effect for effect in owned if effect.section_id not in sections]
        deleted: list[LiveEffect] = []
        injected: list[LiveEffect] = []
        failed_command: dict[str, str] | None = None
        manifest_state = list(owned)
        uncertain_add: LiveEffect | None = None
        try:
            for item, effect in to_delete:
                delete_request = DeleteEffectRequest(item.model, item.layer, item.effect_id)
                failed_command = delete_request.to_wire()
                await self.client.delete_effect(delete_request)
                deleted.append(effect)
                manifest_state.remove(effect)
            for effect in to_add:
                add_request = effect.request()
                failed_command = add_request.to_wire()
                uncertain_add = effect
                await self.client.add_effect(add_request)
                injected.append(effect)
                manifest_state.append(effect)
                uncertain_add = None
        except XLightsAutomationError as error:
            # A read timeout can arrive after xLights applied addEffect. Preserve that
            # exact attempted signature as uncertain ownership so the next preflight
            # can safely recognize either outcome without replaying this POST now.
            if uncertain_add is not None:
                manifest_state.append(uncertain_add)
            resulting = tuple(sorted(manifest_state))
            self.ownership.save(sequence.sequence_path, resulting)
            result = InjectionResult(
                complete=False,
                dry_run=False,
                sequence_path=sequence.sequence_path,
                commands=commands,
                injected=tuple(injected),
                deleted=tuple(deleted),
                unchanged=tuple(unchanged),
                failed_command=failed_command,
                error=str(error),
                recovery=(
                    "xLights has no transaction and the failed POST may be ambiguous. "
                    "Do not save yet: inspect the reserved layers starting at 99, then "
                    "re-run the same "
                    "command; preflight makes that recovery idempotent."
                ),
            )
            if raise_on_partial:
                raise InjectionPartialError(result) from error
            return result

        resulting = tuple(sorted((*retained, *desired)))
        self.ownership.save(sequence.sequence_path, resulting)
        return InjectionResult(
            complete=True,
            dry_run=False,
            sequence_path=sequence.sequence_path,
            commands=commands,
            injected=tuple(injected),
            deleted=tuple(deleted),
            unchanged=tuple(unchanged),
            recovery="No save was issued; review the Twinklr layer and save manually.",
        )

    async def regenerate_section(
        self,
        section_id: str,
        effects: tuple[LiveEffect, ...],
        *,
        dry_run: bool = False,
        raise_on_partial: bool = True,
    ) -> InjectionResult:
        if not section_id or any(effect.section_id != section_id for effect in effects):
            raise ValueError("regenerate_section requires effects for exactly one named section")
        return await self.inject(
            effects,
            dry_run=dry_run,
            replace_sections=frozenset({section_id}),
            raise_on_partial=raise_on_partial,
        )

    async def _read_targets(
        self, target_layers: tuple[tuple[str, int], ...]
    ) -> tuple[_ObservedEffect, ...]:
        observed: list[_ObservedEffect] = []
        layers_by_target: dict[str, set[int]] = {}
        for target, layer in target_layers:
            layers_by_target.setdefault(target, set()).add(layer)
        for target, requested_layers in sorted(layers_by_target.items()):
            ids = await self.client.get_effect_ids(GetEffectIdsRequest(target))
            for layer in sorted(requested_layers):
                if layer >= len(ids.layers):
                    continue
                for effect_id in ids.layers[layer]:
                    settings = await self.client.get_effect_settings(
                        GetEffectSettingsRequest(target, layer, effect_id)
                    )
                    observed.append(_observed(settings))
        return tuple(observed)


def live_effects_from_segments(
    segments: list[FixtureSegment], fixture_group: FixtureGroup
) -> tuple[LiveEffect, ...]:
    """Serialize using the exact ``XsqAdapter``/``DmxSettingsBuilder`` export seam."""
    duration_ms = max((segment.t1_ms for segment in segments), default=1)
    sequence = build_fresh_sequence(
        media_file="twinklr-live-injection.wav",
        duration_ms=duration_ms,
    )
    placements = XsqAdapter().convert(segments, fixture_group, sequence)
    traces = sequence.emission_trace_entries
    if len(traces) != len(placements):
        raise InjectionError("MH trace count diverged from injection placements")
    effects: list[LiveEffect] = []
    for placement, trace in zip(placements, traces, strict=True):
        if placement.ref is None:
            raise InjectionError("xLights placement omitted its EffectDB settings reference")
        settings = sequence.effect_db.get(placement.ref)
        if settings is None:
            raise InjectionError(f"Missing EffectDB entry {placement.ref}")
        section_id = trace.get("section_id")
        live_layer = trace.get("live_layer")
        if not isinstance(section_id, str) or not isinstance(live_layer, int):
            raise InjectionError("MH trace omitted section or live-layer provenance")
        effects.append(
            LiveEffect(
                target=placement.element_name,
                effect=placement.effect_name,
                settings=settings,
                palette="",
                start_ms=placement.start_ms,
                end_ms=placement.end_ms,
                section_id=section_id,
                layer=live_layer,
            )
        )
    return tuple(sorted(effects))


def _observed(settings: EffectSettingsResult) -> _ObservedEffect:
    return _ObservedEffect(
        effect_id=settings.effect_id,
        model=settings.model,
        layer=settings.layer,
        name=settings.name,
        settings=settings.settings,
        palette=settings.palette,
        start_ms=settings.start_ms,
        end_ms=settings.end_ms,
    )


def _canonical_settings(value: str | dict[str, str]) -> tuple[tuple[str, str], ...]:
    if isinstance(value, dict):
        return tuple(sorted(value.items()))
    if not value:
        return ()
    pairs: list[tuple[str, str]] = []
    for token in value.split(","):
        key, separator, item_value = token.partition("=")
        pairs.append((key, item_value if separator else ""))
    return tuple(sorted(pairs))


def _overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def _validate_desired_no_overlap(effects: tuple[LiveEffect, ...]) -> None:
    for index, effect in enumerate(effects):
        for other in effects[index + 1 :]:
            if (
                effect.target == other.target
                and effect.layer == other.layer
                and _overlaps(
                    effect.start_ms,
                    effect.end_ms,
                    other.start_ms,
                    other.end_ms,
                )
            ):
                raise InjectionCollisionError(
                    f"Twinklr planned effects overlap on {effect.target!r}, layer "
                    f"{effect.layer}: {effect.start_ms}-{effect.end_ms}ms and "
                    f"{other.start_ms}-{other.end_ms}ms. No xLights requests were issued."
                )
