"""Extract technical-sophistication metrics from an emitted xLights `.xsq`.

The parity bar (owner, 2026-08-29) is the *final delivered output*: the MH `.xsq` should
carry the same level of advanced/technical implementation detail as before the refactor.
These metrics quantify that — effect volume, DMX channel richness, value-curve density,
element/layer coverage — so a fresh render can be compared to a captured baseline without
depending on exact byte equality or natural LLM variation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from twinklr.core.formats.xlights.sequence.parser import XSQParser

_VALUE_CURVE_RE = re.compile(r"E_VALUECURVE_DMX(\d+)=")
_SLIDER_RE = re.compile(r"E_SLIDER_DMX(\d+)=")


@dataclass(frozen=True)
class XsqMetrics:
    """Deterministic, byte-independent sophistication metrics for one `.xsq`."""

    element_count: int
    placed_effect_count: int
    distinct_effect_types: tuple[str, ...]
    effectdb_entry_count: int
    value_curve_channel_count: int
    max_dmx_channel: int
    max_layers: int
    sequence_timing: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_xsq_metrics(xsq_path: Path | str) -> XsqMetrics:
    """Parse a `.xsq` and compute its sophistication metrics."""
    seq = XSQParser().parse(Path(xsq_path))

    placed_effect_count = 0
    distinct_effect_types: set[str] = set()
    max_layers = 0
    for element in seq.element_effects:
        max_layers = max(max_layers, len(element.layers))
        for layer in element.layers:
            for effect in layer.effects:
                placed_effect_count += 1
                distinct_effect_types.add(effect.effect_type)

    entries = [entry for entry in seq.effect_db.entries if entry]
    value_curve_channel_count = sum(len(_VALUE_CURVE_RE.findall(entry)) for entry in entries)
    max_dmx_channel = 0
    for entry in entries:
        for match in _SLIDER_RE.finditer(entry):
            max_dmx_channel = max(max_dmx_channel, int(match.group(1)))

    return XsqMetrics(
        element_count=len(seq.element_effects),
        placed_effect_count=placed_effect_count,
        distinct_effect_types=tuple(sorted(distinct_effect_types)),
        effectdb_entry_count=len(entries),
        value_curve_channel_count=value_curve_channel_count,
        max_dmx_channel=max_dmx_channel,
        max_layers=max_layers,
        sequence_timing=seq.head.sequence_timing,
    )
