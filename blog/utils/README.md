# Twinklr Blog — Illustration Rendering Pipeline (OpenAI Image API v1.5)

This package turns `ILLUSTRATION_INDEX_v2.md` into a machine-readable manifest and renders illustrations via the **OpenAI Images API** using model **`gpt-image-1.5`**.

## What you get

- `ILLUSTRATION_INDEX_v2.md` — the human-friendly index you edit
- `illustrations.manifest.json` — the machine-friendly render manifest (generated)
- `twinklr_illustrations.py` — single-module workflow (convert + render)
- `assets/illustrations/` — target output location for finals
- `assets/illustrations/_drafts/` — recommended draft output folder (variants)

## Requirements

- Python 3.9+
- `openai>=1.5.0`
- `pydantic>=2.0`

```bash
pip install "openai>=1.5.0" "pydantic>=2.0"
export OPENAI_API_KEY="YOUR_KEY"
```

## 1) Convert the Illustration Index → Manifest JSON

```bash
python twinklr_illustrations.py convert-index \
  --index ILLUSTRATION_INDEX_v2.md \
  --out illustrations.manifest.json
```

The manifest includes: output file paths, placement, alt text, prompt, model, size, and variant count.

## 2) Render Draft Variants (cheap exploration)

Drafts render `N` variants for each illustration into a folder tree:

```
assets/illustrations/_drafts/
  ILL-01-04/
    v1.png
    v2.png
    ...
```

Run:

```bash
python data/blog/twinklr_illustrations.py render \
  --manifest "data/blog/illustrations.manifest.json" \
  --mode drafts
  --concurrency 8
```

> Tip: if you want drafts elsewhere, set `--out-root` to your repo root and override `asset.file` paths in the manifest, or just copy results back later.

## 3) Pick winners (create `selections.json`)

After reviewing draft variants, create a simple file with 1-based variant indexes:

```json
{
  "selections": {
    "ILL-00-00": 2,
    "ILL-01-04": 5,
    "ILL-06-04": 1
  }
}
```

Save as `selections.json`.

## 4) Render Finals (production images)

Finals re-render the selected variant into the **exact** path in each manifest entry (e.g. `assets/illustrations/01_snap_to_grid.png`).

```bash
python data/blog/twinklr_illustrations.py render \
  --manifest "data/blog/illustrations.manifest.json" \
  --mode finals \
  --selections "data/blog/selections.json" \
  --out-root "data/blog" \
  --concurrency 4
```

## 5) Recommended conventions

### Sizes
The OpenAI Images API supports:
- `1024x1024`
- `1024x1536`
- `1536x1024`
- `auto`

This pipeline defaults to:
- banners/heroes: `1536x1024`
- micro: `1024x1024`

If you want wider banners, generate at `1536x1024` and crop in your site build.

### Prompts
Each prompt in the index should:
- include a **VIEW:** line (“what would the audience see?”)
- show **time/motion** using either a frame strip, ghost frames, or a time axis

## 6) CI integrity check (recommended)

Add a build step that:
- scans blog posts for `<!-- ILLUSTRATION: ILL-XX-NN -->`
- verifies each `ILL-*` exists in the manifest
- verifies every referenced `assets/illustrations/*.png` exists

Fail CI if anything is missing so the series stays consistent.

## API reference

- Images API reference (generate): https://platform.openai.com/docs/api-reference/images/create
- Models: https://platform.openai.com/docs/models
