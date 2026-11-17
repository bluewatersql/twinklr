"""Which xLights layer played: the old renderer's `.xsq` against the `.fseq` xLights rendered.

Evidence for the W0 record (README.md beside this file), run once on 2026-11-17:

    uv run python changes/2026_11_12_mh_true_up/evidence/2026-11-17-w0-intent-parity/layer_playback.py \
        ~/xlights/_twinklr_verify/p3_view/out/legacy_need_a_favor.xsq \
        ~/xlights/_twinklr_verify/p3_view/out/legacy_need_a_favor.fseq

Reads both files only. Each head's `.xsq` holds a first EffectLayer (the section effects)
and a second (the transitions); every frame inside a transition effect is compared,
channel by channel, with the byte each layer would send there (value curves sampled
linearly at the frame's start) and the byte the `.fseq` holds. The `.fseq` (v2, zstd,
sparse) is decoded here: the repository has no FSEQ frame reader, only a byte comparer.
"""

from __future__ import annotations

from itertools import pairwise
import json
from pathlib import Path
import struct
import sys
from typing import Any

from defusedxml import ElementTree
import zstandard

STEP_MS = 20


def read_fseq(path: Path) -> tuple[dict[str, Any], bytes]:
    """The header and the decompressed frame data of an FSEQ v2 file."""
    raw = path.read_bytes()
    assert raw[:4] == b"PSEQ", "not an FSEQ file"
    data_offset, minor, major = struct.unpack_from("<HBB", raw, 4)
    channels, frames = struct.unpack_from("<II", raw, 10)
    compression = raw[20] & 0x0F
    blocks = raw[21] | ((raw[20] & 0xF0) << 4)
    sparse = raw[22]
    index = [struct.unpack_from("<II", raw, 32 + 8 * i) for i in range(blocks)]
    start = 32 + 8 * blocks
    ranges = [
        (
            int.from_bytes(raw[start + 6 * i : start + 6 * i + 3], "little"),
            int.from_bytes(raw[start + 6 * i + 3 : start + 6 * i + 6], "little"),
        )
        for i in range(sparse)
    ]
    data = bytearray()
    position = data_offset
    for _, size in index:
        chunk = raw[position : position + size]
        position += size
        if size:
            data += (
                zstandard.ZstdDecompressor().decompressobj().decompress(chunk)
                if compression == 1
                else chunk
            )
    assert len(data) >= frames * channels
    header = {
        "version": f"{major}.{minor}",
        "channels": channels,
        "frames": frames,
        "step_ms": raw[18],
        "compression": "zstd" if compression == 1 else compression,
        "sparse_ranges": ranges,
    }
    return header, bytes(data)


def parse_settings(settings: str) -> dict[int, Any]:
    values: dict[int, Any] = {}
    for part in settings.split(","):
        key, _, raw = part.partition("=")
        if key.startswith("E_SLIDER_DMX"):
            values.setdefault(int(key.removeprefix("E_SLIDER_DMX")), int(raw))
        elif key.startswith("E_VALUECURVE_DMX"):
            fields = dict(item.split("=", 1) for item in raw.strip("|").split("|"))
            low, high = float(fields["Min"]), float(fields["Max"])
            values[int(key.removeprefix("E_VALUECURVE_DMX"))] = [
                (float(t), low + float(v) * (high - low))
                for t, v in (pair.split(":") for pair in fields["Values"].split(";"))
            ]
    return values


def sample(value: int | list[tuple[float, float]], position: float) -> int:
    if isinstance(value, int):
        return value
    for (t0, v0), (t1, v1) in pairwise(value):
        if position <= t1:
            ratio = 0.0 if t1 == t0 else (position - t0) / (t1 - t0)
            return round(v0 + ratio * (v1 - v0))
    return round(value[-1][1])


Effect = tuple[int, int, dict[int, Any]]


def read_xsq(path: Path) -> dict[str, list[list[Effect]]]:
    """Per model, its EffectLayers in file order, each a list of (start, end, values)."""
    root = ElementTree.parse(path).getroot()
    database = [effect.text or "" for effect in root.iterfind("EffectDB/Effect")]
    models: dict[str, list[list[Effect]]] = {}
    for element in root.iterfind("ElementEffects/Element"):
        if element.get("type") != "model":
            continue
        models[element.get("name") or ""] = [
            [
                (
                    int(effect.get("startTime", "0")),
                    int(effect.get("endTime", "0")),
                    parse_settings(database[int(effect.get("ref", "0"))]),
                )
                for effect in layer.iterfind("Effect")
            ]
            for layer in element.iterfind("EffectLayer")
        ]
    return models


def predicted(effects: list[Effect], channel: int, time_ms: int) -> int | None:
    for start, end, values in effects:
        if start <= time_ms < end and channel in values:
            return sample(values[channel], (time_ms - start) / (end - start))
    return None


def main(xsq: Path, fseq: Path) -> dict[str, Any]:
    header, data = read_fseq(fseq)
    models = read_xsq(xsq)
    width = int(header["channels"])

    def played(model_index: int, channel: int, time_ms: int) -> int:
        return data[(time_ms // STEP_MS) * width + model_index * 16 + channel - 1]

    counts = {
        "with_a_base_effect": {"base_only": 0, "either": 0, "transition_only": 0, "neither": 0},
        "without_a_base_effect": {"transition": 0, "other": 0},
    }
    for index, name in enumerate(sorted(models)):  # sparse ranges in head order
        base, transitions = models[name]
        for start, end, values in transitions:
            for time_ms in range(start - start % STEP_MS + STEP_MS, end, STEP_MS):
                covered = any(a <= time_ms < b for a, b, _ in base)
                for channel, value in values.items():
                    layer_1 = sample(value, (time_ms - start) / (end - start))
                    byte = played(index, channel, time_ms)
                    if not covered:
                        key = "transition" if abs(byte - layer_1) <= 1 else "other"
                        counts["without_a_base_effect"][key] += 1
                        continue
                    layer_0 = predicted(base, channel, time_ms)
                    on_0 = layer_0 is not None and abs(byte - layer_0) <= 1
                    on_1 = abs(byte - layer_1) <= 1
                    key = (
                        "either"
                        if on_0 and on_1
                        else "base_only"
                        if on_0
                        else "transition_only"
                        if on_1
                        else "neither"
                    )
                    counts["with_a_base_effect"][key] += 1
    gaps = {
        name: [(a[1], b[0]) for a, b in pairwise(sorted(layers[0])) if b[0] > a[1]]
        for name, layers in models.items()
    }
    return {
        "fseq": header,
        "layer_effects": {n: [len(x) for x in v] for n, v in models.items()},
        "base_gaps": gaps,
        "counts": counts,
    }


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))
