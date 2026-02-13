"""
twinklr_illustrations.py

Single-module, repeatable illustration rendering pipeline for the Twinklr blog.

- Uses OpenAI Image API (model: gpt-image-1.5) via openai-python.
- Loads a manifest JSON (generated from ILLUSTRATION_INDEX_v2.md).
- Renders drafts (N variants) and finals (chosen variant per illustration).
- Writes PNGs to paths specified in the manifest.

Requirements:
  pip install "openai>=1.5.0" "pydantic>=2.0"

Auth:
  export OPENAI_API_KEY="..."

Quickstart:
  python twinklr_illustrations.py convert-index --index ILLUSTRATION_INDEX_v2.md --out illustrations.manifest.json
  python twinklr_illustrations.py render --manifest illustrations.manifest.json --mode drafts
  # review drafts, then create selections.json (example in README)
  python twinklr_illustrations.py render --manifest illustrations.manifest.json --mode finals --selections selections.json
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path
import re
from typing import TYPE_CHECKING, Literal, cast

# OpenAI Python SDK (v1.5+ pattern)
# Docs: https://platform.openai.com/docs/api-reference/images
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from openai import OpenAI

# ---------------------------------------------------------------------------
# Centralized style packs (injected into every prompt)
# ---------------------------------------------------------------------------
# The manifest 'prompt' should be CONTENT-ONLY (scene description).
# This module will prepend the selected style pack based on `asset.style_profile`.
#
# You can add new profiles here and flip an illustration by changing style_profile.
#
# Format: value may be a string (single pack) OR a dict with keys:
#   - "base": required (applies to all)
#   - optional per-type keys: "banner", "hero", "micro", "diagram"
#
STYLE_MARKER_PREFIX = "[TWINKLR_STYLE_PACK:"

STYLE_PACKS: dict[str, object] = {
    "twinklr_sketch_dark_v1": {
        "base": """STYLE: hand-drawn technical sketch / whiteboard vibe, high-contrast on a dark background.
LOOK: clean lines, readable labels, minimal clutter, playful personality.
PALETTE: dark charcoal background; accents in cool cyan/blue + warm amber/red (sparingly).
LIGHTING: if beams/fixtures are present, show visible light beams with subtle haze; avoid concert neon.
COMPOSITION: strong silhouette + clear focal point; leave comfortable margins for cropping.
CONSTRAINTS: no text blocks, no logos, no watermarks; avoid tiny details; avoid photoreal faces; keep it diagram-readable.
OUTPUT: a single PNG illustration, crisp edges, high readability at 800px wide.""",
        "banner": """BANNER FRAMING: wide composition, with a clear top area for title overlay (empty negative space).""",
        "hero": """HERO FRAMING: cinematic but still diagram-readable; emphasize the 'wow' moment.""",
        "micro": """MICRO-ILLUSTRATION: simple icon-like vignette; 1 concept only; large shapes.""",
        "diagram": """DIAGRAM: emphasize structure, arrows, labels, and clear grouping; minimal decoration.""",
    },
}

DEFAULT_STYLE_PROFILE = "twinklr_sketch_dark_v1"

# Draft output directory (relative to out_root / repo root)
DRAFT_DIR = Path("data/blog/assets/_draft")

# Maximum number of concurrent OpenAI image API calls.
# The Images API typically allows ~5-7 RPM; 4 is a safe default.
DEFAULT_CONCURRENCY = 4


def _get_style_pack(asset: IllustrationAsset) -> str:
    """Return the style pack text for an asset's style_profile + type.

    The style profile may be a single string or a dict with keys:
      - base (required)
      - optional per-type overrides: banner/hero/micro/diagram
    """
    entry = STYLE_PACKS.get(asset.style_profile) or STYLE_PACKS[DEFAULT_STYLE_PROFILE]
    if isinstance(entry, str):
        pack = entry
    elif isinstance(entry, dict):
        base = str(entry.get("base", "")).strip()
        per_type = str(entry.get(str(asset.type), "")).strip()
        pack = "\n\n".join([p for p in (base, per_type) if p])
    else:
        pack = ""

    # Background nuance
    if asset.background == "transparent":
        pack = (
            pack + "\nBACKGROUND: transparent (alpha). Keep edges clean; avoid haze at borders."
        ).strip()

    return pack.strip()


def _enforcement_addendum(asset: IllustrationAsset) -> str:
    """Small addendum to enforce: (1) VIEW: so what would I see? and (2) time/motion when requested."""
    raw = (asset.prompt or "").strip()
    lines: list[str] = []

    if not re.search(r"\bVIEW\s*:", raw, flags=re.IGNORECASE):
        lines.append(
            "VIEW: Include a callout labeled 'VIEW:' (1–2 short sentences) describing what the viewer sees from the street at a glance."
        )

    if asset.needs_time and not re.search(
        r"\b(time\s*axis|timeline|frame\s*\d|frames?|t\s*=|ghosted|motion\s*arrows?|trail|step\s*\d)\b",
        raw,
        flags=re.IGNORECASE,
    ):
        lines.append(
            "TIME/MOTION: Depict motion explicitly using ONE: (a) 3–4 frame strip left→right, (b) ghosted positions + arrows, or (c) a timeline axis with states."
        )

    if asset.needs_labels and not re.search(
        r"\b(label|labels|annotat|callout|arrow)\b", raw, flags=re.IGNORECASE
    ):
        lines.append(
            "LABELS: Add minimal large labels/arrows where useful. Keep labels short and legible."
        )

    return "\n".join(lines).strip()


def build_final_prompt(asset: IllustrationAsset) -> str:
    """Compose the final prompt sent to the image model.

    - Prepends a centralized style pack (unless already present)
    - Appends small enforcement addenda for VIEW/time/labels if missing
    """
    raw = (asset.prompt or "").strip()
    if STYLE_MARKER_PREFIX in raw:
        return raw

    style_pack = _get_style_pack(asset)
    addendum = _enforcement_addendum(asset)

    parts: list[str] = [
        f"{STYLE_MARKER_PREFIX}{asset.style_profile}]",
        style_pack,
        "SCENE:",
        raw,
    ]
    if addendum:
        parts.extend(["", "ENFORCEMENTS:", addendum])

    return "\n".join([p for p in parts if p]).strip()


# -----------------------------
# Pydantic schema
# -----------------------------

ImageSize = Literal["1024x1024", "1024x1536", "1536x1024", "auto"]
RenderMode = Literal["drafts", "finals"]
IllustrationType = Literal["banner", "hero", "micro", "diagram"]


class IllustrationAsset(BaseModel):
    """Single illustration asset spec."""

    id: str = Field(..., description="Unique ID, e.g. ILL-01-04")
    title: str
    post_part: int = Field(..., ge=0, le=99)
    file: str = Field(..., description="Output file path (relative to repo root)")
    placement: str
    alt: str
    prompt: str = Field(
        ...,
        description="Content prompt (scene + labels + composition). Style pack and VIEW/time enforcements are injected by the renderer module unless already present.",
    )
    style_profile: str = "twinklr_sketch_dark_v1"

    model: str = Field(default="gpt-image-1.5")
    size: ImageSize = Field(default="1536x1024")
    type: IllustrationType = Field(default="micro")

    variants: int = Field(default=6, ge=1, le=20)
    needs_time: bool = False
    needs_labels: bool = True

    # Optional knobs
    # OpenAI Images API accepts: transparent|opaque|auto (GPT image models).
    background: Literal["transparent", "opaque", "auto"] | None = "opaque"
    output_format: Literal["png", "webp", "jpeg"] | None = "png"
    # API accepts: low|medium|high|auto. citeturn0search3
    quality: Literal["low", "medium", "high", "auto"] | None = "high"


class IllustrationManifest(BaseModel):
    schema_version: str = "twinklr.illustrations.manifest.v1"
    generated_at: str | None = None
    count: int = 0
    illustrations: list[IllustrationAsset]


class RenderSelections(BaseModel):
    """Mapping of illustration id -> chosen draft variant index (1-based)."""

    selections: dict[str, int] = Field(default_factory=dict)


# -----------------------------
# Index (MD) -> manifest conversion
# -----------------------------


def parse_index_markdown(index_md: str) -> IllustrationManifest:
    """
    Parse ILLUSTRATION_INDEX_v2.md style markdown into a manifest.

    Expected entry format:

    ### ILL-01-04 — Title
    **File:** `assets/illustrations/01_snap_to_grid.png`
    **Placement:** ...
    **Alt text:** ...
    **Description / Prompt:**
    ...
    ---
    """
    chunks = re.split(r"(?m)^###\s+(ILL-\d{2}-\d{2})\s+—\s+", index_md)
    assets: list[IllustrationAsset] = []

    for i in range(1, len(chunks), 2):
        ill_id = chunks[i].strip()
        rest = chunks[i + 1]
        title = rest.splitlines()[0].strip()
        file_m = re.search(r"\*\*File:\*\*\s+`([^`]+)`", rest)
        placement_m = re.search(r"\*\*Placement:\*\*\s+(.+)", rest)
        alt_m = re.search(r"\*\*Alt text:\*\*\s+(.+)", rest)
        prompt_m = re.search(
            r"\*\*Description\s*/\s*Prompt:\*\*\s*\n(.*?)(?=\n---\n|\n## Part|\Z)",
            rest,
            flags=re.S,
        )

        file_path = file_m.group(1).strip() if file_m else f"assets/illustrations/{ill_id}.png"
        placement = placement_m.group(1).strip() if placement_m else ""
        alt = alt_m.group(1).strip() if alt_m else ""
        prompt = (prompt_m.group(1).strip() if prompt_m else "").strip()

        part_num = int(ill_id.split("-")[1])
        typ: IllustrationType = "micro"
        if ill_id.endswith("-00"):
            typ = "banner"
        elif "hero" in title.lower():
            typ = "hero"

        size: ImageSize = "1536x1024" if typ in ("banner", "hero", "diagram") else "1024x1024"
        variants = 4 if typ == "banner" else 6

        assets.append(
            IllustrationAsset(
                id=ill_id,
                title=title,
                post_part=part_num,
                file=file_path,
                placement=placement,
                alt=alt,
                prompt=prompt,
                type=typ,
                size=size,
                variants=variants,
                needs_time=bool(re.search(r"\btime\b|\bmotion\b|VIEW:", prompt, flags=re.I)),
                needs_labels=True,
            )
        )

    return IllustrationManifest(
        count=len(assets),
        illustrations=assets,
    )


# -----------------------------
# Rendering
# -----------------------------


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def openai_generate_png(
    client: OpenAI,
    prompt: str,
    model: str,
    size: ImageSize,
    background: Literal["transparent", "opaque", "auto"] | None,
    output_format: Literal["png", "webp", "jpeg"],
    quality: Literal["low", "medium", "high", "auto"] | None,
) -> bytes:
    """
    Call the OpenAI Images API and return PNG bytes.

    API ref: https://platform.openai.com/docs/api-reference/images/create
    """
    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        n=1,
        background=background,
        output_format=output_format,
        quality=quality,
    )
    # GPT image models return base64 by default.
    if not resp.data or len(resp.data) == 0:
        raise RuntimeError("Image API returned no image data.")
    b64 = resp.data[0].b64_json
    if b64 is None:
        raise RuntimeError(
            "Image API did not return b64_json for this request. Ensure you are using a GPT image model (e.g. gpt-image-1.5)."
        )
    return base64.b64decode(b64)


async def openai_generate_png_async(
    client: AsyncOpenAI,
    prompt: str,
    model: str,
    size: ImageSize,
    background: Literal["transparent", "opaque", "auto"] | None,
    output_format: Literal["png", "webp", "jpeg"],
    quality: Literal["low", "medium", "high", "auto"] | None,
) -> bytes:
    """Async variant of :func:`openai_generate_png`.

    Uses :class:`AsyncOpenAI` so multiple calls can run concurrently
    behind an ``asyncio.Semaphore``.
    """
    resp = await client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        n=1,
        background=background,
        output_format=output_format,
        quality=quality,
    )
    if not resp.data or len(resp.data) == 0:
        raise RuntimeError("Image API returned no image data.")
    b64 = resp.data[0].b64_json
    if b64 is None:
        raise RuntimeError(
            "Image API did not return b64_json for this request. "
            "Ensure you are using a GPT image model (e.g. gpt-image-1.5)."
        )
    return base64.b64decode(b64)


async def _render_single(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    prompt: str,
    model: str,
    size: ImageSize,
    background: Literal["transparent", "opaque", "auto"] | None,
    output_format: Literal["png", "webp", "jpeg"],
    quality: Literal["low", "medium", "high", "auto"] | None,
    out_path: Path,
    label: str,
    dry_run: bool = False,
) -> None:
    """Render a single image, respecting the concurrency semaphore.

    Skips generation when the output file already exists on disk.
    """
    if out_path.exists():
        print(f"[SKIP] {label} — already exists at {out_path}")
        return

    ensure_parent(out_path)

    if dry_run:
        print(f"[DRY] {label} -> {out_path}")
        return

    async with sem:
        img_bytes = await openai_generate_png_async(
            client=client,
            prompt=prompt,
            model=model,
            size=size,
            background=background,
            output_format=output_format,
            quality=quality,
        )
    out_path.write_bytes(img_bytes)
    print(f"[OK] {label} -> {out_path}")


async def render_manifest(
    manifest: IllustrationManifest,
    mode: RenderMode,
    out_root: Path,
    selections: RenderSelections | None = None,
    dry_run: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> None:
    """Render all illustrations in the manifest with parallel API calls.

    Args:
        manifest: The illustration manifest to render.
        mode: ``"drafts"`` renders N variants per asset; ``"finals"`` renders
            the chosen variant into its manifest path.
        out_root: Repository root (or any base directory for output paths).
        selections: Required for ``finals`` mode — maps illustration ID to
            1-based variant index.
        dry_run: If ``True``, print planned actions without calling the API.
        concurrency: Maximum number of concurrent OpenAI image API calls.
    """
    client = AsyncOpenAI()
    sem = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[None]] = []

    for asset in manifest.illustrations:
        ofmt = cast("Literal['png', 'webp', 'jpeg']", asset.output_format or "png")
        qual = cast("Literal['low', 'medium', 'high', 'auto']", asset.quality or "high")
        prompt = build_final_prompt(asset)

        if mode == "drafts":
            # Drafts use opaque background for quick visual review.
            bg = cast(
                "Literal['transparent', 'opaque', 'auto'] | None",
                asset.background or "opaque",
            )
            # Drafts go into DRAFT_DIR / ILL-ID / v1..vN.png
            for v in range(1, asset.variants + 1):
                out_path = out_root / DRAFT_DIR / asset.id / f"v{v}.png"
                label = f"draft {asset.id} v{v}"
                tasks.append(
                    asyncio.create_task(
                        _render_single(
                            client=client,
                            sem=sem,
                            prompt=prompt,
                            model=asset.model,
                            size=asset.size,
                            background=bg,
                            output_format=ofmt,
                            quality=qual,
                            out_path=out_path,
                            label=label,
                            dry_run=dry_run,
                        )
                    )
                )

        elif mode == "finals":
            if selections is None or asset.id not in selections.selections:
                print(f"[SKIP] no selection for {asset.id}")
                continue

            chosen = selections.selections[asset.id]
            if chosen < 1:
                print(f"[SKIP] {asset.id} — selection is {chosen} (not yet chosen)")
                continue

            # Finals always render with opaque background for compositing.
            final_bg: Literal["transparent", "opaque", "auto"] | None = "opaque"

            # Re-render final into the manifest path (relative to repo root)
            rel_out = Path(asset.file)
            out_path = out_root / rel_out
            label = f"final {asset.id} (v{chosen})"
            tasks.append(
                asyncio.create_task(
                    _render_single(
                        client=client,
                        sem=sem,
                        prompt=prompt,
                        model=asset.model,
                        size=asset.size,
                        background=final_bg,
                        output_format=ofmt,
                        quality=qual,
                        out_path=out_path,
                        label=label,
                        dry_run=dry_run,
                    )
                )
            )

        else:
            raise ValueError(f"Unknown mode: {mode}")

    if tasks:
        print(f"[INFO] Dispatching {len(tasks)} render tasks (concurrency={concurrency})…")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            print(f"\n[WARN] {len(errors)} task(s) failed:")
            for err in errors:
                print(f"  - {err}")
            raise RuntimeError(f"{len(errors)} render task(s) failed. See output above.")


# -----------------------------
# CLI
# -----------------------------


def cmd_convert_index(args: argparse.Namespace) -> None:
    md = Path(args.index).read_text(encoding="utf-8")
    manifest = parse_index_markdown(md)
    out = Path(args.out)
    ensure_parent(out)
    out.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    print(f"[OK] wrote manifest: {out} ({manifest.count} illustrations)")


def cmd_render(args: argparse.Namespace) -> None:
    manifest = IllustrationManifest.model_validate_json(
        Path(args.manifest).read_text(encoding="utf-8")
    )

    selections = None
    if args.selections:
        selections = RenderSelections.model_validate_json(
            Path(args.selections).read_text(encoding="utf-8")
        )

    out_root = Path(args.out_root)
    asyncio.run(
        render_manifest(
            manifest=manifest,
            mode=args.mode,
            out_root=out_root,
            selections=selections,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Twinklr blog illustration renderer (OpenAI Images API, v1.5)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser(
        "convert-index", help="Convert Illustration Index markdown into manifest JSON."
    )
    c.add_argument("--index", required=True, help="Path to ILLUSTRATION_INDEX_v2.md")
    c.add_argument("--out", required=True, help="Path to write illustrations.manifest.json")
    c.set_defaults(func=cmd_convert_index)

    r = sub.add_parser("render", help="Render drafts or finals from a manifest.")
    r.add_argument("--manifest", required=True, help="Path to illustrations.manifest.json")
    r.add_argument("--mode", required=True, choices=["drafts", "finals"])
    r.add_argument("--out-root", default=".", help="Repo root to write outputs into (default: .)")
    r.add_argument(
        "--selections", default=None, help="Path to selections.json (required for finals)"
    )
    r.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Max concurrent OpenAI image API calls (default: {DEFAULT_CONCURRENCY})",
    )
    r.add_argument(
        "--dry-run", action="store_true", help="Print what would happen without calling the API"
    )
    r.set_defaults(func=cmd_render)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
