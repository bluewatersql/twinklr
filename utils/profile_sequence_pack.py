from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
from typing import TYPE_CHECKING, Any, Literal
import uuid
from xml.etree import ElementTree as ET
import zipfile
import zlib

from pydantic import BaseModel, ConfigDict, field_validator

from twinklr.core.formats.xlights.sequence.parser import XSQParser

if TYPE_CHECKING:
    from twinklr.core.formats.xlights.sequence.models.xsq import XSequence

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

ConfigMode = Literal["plain", "compressed"]

_EFFECTDB_PREFIX_RE = re.compile(r"[ETBE]_\w+_")


# -------------------------------------------------
# Utilities
# -------------------------------------------------
def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def json_canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def config_fingerprint(obj: Any) -> str:
    return hashlib.sha1(json_canonical(obj)).hexdigest()


def compress_config(obj: Any) -> tuple[str, str, str]:
    """Returns: (codec, fingerprint, blob_b64).

    fingerprint is sha1 of canonical json bytes (stable).
    """

    payload = json_canonical(obj)
    fp = hashlib.sha1(payload).hexdigest()
    blob = zlib.compress(payload, level=6)
    blob_b64 = base64.b64encode(blob).decode("ascii")
    return ("zlib+json", fp, blob_b64)


def strip_nulls(data):
    if isinstance(data, dict):
        return {key: strip_nulls(value) for key, value in data.items() if value is not None}
    elif isinstance(data, list):
        return [strip_nulls(element) for element in data if element is not None]
    else:
        return data


def clean_effectdb_settings(s: str) -> str:
    # Removes noisy field-prefixes from EffectDB's serialized settings string.
    return _EFFECTDB_PREFIX_RE.sub("", s)


def infer_asset_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}:
        return "audio"
    if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
        return "video"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        return "image"
    if ext in {".fs"}:
        return "shader"
    if ext in {".docx", ".doc", ".pdf", ".txt", ".csv", ".xls", ".xlsx"}:
        return "document"
    return "other"


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# -------------------------------------------------
#  Data Models (Pydantic)
# -------------------------------------------------


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class FileEntry(_FrozenModel):
    file_id: str
    filename: str
    ext: str
    size: int
    sha256: str
    kind: str  # sequence, rgb_effects, asset, shader, other


class PackageManifest(_FrozenModel):
    package_id: str
    zip_sha256: str
    files: list[FileEntry]
    sequence_file_id: str | None
    rgb_effects_file_id: str | None


class EffectEventOut(_FrozenModel):
    effect_event_id: str

    # "where" join key (string name from sequence)
    target_name: str
    target_type: str | None = None  # optional; omitted from json by default
    layer_index: int
    layer_name: str

    # "what/when"
    effect_type: str
    start_ms: int
    end_ms: int

    # config representation (plain OR compressed)
    config_plain: dict[str, Any] | None = None

    config_codec: str | None = None
    config_fingerprint: str
    config_blob_b64: str | None = None

    # lineage extras
    effectdb_ref: int | None = None
    effectdb_settings: str | None = None
    palette: str = ""
    protected: bool = False
    label: str | None = None

    @field_validator("config_plain", mode="before")
    @classmethod
    def _strip_empty_config_plain(cls, v: Any) -> Any:
        if v == {}:
            return None
        return v


class BaseEffectEventsFile(_FrozenModel):
    # Written once as header (not repeated per event)
    package_id: str
    sequence_file_id: str
    sequence_sha256: str
    config_mode: ConfigMode

    events: list[EffectEventOut]


class TargetFact(_FrozenModel):
    layout_id: str
    rgb_effects_file_id: str
    rgb_effects_sha256: str
    target_name: str
    target_kind: str  # model|group|unknown

    # best-effort spatial info (may be None)
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None
    cx: float | None = None
    cy: float | None = None


# -------------------------------------------------
# Color Palette Parsing
# -------------------------------------------------


def parse_color_palettes_from_sequence(seq_path: Path) -> dict[str, Any]:
    """Parse color palettes directly from sequence XML file.

    Returns dict with:
    - unique_colors: list of unique color codes used across all palettes
    - unique_indices: list of ALL 0-based palette slot indices used (1-based palette numbers converted to 0-based)
    - single_colors: DISTINCT list - one entry per unique color, with palette ENTRY indices where it appears alone
    - color_palettes: DISTINCT list - one entry per unique color combo (order-independent), with palette ENTRY indices
    """
    xml = seq_path.read_text(encoding="utf-8", errors="ignore")
    root = ET.fromstring(xml)

    palettes_node = root.find(".//ColorPalettes")
    if palettes_node is None:
        return {
            "unique_colors": [],
            "single_colors": [],
            "color_palettes": [],
        }

    all_unique_colors = set()

    # Collect palette entries with their entry index
    single_color_map = {}  # color -> list of palette entry indices
    multi_color_map = {}  # color_combo -> list of palette entry indices

    for entry_idx, palette_node in enumerate(palettes_node.findall("ColorPalette")):
        palette_str = palette_node.text or ""
        if not palette_str:
            continue

        # Parse palette entry
        parsed = _parse_palette_entry(palette_str)

        # Track unique colors and palette slot indices (0-based from palette numbers 1-8)
        for color in parsed["colors"]:
            all_unique_colors.add(color)

        # Categorize by color count and track ENTRY index
        if len(parsed["colors"]) == 1:
            color = parsed["colors"][0]
            if color not in single_color_map:
                single_color_map[color] = []
            single_color_map[color].append(entry_idx)

        elif len(parsed["colors"]) > 1:
            # Sort colors for order-independent comparison
            color_combo = tuple(sorted(parsed["colors"]))
            if color_combo not in multi_color_map:
                multi_color_map[color_combo] = []
            multi_color_map[color_combo].append(entry_idx)

    # Build single_colors output
    single_colors = [
        {
            "color": color,
            "palette_entry_indices": entry_indices,  # indices of ColorPalette elements
        }
        for color, entry_indices in sorted(single_color_map.items())
    ]

    # Build color_palettes output
    color_palettes = [
        {
            "colors": list(color_combo),
            "palette_entry_indices": entry_indices,  # indices of ColorPalette elements
        }
        for color_combo, entry_indices in sorted(multi_color_map.items())
    ]

    palettes = {
        "unique_colors": sorted(all_unique_colors),
        "single_colors": single_colors,
        "color_palettes": color_palettes,
    }
    palettes["classifications"] = classify_palettes_by_color_properties(palettes)
    return palettes


_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COLOR_CURVE_RE = re.compile(r"c=(#[0-9A-Fa-f]{6})")


def _parse_color_curve(value: str) -> list[str]:
    """Extract hex colors from an xLights color curve value.

    Color curves encode time-varying colors in the format:
        Active=TRUE|Id=...|Values=x=0.190^c=#c8102e;x=0.240^c=#000000;...|

    Returns de-duplicated list of hex colors found in the Values field.
    """
    colors = _COLOR_CURVE_RE.findall(value)
    seen: set[str] = set()
    unique: list[str] = []
    for c in colors:
        upper = c.upper()
        if upper not in seen:
            seen.add(upper)
            unique.append(upper)
    return unique


def _parse_palette_entry(palette_str: str) -> dict[str, Any]:
    """Parse a single palette entry string from sequence file.

    Handles two value formats for C_BUTTON_Palette slots:
      - Simple hex: ``#RRGGBB``
      - Color curve: ``Active=TRUE|Id=...|Values=x=0.190^c=#c8102e;...|``

    Extracts color codes where corresponding checkbox value is 1.

    Returns:
    - colors: list of enabled color codes (de-duplicated within this entry)
    - slot_indices: list of 0-based palette slot indices (which of the 8 slots are used)
    """
    parts = palette_str.split(",")

    color_buttons: dict[int, list[str]] = {}
    checkboxes: dict[int, bool] = {}

    for part in parts:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key.startswith("C_BUTTON_Palette"):
            match = re.match(r"C_BUTTON_Palette(\d+)", key)
            if match:
                palette_slot = int(match.group(1))
                if _HEX_COLOR_RE.match(value):
                    color_buttons[palette_slot] = [value.upper()]
                elif value.startswith("Active="):
                    curve_colors = _parse_color_curve(value)
                    if curve_colors:
                        color_buttons[palette_slot] = curve_colors
                    else:
                        logger.warning(
                            "Color curve in palette slot %d has no parseable colors: %s",
                            palette_slot,
                            value[:200],
                        )
                else:
                    logger.warning(
                        "Unrecognised palette slot %d value format: %r",
                        palette_slot,
                        value[:200],
                    )

        elif key.startswith("C_CHECKBOX_Palette"):
            match = re.match(r"C_CHECKBOX_Palette(\d+)", key)
            if match:
                palette_slot = int(match.group(1))
                checkboxes[palette_slot] = value == "1"

    # Build enabled colors list (checkbox=1 only)
    enabled_colors: list[str] = []
    enabled_slot_indices: list[int] = []

    for palette_slot in sorted(color_buttons.keys()):
        if checkboxes.get(palette_slot, False):
            slot_idx = palette_slot - 1
            for color in color_buttons[palette_slot]:
                enabled_colors.append(color)
                enabled_slot_indices.append(slot_idx)

    # De-duplicate colors within this entry while preserving order
    seen_colors: set[str] = set()
    unique_colors: list[str] = []
    unique_slot_indices: list[int] = []

    for color, slot_idx in zip(enabled_colors, enabled_slot_indices, strict=False):
        if color not in seen_colors:
            seen_colors.add(color)
            unique_colors.append(color)
            unique_slot_indices.append(slot_idx)

    return {"colors": unique_colors, "slot_indices": unique_slot_indices}


def classify_palettes_by_color_properties(palette_data: dict[str, Any]) -> dict[str, Any]:
    """Classify palettes by color properties (hue, saturation, brightness).

    Returns classifications like:
    - monochrome: Only black/white/gray
    - warm: Contains warm colors (red, orange, yellow)
    - cool: Contains cool colors (blue, green, purple)
    - primary: Only primary colors (red, blue, yellow)
    - etc.
    """

    def hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
        """Convert hex color to RGB tuple, or None if not a valid 6-char hex string."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in hex_color):
            logger.warning("Invalid hex color passed to hex_to_rgb: %r", hex_color)
            return None
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def is_grayscale(hex_color: str) -> bool:
        """Check if color is grayscale (R=G=B)."""
        rgb = hex_to_rgb(hex_color)
        if rgb is None:
            return False
        r, g, b = rgb
        return r == g == b

    def is_warm(hex_color: str) -> bool:
        """Check if color is warm (red/orange/yellow dominant)."""
        rgb = hex_to_rgb(hex_color)
        if rgb is None:
            return False
        r, g, b = rgb
        return r > b and r > g * 0.8

    def is_cool(hex_color: str) -> bool:
        """Check if color is cool (blue/green dominant)."""
        rgb = hex_to_rgb(hex_color)
        if rgb is None:
            return False
        r, g, b = rgb
        return (b > r and b > g * 0.8) or (g > r and g > b * 0.8)

    def color_category(hex_color: str) -> str:
        """Categorize color into basic color families."""
        rgb = hex_to_rgb(hex_color)
        if rgb is None:
            return "unknown"

        r, g, b = rgb
        if r == g == b:
            if r == 0:
                return "black"
            elif r == 255:
                return "white"
            else:
                return "gray"

        max_val = max(r, g, b)

        if r == max_val and g < 100 and b < 100:
            return "red"
        elif g == max_val and r < 100 and b < 100:
            return "green"
        elif b == max_val and r < 100 and g < 100:
            return "blue"
        elif r == max_val and g == max_val and b < 100:
            return "yellow"
        elif r == max_val and b == max_val and g < 100:
            return "magenta"
        elif g == max_val and b == max_val and r < 100:
            return "cyan"
        elif r > 200 and g > 100 and g < 200 and b < 100:
            return "orange"
        elif r > 100 and g < 100 and b > 100:
            return "purple"
        else:
            return "mixed"

    # Combine all palettes
    all_palettes = []
    for entry in palette_data["single_colors"]:
        all_palettes.append(
            {"colors": [entry["color"]], "palette_entry_indices": entry["palette_entry_indices"]}
        )
    for entry in palette_data["color_palettes"]:
        all_palettes.append(
            {"colors": entry["colors"], "palette_entry_indices": entry["palette_entry_indices"]}
        )

    # Classify
    monochrome = []
    warm_palettes = []
    cool_palettes = []
    primary_only = []
    by_color_family = {}

    for palette in all_palettes:
        colors = palette["colors"]

        # Monochrome check
        if all(is_grayscale(c) for c in colors):
            monochrome.append(palette)

        # Warm/cool check
        if any(is_warm(c) for c in colors):
            warm_palettes.append(palette)
        if any(is_cool(c) for c in colors):
            cool_palettes.append(palette)

        # Primary colors only (red, blue, yellow + black/white)
        primary_set = {"#FF0000", "#0000FF", "#FFFF00", "#000000", "#FFFFFF"}
        if all(c.upper() in primary_set for c in colors):
            primary_only.append(palette)

        # Group by color family
        for color in colors:
            category = color_category(color)
            if category not in by_color_family:
                by_color_family[category] = []
            by_color_family[category].append(
                {
                    "colors": palette["colors"],
                    "palette_entry_indices": palette["palette_entry_indices"],
                }
            )

    return {
        "monochrome": monochrome,
        "warm": warm_palettes,
        "cool": cool_palettes,
        "primary_only": primary_only,
        "by_color_family": by_color_family,
    }


# -------------------------------------------------
# Stage A: Zip ingest + hashing
# -------------------------------------------------


def ingest_zip(zip_path: Path) -> PackageManifest:
    package_id = str(uuid.uuid4())
    zip_sha = sha256_bytes(zip_path.read_bytes())

    files: list[FileEntry] = []
    sequence_file_id: str | None = None
    rgb_effects_file_id: str | None = None

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            filename = Path(info.filename).name  # flatten
            ext = Path(filename).suffix.lower()
            data = zf.read(info.filename)
            file_sha = sha256_bytes(data)

            kind = "other"
            lower = filename.lower()
            if lower.endswith(("rgb_effects.xml", "rgbeffects.xml")):
                kind = "rgb_effects"
            elif ext in {".xsq", ".seq"}:
                kind = "sequence"
            else:
                at = infer_asset_type(filename)
                if at == "shader":
                    kind = "shader"
                elif at in {"audio", "video", "image"}:
                    kind = "asset"

            file_id = str(uuid.uuid4())
            files.append(
                FileEntry(
                    file_id=file_id,
                    filename=filename,
                    ext=ext,
                    size=info.file_size,
                    sha256=file_sha,
                    kind=kind,
                )
            )

            if kind == "sequence" and sequence_file_id is None:
                sequence_file_id = file_id
            if kind == "rgb_effects" and rgb_effects_file_id is None:
                rgb_effects_file_id = file_id

    return PackageManifest(
        package_id=package_id,
        zip_sha256=zip_sha,
        files=files,
        sequence_file_id=sequence_file_id,
        rgb_effects_file_id=rgb_effects_file_id,
    )


def extract_zip_flat(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            filename = Path(info.filename).name
            (out_dir / filename).write_bytes(zf.read(info.filename))


# -------------------------------------------------
# Stage B: XSQ -> BaseEffects (using your parser/model)
# -------------------------------------------------


def build_effect_config_dict(
    sequence: XSequence, effect: Any
) -> tuple[dict[str, Any], int | None, str | None]:
    """Normalize config content to something stable.

    - include parameters dict
    - include palette/protected/label/ref
    - optionally resolve EffectDB settings string for ref
    """

    cfg: dict[str, Any] = {}

    params = getattr(effect, "parameters", {}) or {}
    if isinstance(params, dict):
        cfg.update(params)
    else:
        cfg["parameters"] = params

    palette = getattr(effect, "palette", "")
    protected = bool(getattr(effect, "protected", False))
    label = getattr(effect, "label", None)
    ref = getattr(effect, "ref", None)

    cfg["_palette"] = palette
    cfg["_protected"] = protected
    if label is not None:
        cfg["_label"] = label
    if ref is not None:
        cfg["_ref"] = ref

    resolved: str | None = None
    if isinstance(ref, int):
        try:
            resolved = sequence.effect_db.get(ref)  # type: ignore[attr-defined]
        except Exception:
            resolved = None
        if resolved is not None:
            resolved = clean_effectdb_settings(resolved)
            cfg["_effectdb_settings"] = resolved

    return cfg, (ref if isinstance(ref, int) else None), resolved


def extract_effect_events_from_sequence(
    sequence: XSequence,
    config_mode: ConfigMode,
) -> list[EffectEventOut]:
    events: list[EffectEventOut] = []

    for elem in sequence.element_effects:
        target_name = elem.element_name

        for layer in elem.layers:
            layer_index = layer.index
            layer_name = layer.name or f"layer_{layer_index}"

            for eff in layer.effects:
                cfg_dict, eff_ref, eff_ref_settings = build_effect_config_dict(sequence, eff)

                if config_mode == "plain":
                    fp = config_fingerprint(cfg_dict)
                    out = EffectEventOut(
                        effect_event_id=str(uuid.uuid4()),
                        target_name=target_name,
                        target_type=None,  # stripped until enrichment
                        layer_index=layer_index,
                        layer_name=layer_name,
                        effect_type=eff.effect_type,
                        start_ms=eff.start_time_ms,
                        end_ms=eff.end_time_ms,
                        config_codec=None,
                        config_fingerprint=fp,
                        config_blob_b64=None,
                        effectdb_ref=eff_ref,
                        effectdb_settings=eff_ref_settings,
                        palette=eff.palette,
                        protected=eff.protected,
                        label=eff.label,
                    )
                else:
                    codec, fp, blob_b64 = compress_config(cfg_dict)
                    out = EffectEventOut(
                        effect_event_id=str(uuid.uuid4()),
                        target_name=target_name,
                        target_type=None,  # stripped until enrichment
                        layer_index=layer_index,
                        layer_name=layer_name,
                        effect_type=eff.effect_type,
                        start_ms=eff.start_time_ms,
                        end_ms=eff.end_time_ms,
                        config_codec=codec,
                        config_fingerprint=fp,
                        config_blob_b64=blob_b64,
                        effectdb_ref=eff_ref,
                        effectdb_settings=eff_ref_settings,
                        palette=eff.palette,
                        protected=eff.protected,
                        label=eff.label,
                    )

                events.append(out)

    events.sort(key=lambda e: (e.start_ms, e.layer_name, e.target_name, e.effect_type))
    return events


def asset_and_shader_inventory(manifest: PackageManifest) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    shaders: list[dict[str, Any]] = []

    for f in manifest.files:
        if f.kind == "asset":
            assets.append(
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "asset_type": infer_asset_type(f.filename),
                }
            )
        elif f.kind == "shader":
            shaders.append(
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "shader_type": Path(f.filename).suffix.lower(),
                }
            )

    return {"assets": assets, "shaders": shaders}


# -------------------------------------------------
# Stage C: rgb_effects.xml -> LayoutSemantics (placeholder extractor)
# -------------------------------------------------


def parse_rgb_effects_layout(rgb_path: Path, rgb_file_id: str) -> tuple[str, str, list[TargetFact]]:
    rgb_sha = sha256_file(rgb_path)
    layout_id = str(uuid.uuid4())

    xml = rgb_path.read_text(encoding="utf-8", errors="ignore")
    root = ET.fromstring(xml)

    targets: list[TargetFact] = []

    def sf(node: ET.Element, k: str) -> float | None:
        v = node.attrib.get(k) or node.attrib.get(k.capitalize())
        if v is None:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    for n in root.iter():
        name = n.attrib.get("name") or n.attrib.get("Name")
        if not name:
            continue

        tag = n.tag.lower()
        kind = "unknown"
        if "group" in tag:
            kind = "group"
        elif "model" in tag:
            kind = "model"

        x = sf(n, "x")
        y = sf(n, "y")
        w = sf(n, "w") or sf(n, "width")
        h = sf(n, "h") or sf(n, "height")

        x0 = x
        y0 = y
        x1 = (x + w) if (x is not None and w is not None) else None
        y1 = (y + h) if (y is not None and h is not None) else None
        cx = (x0 + x1) / 2.0 if (x0 is not None and x1 is not None) else None
        cy = (y0 + y1) / 2.0 if (y0 is not None and y1 is not None) else None

        targets.append(
            TargetFact(
                layout_id=layout_id,
                rgb_effects_file_id=rgb_file_id,
                rgb_effects_sha256=rgb_sha,
                target_name=str(name),
                target_kind=kind,
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                cx=cx,
                cy=cy,
            )
        )

    # de-dupe by name
    seen: set[str] = set()
    uniq: list[TargetFact] = []
    for t in targets:
        if t.target_name in seen:
            continue
        seen.add(t.target_name)
        uniq.append(t)

    return layout_id, rgb_sha, uniq


# -------------------------------------------------
# Stage D: Join events to layout facts (simple name join)
# -------------------------------------------------


def enrich_events(events: list[EffectEventOut], targets: list[TargetFact]) -> list[dict[str, Any]]:
    by_name = {t.target_name: t for t in targets}
    out: list[dict[str, Any]] = []

    for e in events:
        row = e.model_dump(exclude_none=True)
        t = by_name.get(e.target_name)
        if t is not None:
            row.update(
                {
                    "layout_id": t.layout_id,
                    "rgb_effects_sha256": t.rgb_effects_sha256,
                    "target_kind_resolved": t.target_kind,
                    "target_x0": t.x0,
                    "target_y0": t.y0,
                    "target_x1": t.x1,
                    "target_y1": t.y1,
                    "target_cx": t.cx,
                    "target_cy": t.cy,
                }
            )

        duration = max(0, e.end_ms - e.start_ms)
        row["feat_duration_ms"] = duration

        out.append(strip_nulls(row))

    return out


# -------------------------------------------------
# Orchestration
# -------------------------------------------------


def main(zip_path: str, out_dir: str, config_mode: ConfigMode) -> None:
    repo_root = default_repo_root()

    zip_p = repo_root / Path(zip_path)
    out_p = repo_root / Path(out_dir)

    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(out_p)

    out_p.mkdir(parents=True, exist_ok=True)

    manifest = ingest_zip(zip_p)
    write_json(out_p / "package_manifest.json", manifest.model_dump(exclude_none=True))

    extracted_dir = out_p / "extracted"
    extract_zip_flat(zip_p, extracted_dir)

    files_by_id = {f.file_id: f for f in manifest.files}

    if manifest.sequence_file_id is None:
        raise RuntimeError(f"No .xsq/.seq found in zip: {zip_p}")

    seq_file = files_by_id[manifest.sequence_file_id]
    seq_path = extracted_dir / seq_file.filename
    seq_sha = seq_file.sha256

    # Parse XSQ using your parser
    parser = XSQParser()
    sequence: XSequence = parser.parse(seq_path)

    # Sequence metadata + inventories
    seq_meta = {
        "package_id": manifest.package_id,
        "sequence_file_id": seq_file.file_id,
        "sequence_sha256": seq_sha,
        "xlights_version": sequence.head.version,
        "sequence_duration_ms": sequence.head.sequence_duration_ms,
        "media_file": Path(sequence.head.media_file).name,
        "image_dir": Path(sequence.head.image_dir).name if sequence.head.image_dir else "",
        "song": sequence.head.song,
        "artist": sequence.head.artist,
        "album": sequence.head.album,
        "author": sequence.head.author,
    }
    write_json(out_p / "sequence_metadata.json", seq_meta)

    # Color Palettes
    color_palettes = parse_color_palettes_from_sequence(seq_path)
    write_json(out_p / "color_palettes.json", color_palettes)

    inv = asset_and_shader_inventory(manifest)
    write_json(out_p / "asset_inventory.json", inv["assets"])
    write_json(out_p / "shader_inventory.json", inv["shaders"])

    # Extract Base Effect Events from parsed model
    events = extract_effect_events_from_sequence(sequence=sequence, config_mode=config_mode)

    base_events_file = BaseEffectEventsFile(
        package_id=manifest.package_id,
        sequence_file_id=seq_file.file_id,
        sequence_sha256=seq_sha,
        config_mode=config_mode,
        events=events,
    )
    write_json(
        out_p / "base_effect_events.json",
        base_events_file.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True),
    )

    # rgb_effects semantics (optional + cached by sha)
    targets: list[TargetFact] = []
    layout_id: str | None = None
    rgb_sha: str | None = None

    if manifest.rgb_effects_file_id is not None:
        rgb_file = files_by_id[manifest.rgb_effects_file_id]
        rgb_path = extracted_dir / rgb_file.filename

        cache_dir = out_p / "rgb_cache"
        cache_dir.mkdir(exist_ok=True)
        cache_key = rgb_file.sha256
        cache_hit = cache_dir / f"{cache_key}.json"

        if cache_hit.exists():
            data = json.loads(cache_hit.read_text(encoding="utf-8"))
            layout_id = data["layout_id"]
            rgb_sha = data["rgb_sha256"]
            targets = [TargetFact(**t) for t in data["targets"]]
        else:
            layout_id, rgb_sha, targets = parse_rgb_effects_layout(rgb_path, rgb_file.file_id)
            cache_hit.write_text(
                json.dumps(
                    {
                        "layout_id": layout_id,
                        "rgb_sha256": rgb_sha,
                        "targets": [
                            t.model_dump(
                                exclude_none=True, exclude_unset=True, exclude_defaults=True
                            )
                            for t in targets
                        ],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        write_json(
            out_p / "layout_semantics.json",
            {
                "layout_id": layout_id,
                "rgb_sha256": rgb_sha,
                "targets": [
                    t.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)
                    for t in targets
                ],
            },
        )
    else:
        write_json(
            out_p / "layout_semantics.json", {"layout_id": None, "rgb_sha256": None, "targets": []}
        )

    # Join
    enriched = enrich_events(events, targets)
    write_json(out_p / "enriched_effect_events.json", enriched)

    # quick lineage pointers
    lineage = {
        "package_id": manifest.package_id,
        "zip_sha256": manifest.zip_sha256,
        "sequence_file": seq_file.model_dump(exclude_none=True),
        "rgb_effects_file": files_by_id[manifest.rgb_effects_file_id].model_dump(exclude_none=True)
        if manifest.rgb_effects_file_id
        else None,
        "layout_id": layout_id,
        "rgb_sha256": rgb_sha,
        "config_mode": config_mode,
        "effect_event_ids": [e.effect_event_id for e in events],
    }
    write_json(out_p / "lineage_index.json", lineage)


if __name__ == "__main__":
    # "plain" or "compressed"
    # zip_path = "data/vendor_packages/example.zip"
    for x in range(1, 14):
        zip_path = f"data/vendor_packages/example{x}.zip"
        out_dir = f"data/test/example{x}"
        config_mode: ConfigMode = "plain"
        try:
            main(zip_path, out_dir, config_mode)
        except RuntimeError as e:
            logger.warning("Skipping example%d: %s", x, e)
            continue
