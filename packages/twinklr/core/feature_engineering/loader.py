"""Load persisted FE artifacts into a typed bundle for downstream consumption."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from twinklr.core.feature_engineering.color_discovery import DiscoveredPalette, HueBin
from twinklr.core.feature_engineering.embeddings.models import SimilarityLink
from twinklr.core.feature_engineering.models.adapters import SequencerAdapterBundle
from twinklr.core.feature_engineering.models.color_arc import SongColorArc
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_engineering.models.style import StyleFingerprint
from twinklr.core.feature_engineering.models.transitions import TransitionGraph
from twinklr.core.feature_engineering.models.vocabulary import VocabularyExtensions
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

logger = logging.getLogger(__name__)


class FEArtifactBundle(BaseModel):
    """Typed bundle of loaded FE artifacts for downstream consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_catalog_entries: tuple[EffectRecipe, ...] = ()
    color_arc: SongColorArc | None = None
    propensity_index: PropensityIndex | None = None
    style_fingerprint: StyleFingerprint | None = None
    transition_graph: TransitionGraph | None = None
    motif_catalog: MotifCatalog | None = None
    adapter_payloads: tuple[SequencerAdapterBundle, ...] = ()
    vocabulary_extensions: VocabularyExtensions | None = None
    color_palette_library: tuple[DiscoveredPalette, ...] = ()
    color_narrative: tuple[ColorNarrativeRow, ...] = ()
    similarity_links: tuple[SimilarityLink, ...] = ()
    sequence_embedding: tuple[float, ...] | None = None
    transition_model_v2_path: str | None = None


def _read_json(path: Path) -> dict:
    """Read a JSON file and return the parsed dict."""
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _load_optional_model(
    manifest: dict[str, str],
    key: str,
    model_cls: type[BaseModel],
    fe_dir: Path,
) -> BaseModel | None:
    """Load a Pydantic model from the manifest if the key exists."""
    rel_path = manifest.get(key)
    if not rel_path:
        return None
    full = Path(rel_path)
    if not full.is_absolute():
        full = fe_dir / full
    if not full.exists():
        logger.warning("FE artifact listed in manifest but missing: %s", full)
        return None
    data = _read_json(full)
    return model_cls.model_validate(data)


def load_fe_artifacts(fe_output_dir: Path) -> FEArtifactBundle:
    """Load all FE artifacts from a feature store output directory.

    Reads ``feature_store_manifest.json`` to discover artifact paths,
    then loads each typed artifact.  Missing artifacts gracefully
    default to ``None`` / empty tuples.

    Args:
        fe_output_dir: Root directory of FE output (contains manifest).

    Returns:
        Typed bundle with all available FE data.
    """
    manifest_path = fe_output_dir / "feature_store_manifest.json"
    if not manifest_path.exists():
        logger.warning("No feature_store_manifest.json in %s", fe_output_dir)
        return FEArtifactBundle()

    manifest: dict[str, str] = _read_json(manifest_path)

    color_arc = _load_optional_model(manifest, "color_arc", SongColorArc, fe_output_dir)
    propensity = _load_optional_model(manifest, "propensity_index", PropensityIndex, fe_output_dir)
    style = _load_optional_model(manifest, "style_fingerprint", StyleFingerprint, fe_output_dir)
    transition = _load_optional_model(manifest, "transition_graph", TransitionGraph, fe_output_dir)
    motif = _load_optional_model(manifest, "motif_catalog", MotifCatalog, fe_output_dir)

    recipes = _load_recipe_catalog(manifest, fe_output_dir)
    adapters = _load_adapter_payloads(manifest, fe_output_dir)
    vocabulary_extensions = _load_optional_model(
        manifest, "vocabulary_extensions", VocabularyExtensions, fe_output_dir
    )
    palettes = _load_discovered_palettes(manifest, fe_output_dir)
    narrative = _load_color_narrative(manifest, fe_output_dir)

    # Transition model V2 path (written by MarkovTransitionModel.save)
    transition_v2_path = manifest.get("transition_model_v2")

    return FEArtifactBundle(
        recipe_catalog_entries=tuple(recipes),
        color_arc=color_arc,  # type: ignore[arg-type]
        propensity_index=propensity,  # type: ignore[arg-type]
        style_fingerprint=style,  # type: ignore[arg-type]
        transition_graph=transition,  # type: ignore[arg-type]
        motif_catalog=motif,  # type: ignore[arg-type]
        adapter_payloads=tuple(adapters),
        vocabulary_extensions=vocabulary_extensions,  # type: ignore[arg-type]
        color_palette_library=palettes,
        color_narrative=narrative,
        transition_model_v2_path=transition_v2_path,
    )


def _load_discovered_palettes(
    manifest: dict[str, str],
    fe_dir: Path,
) -> tuple[DiscoveredPalette, ...]:
    """Load color palettes from the palette library artifact.

    Args:
        manifest: Parsed feature_store_manifest.json dict.
        fe_dir: Root FE output directory for resolving relative paths.

    Returns:
        Tuple of DiscoveredPalette instances, or empty tuple if absent/missing.
    """
    rel_path = manifest.get("color_palette_library")
    if not rel_path:
        return ()
    full = Path(rel_path)
    if not full.is_absolute():
        full = fe_dir / rel_path
    if not full.exists():
        logger.warning("color_palette_library listed in manifest but missing: %s", full)
        return ()
    data = _read_json(full)
    palettes: list[DiscoveredPalette] = []
    for p in data.get("palettes", []):
        hue_bins = tuple(
            HueBin(bin_name=hb["bin_name"], colors=tuple(hb["colors"]))
            for hb in p.get("hue_bins", [])
        )
        palettes.append(
            DiscoveredPalette(
                scope_key=tuple(p["scope_key"]),
                colors=tuple(p["colors"]),
                name=p["name"],
                hue_bins=hue_bins,
            )
        )
    return tuple(palettes)


def _load_color_narrative(
    manifest: dict[str, str],
    fe_dir: Path,
) -> tuple[ColorNarrativeRow, ...]:
    """Load color narrative rows from the color narrative artifact.

    Args:
        manifest: Parsed feature_store_manifest.json dict.
        fe_dir: Root FE output directory for resolving relative paths.

    Returns:
        Tuple of ColorNarrativeRow instances, or empty tuple if absent/missing.
    """
    rel_path = manifest.get("color_narrative")
    if not rel_path:
        return ()
    full = Path(rel_path)
    if not full.is_absolute():
        full = fe_dir / rel_path
    if not full.exists():
        logger.warning("color_narrative listed in manifest but missing: %s", full)
        return ()
    # Support both JSON (single doc / array) and JSONL (one object per line)
    if full.suffix == ".jsonl":
        rows: list[dict] = []
        with full.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    else:
        data = _read_json(full)
        rows = data if isinstance(data, list) else data.get("rows", [])
    return tuple(ColorNarrativeRow.model_validate(r) for r in rows)


def _load_recipe_catalog(
    manifest: dict[str, str],
    fe_dir: Path,
) -> list[EffectRecipe]:
    """Load promoted recipes from the recipe catalog artifact."""
    rel_path = manifest.get("recipe_catalog")
    if not rel_path:
        return []
    full = Path(rel_path)
    if not full.is_absolute():
        full = fe_dir / full
    if not full.exists():
        logger.warning("recipe_catalog listed in manifest but missing: %s", full)
        return []
    data = _read_json(full)
    raw_recipes = data.get("recipes", [])
    return [EffectRecipe.model_validate(r) for r in raw_recipes]


def _load_adapter_payloads(
    manifest: dict[str, str],
    fe_dir: Path,
) -> list[SequencerAdapterBundle]:
    """Load adapter payloads from JSONL file."""
    rel_path = manifest.get("planner_adapter_payloads")
    if not rel_path:
        return []
    full = Path(rel_path)
    if not full.is_absolute():
        full = fe_dir / full
    if not full.exists():
        logger.warning("adapter payloads listed in manifest but missing: %s", full)
        return []
    results: list[SequencerAdapterBundle] = []
    with full.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                results.append(SequencerAdapterBundle.model_validate(json.loads(line)))
    return results
