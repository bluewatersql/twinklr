#!/usr/bin/env python3
"""
img_demo.py

Single-file demo:
1) OpenAI Image API: generate 4 "attempted-consistent" PNG frames (frame0 generate + frames1..3 edits)
2) Pillow tooling demos:
   (1) simple text overlay (Pillow)
   (2) image manipulation: tree warp + seam-safe horizontal tiling (Pillow)
   (3) GIF animated (frames) + falling snow overlay (Pillow)
   (4) Image EDIT with MASK:
       - creates a sky-only mask PNG
       - if OpenAI enabled: calls images.edit(image=..., mask=...) to ONLY modify the sky
       - if --skip-openai: demonstrates the same idea locally by compositing a moon-glow overlay using the mask

Requirements:
  pip install openai pillow

Usage:
  python img_demo.py --out out_demo
  python img_demo.py --out out_demo --skip-openai

Env:
  export OPENAI_API_KEY="..."
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random

from openai import OpenAI
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# -----------------------------
# Prompting (consistency-first)
# -----------------------------

BASE_PROMPT = """
A cozy snowy village at night with warm glowing windows and a decorated Christmas tree.
Style: storybook illustration, simplified, low detail. Theme: traditional Christmas.
Composition: wide depth but uncluttered, large shapes, clear horizon.
Background: opaque.
Lighting: warm window glow against cool snow, strong contrast.
Readability: high contrast, bold shapes, minimal small details.
Avoid: dense textures, complex brick detail, tiny snowflakes, text, watermarks, logos.
Output intent: LED matrix background plate.
""".strip()

CONSISTENCY_ANCHORS = """
Consistency anchors (must hold across all frames):
- Same camera angle, framing, horizon line, and village layout
- Same buildings and window placement; same decorated tree shape and position
- Same color palette and storybook style; bold shapes, clean edges, low detail
- No text/logos/watermarks; no tiny snowflakes
Animation changes must be subtle and localized.
""".strip()

# Scenario 4 prompt: demonstrate *masked edit* (sky-only)
SCENARIO_4_MASKED_EDIT_PROMPT = """
You are editing an existing image using the provided mask.
Only change pixels inside the mask (white/opaque area). Do not change anything outside the mask.

Within the masked SKY region only:
- Add a soft, subtle moon glow (gentle halo).
- Add a few large, soft snow streaks (chunky, LED-friendly), sparse, not dense.

Must keep identical:
- Village layout, buildings, windows, tree silhouette, horizon, snowbanks, palette, and style.

Avoid: new objects, text, logos, watermarks, tiny dotted snow, heavy textures.
""".strip()


@dataclass(frozen=True)
class FramePrompt:
    frame_index: int
    label: str
    prompt: str


def build_frame_prompts() -> list[FramePrompt]:
    # NOTE: Without masks, even edits can drift. This is just to demonstrate calls.
    deltas = [
        ("base", "Base scene, no motion."),
        ("twinkle_1", "Windows glow slightly brighter in a few houses; keep layout identical."),
        ("steam_up", "Chimney steam rises a bit higher; keep everything else identical."),
        (
            "twinkle_2",
            "Tree lights sparkle subtly (larger sparkles, not tiny dots); keep layout identical.",
        ),
    ]

    prompts: list[FramePrompt] = []
    for i, (label, delta) in enumerate(deltas):
        full = "\n\n".join(
            [
                BASE_PROMPT,
                CONSISTENCY_ANCHORS,
                f"Frame-specific change ({label}): {delta}",
            ]
        ).strip()
        prompts.append(FramePrompt(frame_index=i, label=label, prompt=full))
    return prompts


# -----------------------------
# OpenAI Image API helpers
# -----------------------------


def _write_png_from_b64(b64_data: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64_data))


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")


def generate_sequence_frames_openai(
    out_dir: Path,
    prompts: list[FramePrompt],
    *,
    model: str = "gpt-image-1.5",
    size: str = "1536x1024",
) -> list[Path]:
    """
    Frame 0: images.generate(prompt=...)
    Frames 1..: images.edit(image=previous_frame, prompt=...)

    This is a demo of the API calls, not a guaranteed animation workflow.
    For stable animation, prefer scenario 4 (masked edits) or purely-Pillow motion.
    """
    _require_api_key()
    client = OpenAI()

    frames_dir = out_dir / "frames_openai"
    frames_dir.mkdir(parents=True, exist_ok=True)

    out_paths: list[Path] = []

    # Frame 0: fresh generation
    frame0_path = frames_dir / f"frame_00_{prompts[0].label}.png"
    img0 = client.images.generate(
        model=model,
        prompt=prompts[0].prompt,
        n=1,
        size=size,  # pyright: ignore[reportArgumentType]
    )
    _write_png_from_b64(img0.data[0].b64_json, frame0_path)  # pyright: ignore[reportArgumentType, reportOptionalSubscript]
    out_paths.append(frame0_path)

    # Frames 1..: edit-chain continuity
    current_base = frame0_path
    for fp in prompts[1:]:
        out_path = frames_dir / f"frame_{fp.frame_index:02d}_{fp.label}.png"
        with current_base.open("rb") as f_in:
            edited = client.images.edit(
                model=model,
                image=f_in,
                prompt=fp.prompt,
                n=1,
                size=size,  # pyright: ignore[reportArgumentType]
            )
        _write_png_from_b64(edited.data[0].b64_json, out_path)  # pyright: ignore[reportArgumentType, reportOptionalSubscript]
        out_paths.append(out_path)

        # edit-chain continuity:
        current_base = out_path

    return out_paths


def generate_placeholder_frames(out_dir: Path, count: int, size: tuple[int, int]) -> list[Path]:
    """
    Fallback if you run with --skip-openai.
    Creates simple “night village” placeholders so the Pillow demos still run.
    """
    frames_dir = out_dir / "frames_placeholder"
    frames_dir.mkdir(parents=True, exist_ok=True)

    w, h = size
    out_paths: list[Path] = []
    for i in range(count):
        img = Image.new("RGB", (w, h), (10, 20, 40))
        draw = ImageDraw.Draw(img)

        # Snow ground
        draw.rectangle([0, int(h * 0.70), w, h], fill=(230, 235, 245))

        # Village blocks
        rng = random.Random(1000 + i)
        for b in range(6):
            x0 = int((b / 6.0) * w) + 10
            x1 = int(((b + 1) / 6.0) * w) - 10
            y1 = int(h * 0.70)
            y0 = y1 - rng.randint(int(h * 0.18), int(h * 0.30))
            draw.rectangle([x0, y0, x1, y1], fill=(40, 50, 70))
            # Warm windows
            for _ in range(6):
                wx = rng.randint(x0 + 8, x1 - 18)
                wy = rng.randint(y0 + 10, y1 - 20)
                glow = 200 + (i * 10) % 40
                draw.rectangle([wx, wy, wx + 8, wy + 8], fill=(glow, glow - 40, 80))

        # Tree
        tx = int(w * 0.62)
        base_y = int(h * 0.70)
        tri_h = int(h * 0.30)
        draw.polygon(
            [(tx, base_y - tri_h), (tx - int(w * 0.08), base_y), (tx + int(w * 0.08), base_y)],
            fill=(20, 90, 60),
        )
        # Twinkle
        for _ in range(10):
            px = tx + rng.randint(-int(w * 0.06), int(w * 0.06))
            py = base_y - rng.randint(10, tri_h - 10)
            r = rng.randint(3, 6)
            draw.ellipse([px - r, py - r, px + r, py + r], fill=(240, 210, 90))

        out_path = frames_dir / f"frame_{i:02d}.png"
        img.save(out_path, "PNG")
        out_paths.append(out_path)

    return out_paths


# -----------------------------
# Pillow scenario 1: text overlay
# -----------------------------


def add_text_overlay(img: Image.Image, text: str) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()

    pad = 14
    draw.text(
        (pad, pad),
        text,
        font=font,
        fill=(255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )
    return out


# -----------------------------
# Pillow scenario 2: tree warp + seam-safe
# -----------------------------


def warp_tree_region(img: Image.Image) -> Image.Image:
    """
    Gentle horizontal skew of an estimated 'tree region' using a safe affine transform.
    Avoids the smear/tearing you saw with an incorrect MESH transform.
    """
    out = img.copy()
    w, h = out.size

    # Heuristic bbox for tree area (center-right)
    x0 = int(w * 0.52)
    x1 = int(w * 0.74)
    y0 = int(h * 0.28)
    y1 = int(h * 0.88)

    patch = out.crop((x0, y0, x1, y1))
    pw, ph = patch.size

    k = 0.06  # small = subtle warp
    coeffs = (1.0, k, -k * (ph / 2.0), 0.0, 1.0, 0.0)
    warped = patch.transform(
        (pw, ph),
        Image.Transform.AFFINE,
        coeffs,
        resample=Image.Resampling.BICUBIC,
    )

    mask = Image.new("L", (pw, ph), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([8, 8, pw - 8, ph - 8], radius=18, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(6))

    out.paste(warped, (x0, y0), mask)
    return out


def make_seam_safe_horizontal(img: Image.Image, seam_width: int = 96) -> Image.Image:
    """
    True seam-safe horizontal tiling:
    - Offset by half-width (wrap seam to center)
    - Heal/blend the center seam
    - Offset back (edges now match when tiled)
    """
    base = img.convert("RGBA")
    w, h = base.size
    seam_width = max(16, min(seam_width, w // 2))

    off = ImageChops.offset(base, w // 2, 0)

    left_shift = ImageChops.offset(off, -seam_width // 2, 0)
    right_shift = ImageChops.offset(off, seam_width // 2, 0)

    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)

    cx = w // 2
    x0 = cx - seam_width // 2
    x1 = cx + seam_width // 2

    for x in range(x0, x1):
        t = (x - x0) / max(1, (x1 - x0))
        a = int(255 * t)
        md.line([(x, 0), (x, h)], fill=a)

    mask = mask.filter(ImageFilter.GaussianBlur(2))
    healed = Image.composite(right_shift, left_shift, mask)

    final = ImageChops.offset(healed, -(w // 2), 0)
    return final.convert(img.mode)


# -----------------------------
# Pillow scenario 3: GIF + falling snow overlay
# -----------------------------


def iter_snow_particles(seed: int, count: int, w: int, h: int) -> list[tuple[int, int, int]]:
    rng = random.Random(seed)
    parts: list[tuple[int, int, int]] = []
    for _ in range(count):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        r = rng.randint(1, 3)  # chunky snow for LED readability
        parts.append((x, y, r))
    return parts


def add_falling_snow(img: Image.Image, frame_idx: int, *, density: int = 260) -> Image.Image:
    base = img.convert("RGBA")
    w, h = base.size

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    particles = iter_snow_particles(seed=1337, count=density, w=w, h=h)
    dy = (frame_idx * 10) % h

    for x, y, r in particles:
        yy = (y + dy) % h
        a = 140 + ((x + y + frame_idx * 17) % 90)
        draw.ellipse([x - r, yy - r, x + r, yy + r], fill=(255, 255, 255, a))

    layer = layer.filter(ImageFilter.GaussianBlur(0.6))
    return Image.alpha_composite(base, layer).convert("RGB")


def write_gif(frames: list[Image.Image], out_path: Path, duration_ms: int = 120) -> None:
    if len(frames) < 2:
        raise ValueError(f"Need >=2 frames to write an animated GIF, got {len(frames)}")

    first = frames[0].convert("RGBA")
    rest = [f.convert("RGBA") for f in frames[1:]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    first.save(
        out_path,
        save_all=True,
        append_images=rest,
        duration=duration_ms,
        loop=0,
        optimize=False,
        disposal=2,
    )


# -----------------------------
# Scenario 4: image edit/overlay/mask
# -----------------------------


def build_sky_mask_rgba(
    size: tuple[int, int], *, sky_ratio: float = 0.55, feather_px: int = 16
) -> Image.Image:
    """
    Returns an RGBA mask image:
      - White/opaque = editable area
      - Transparent = locked area
    Many image edit APIs interpret mask alpha this way.
    """
    w, h = size
    sky_h = int(h * sky_ratio)

    # Start with transparent everywhere
    mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Editable (white, opaque) in sky region
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, 0, w, sky_h], fill=(255, 255, 255, 255))

    if feather_px > 0:
        # Feather only the alpha channel
        a = mask.split()[-1].filter(ImageFilter.GaussianBlur(radius=float(feather_px)))
        mask = Image.merge("RGBA", (a, a, a, a))

    return mask


def local_masked_overlay_demo(img: Image.Image, mask_rgba: Image.Image) -> Image.Image:
    """
    Demonstrates 'overlay + mask' locally (no OpenAI):
    - Creates a soft moon-glow gradient layer
    - Applies it ONLY within the mask
    """
    base = img.convert("RGBA")
    w, h = base.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Moon glow near upper-right
    cx, cy = int(w * 0.82), int(h * 0.20)
    max_r = int(min(w, h) * 0.25)
    for r in range(max_r, 0, -6):
        t = r / max_r
        # Soft warm-white glow
        alpha = int(120 * (t * t))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 245, 220, alpha))

    overlay = overlay.filter(ImageFilter.GaussianBlur(6))

    # Apply mask alpha to the overlay alpha
    mask_alpha = mask_rgba.split()[-1]
    o_r, o_g, o_b, o_a = overlay.split()
    o_a = ImageChops.multiply(o_a, mask_alpha)
    overlay_masked = Image.merge("RGBA", (o_r, o_g, o_b, o_a))

    out = Image.alpha_composite(base, overlay_masked).convert("RGB")

    # Slightly boost contrast in sky so it reads on LEDs
    out = ImageEnhance.Contrast(out).enhance(1.03)
    return out


def openai_masked_edit(
    *,
    model: str,
    size: str,
    image_path: Path,
    mask_path: Path,
    prompt: str,
    out_path: Path,
) -> None:
    _require_api_key()
    client = OpenAI()

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with image_path.open("rb") as f_img, mask_path.open("rb") as f_mask:
        edited = client.images.edit(
            model=model,
            image=f_img,
            mask=f_mask,
            prompt=prompt,
            n=1,
            size=size,  # pyright: ignore[reportArgumentType]
        )

    _write_png_from_b64(edited.data[0].b64_json, out_path)  # pyright: ignore[reportArgumentType, reportOptionalSubscript]


# -----------------------------
# Main
# -----------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument(
        "--skip-openai", action="store_true", help="Skip OpenAI calls; use placeholders"
    )
    ap.add_argument("--model", default="gpt-image-1.5", help="GPT Image model (e.g. gpt-image-1.5)")
    ap.add_argument("--size", default="1536x1024", help="Image size (e.g. 1536x1024)")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = build_frame_prompts()

    # Persist prompts for traceability
    prompts_json = [
        {"frame_index": p.frame_index, "label": p.label, "prompt": p.prompt} for p in prompts
    ]
    prompts_json.append(
        {
            "frame_index": 999,
            "label": "scenario_4_masked_edit",
            "prompt": SCENARIO_4_MASKED_EDIT_PROMPT,
        }
    )
    (out_dir / "prompts_used.json").write_text(json.dumps(prompts_json, indent=2), encoding="utf-8")

    print("\nPROMPTS USED:\n")
    for p in prompts:
        print(f"\n--- Frame {p.frame_index:02d} ({p.label}) ---\n{p.prompt}\n")
    print(f"\n--- Scenario 4 (masked edit) ---\n{SCENARIO_4_MASKED_EDIT_PROMPT}\n")

    # Generate frames
    if args.skip_openai:
        w_s, h_s = args.size.lower().split("x")
        frame_paths = generate_placeholder_frames(
            out_dir, count=len(prompts), size=(int(w_s), int(h_s))
        )
    else:
        frame_paths = generate_sequence_frames_openai(
            out_dir, prompts, model=args.model, size=args.size
        )

    frames = [Image.open(p).convert("RGB") for p in frame_paths]

    # Scenario 1: text overlay
    overlay_img = add_text_overlay(frames[0], "TWINKLR DEMO • LED MATRIX PLATE")
    overlay_path = out_dir / "scenario_1_text_overlay.png"
    overlay_img.save(overlay_path, "PNG")

    # Scenario 2: tree warp + seam safe horizontal
    warped = warp_tree_region(frames[0])
    seam_safe = make_seam_safe_horizontal(warped, seam_width=72)
    seam_path = out_dir / "scenario_2_tree_warp_seam_safe.png"
    seam_safe.save(seam_path, "PNG")

    # Scenario 3: GIF + falling snow overlay (use all frames as base)
    snow_frames = [add_falling_snow(f, i, density=260) for i, f in enumerate(frames)]
    gif_path = out_dir / "scenario_3_animated_snow.gif"
    write_gif(snow_frames, gif_path, duration_ms=120)

    # Contact sheet (helps you see drift if you used OpenAI multi-frame)
    contact_w, contact_h = frames[0].size
    sheet = Image.new("RGB", (contact_w * len(frames), contact_h), (0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * contact_w, 0))
    sheet_path = out_dir / "frames_contact_sheet.png"
    sheet.save(sheet_path, "PNG")

    # Scenario 4: MASKED edit demo
    # - Build a sky-only mask (save it)
    # - If OpenAI enabled: run images.edit(image, mask, prompt)
    # - If skip-openai: do a local overlay using the same mask concept
    mask_img = build_sky_mask_rgba(frames[0].size, sky_ratio=0.55, feather_px=18)
    mask_path = out_dir / "scenario_4_mask_sky.png"
    mask_img.save(mask_path, "PNG")

    scenario4_out = out_dir / "scenario_4_masked_edit.png"
    if args.skip_openai:
        local = local_masked_overlay_demo(frames[0], mask_img)
        local.save(scenario4_out, "PNG")
    else:
        # Use frame 0 as the base for a locked-layout edit.
        # NOTE: If the model drifts outside the mask, it is a model issue; the prompt strongly requests mask-only edits.
        openai_masked_edit(
            model=args.model,
            size=args.size,
            image_path=frame_paths[0],
            mask_path=mask_path,
            prompt=SCENARIO_4_MASKED_EDIT_PROMPT,
            out_path=scenario4_out,
        )

    print("\nWROTE OUTPUTS:\n")
    print(f"- prompts_used.json: {out_dir / 'prompts_used.json'}")
    for p in frame_paths:
        print(f"- frame: {p}")
    print(f"- scenario 1 (text): {overlay_path}")
    print(f"- scenario 2 (warp+seam): {seam_path}")
    print(f"- scenario 3 (gif+snow): {gif_path}")
    print(f"- contact sheet: {sheet_path}")
    print(f"- scenario 4 (mask): {mask_path}")
    print(f"- scenario 4 (masked edit result): {scenario4_out}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
