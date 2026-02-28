"""EffectStackDetector — groups co-occurring effects into visual stacks.

In xLights the visual unit on a display model is the full layer stack
active on a target at a given time.  This module detects those stacks
by grouping EffectPhrase instances that share the same target and
overlap temporally.

The output is a tuple of EffectStack objects — the atomic units for
downstream template mining.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackLayer,
)
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole

# Effect families that typically serve as base/wash layers.
_BASE_FAMILIES: frozenset[str] = frozenset(
    {"color_wash", "fill", "on", "morph", "shader", "pictures", "video"}
)

# Effect families that typically serve as accent/overlay layers.
_ACCENT_FAMILIES: frozenset[str] = frozenset(
    {"sparkle", "twinkle", "shimmer", "snowflakes", "candle", "strobe", "fireworks"}
)


@dataclass(frozen=True)
class EffectStackDetectorOptions:
    """Runtime options for stack detection."""

    overlap_threshold: float = 0.8


class EffectStackDetector:
    """Detect multi-layer effect stacks from encoded phrases.

    Groups all EffectPhrase instances that share the same
    (package_id, sequence_file_id, target_name) and overlap
    temporally by at least ``overlap_threshold`` into a single
    EffectStack.
    """

    def __init__(self, options: EffectStackDetectorOptions | None = None) -> None:
        self._options = options or EffectStackDetectorOptions()

    def detect(self, *, phrases: tuple[EffectPhrase, ...]) -> tuple[EffectStack, ...]:
        """Detect effect stacks from a corpus of phrases.

        Args:
            phrases: All encoded phrases (may span multiple packages/sequences).

        Returns:
            Tuple of detected stacks, sorted by (package, sequence, target, start_ms).
        """
        if not phrases:
            return ()

        grouped: dict[tuple[str, str, str], list[EffectPhrase]] = defaultdict(list)
        for phrase in phrases:
            key = (phrase.package_id, phrase.sequence_file_id, phrase.target_name)
            grouped[key].append(phrase)

        stacks: list[EffectStack] = []
        for (pkg, seq, target), target_phrases in sorted(grouped.items()):
            ordered = sorted(target_phrases, key=lambda p: (p.start_ms, p.layer_index))
            target_stacks = self._detect_target_stacks(
                package_id=pkg,
                sequence_file_id=seq,
                target_name=target,
                phrases=ordered,
            )
            stacks.extend(target_stacks)

        stacks.sort(key=lambda s: (s.package_id, s.sequence_file_id, s.target_name, s.start_ms))
        return tuple(stacks)

    def _detect_target_stacks(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
        phrases: list[EffectPhrase],
    ) -> list[EffectStack]:
        """Detect stacks for a single target within a sequence.

        Uses a greedy overlap-merge strategy: for each phrase, attempt
        to merge it into the most recent open stack.  If the overlap
        is below threshold, start a new stack.
        """
        if not phrases:
            return []

        open_stacks: list[list[EffectPhrase]] = []

        for phrase in phrases:
            merged = False
            for stack_phrases in reversed(open_stacks):
                if self._can_merge(stack_phrases, phrase):
                    stack_phrases.append(phrase)
                    merged = True
                    break
            if not merged:
                open_stacks.append([phrase])

        result: list[EffectStack] = []
        for stack_phrases in open_stacks:
            stack = self._build_stack(
                package_id=package_id,
                sequence_file_id=sequence_file_id,
                target_name=target_name,
                phrases=stack_phrases,
            )
            result.append(stack)

        return result

    def _can_merge(self, existing: list[EffectPhrase], candidate: EffectPhrase) -> bool:
        """Check if candidate should merge into the existing stack.

        Candidate must be on a different layer_index and overlap
        with every existing phrase by at least the threshold.
        """
        existing_layers = {p.layer_index for p in existing}
        if candidate.layer_index in existing_layers:
            return False

        for phrase in existing:
            overlap = self._overlap_ratio(phrase, candidate)
            if overlap < self._options.overlap_threshold:
                return False

        return True

    @staticmethod
    def _overlap_ratio(a: EffectPhrase, b: EffectPhrase) -> float:
        """Compute temporal overlap ratio (intersection / shorter duration)."""
        overlap_start = max(a.start_ms, b.start_ms)
        overlap_end = min(a.end_ms, b.end_ms)
        overlap_ms = max(0, overlap_end - overlap_start)

        shorter = min(a.duration_ms, b.duration_ms)
        if shorter <= 0:
            return 0.0
        return overlap_ms / shorter

    def _build_stack(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
        phrases: list[EffectPhrase],
    ) -> EffectStack:
        """Build an EffectStack from a set of co-occurring phrases."""
        sorted_phrases = sorted(phrases, key=lambda p: p.layer_index)

        layers: list[EffectStackLayer] = []
        for idx, phrase in enumerate(sorted_phrases):
            role = self._infer_layer_role(
                phrase=phrase,
                position=idx,
                total_layers=len(sorted_phrases),
            )
            blend = self._parse_blend_mode(phrase.blend_mode)
            mix_val = phrase.mix if phrase.mix is not None else 1.0

            layers.append(
                EffectStackLayer(
                    phrase=phrase,
                    layer_role=role,
                    blend_mode=blend,
                    mix=mix_val,
                    preserved_params=dict(phrase.preserved_params),
                )
            )

        start_ms = max(p.start_ms for p in sorted_phrases)
        end_ms = min(p.end_ms for p in sorted_phrases)
        if end_ms <= start_ms:
            start_ms = min(p.start_ms for p in sorted_phrases)
            end_ms = max(p.end_ms for p in sorted_phrases)

        section_label = sorted_phrases[0].section_label

        signature = self._build_signature(layers)

        stack_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{package_id}:{sequence_file_id}:{target_name}:{start_ms}:{signature}",
            )
        )

        return EffectStack(
            stack_id=stack_id,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            target_name=target_name,
            model_type=None,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=max(0, end_ms - start_ms),
            section_label=section_label,
            layers=tuple(layers),
            layer_count=len(layers),
            stack_signature=signature,
        )

    @staticmethod
    def _infer_layer_role(
        *,
        phrase: EffectPhrase,
        position: int,
        total_layers: int,
    ) -> LayerRole:
        """Infer the visual role of a layer within a stack.

        Uses effect family first, then falls back to positional heuristic:
        position 0 = BASE, last position = ACCENT (if >1 layer), middle = RHYTHM.
        """
        if phrase.effect_family in _BASE_FAMILIES:
            return LayerRole.BASE
        if phrase.effect_family in _ACCENT_FAMILIES:
            return LayerRole.ACCENT

        if total_layers == 1:
            return LayerRole.BASE
        if position == 0:
            return LayerRole.BASE
        if position == total_layers - 1:
            return LayerRole.ACCENT
        return LayerRole.RHYTHM

    @staticmethod
    def _parse_blend_mode(raw: str | None) -> BlendMode:
        if raw is None:
            return BlendMode.NORMAL
        upper = raw.upper()
        try:
            return BlendMode(upper)
        except ValueError:
            return BlendMode.NORMAL

    @staticmethod
    def _build_signature(layers: list[EffectStackLayer]) -> str:
        """Build a canonical stack signature from its layers.

        Format: ``family@depth|blend+family@depth|blend+...``
        where depth is the first letter of the VisualDepth and blend
        is lowercase blend mode.

        Example: ``color_wash@b|normal+bars@m|add+sparkle@f|screen``
        """
        parts: list[str] = []
        for layer in layers:
            depth = _depth_abbreviation(layer.layer_role)
            blend = layer.blend_mode.value.lower()
            parts.append(f"{layer.phrase.effect_family}@{depth}|{blend}")
        return "+".join(parts)


def _depth_abbreviation(role: LayerRole) -> str:
    """Single-letter abbreviation for layer role in signatures."""
    _MAP = {
        LayerRole.BASE: "b",
        LayerRole.RHYTHM: "r",
        LayerRole.ACCENT: "a",
        LayerRole.HIGHLIGHT: "h",
        LayerRole.FILL: "f",
        LayerRole.TEXTURE: "t",
        LayerRole.CUSTOM: "c",
    }
    return _MAP.get(role, "?")
