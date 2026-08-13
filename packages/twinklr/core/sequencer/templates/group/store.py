"""TemplateStore — JSON-backed template storage.

Loads template metadata from ``catalog/templates/index.json`` (the tracked
catalog root) and lazy-loads full ``EffectRecipe`` objects from individual
JSON files on demand. Optionally merges in a local, untracked
``data/templates/`` overlay via ``from_catalog_with_local_extensions``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
)

logger = logging.getLogger(__name__)

_TYPE_TO_LANE: dict[GroupTemplateType, LaneKind] = {
    GroupTemplateType.BASE: LaneKind.BASE,
    GroupTemplateType.RHYTHM: LaneKind.RHYTHM,
    GroupTemplateType.ACCENT: LaneKind.ACCENT,
}


class TemplateStoreEntry(BaseModel):
    """Lightweight metadata entry from index.json.

    Provides the same interface as ``TemplateInfo`` for catalog compatibility.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_id: str
    name: str
    template_type: GroupTemplateType
    visual_intent: GroupVisualIntent
    tags: tuple[str, ...] = ()
    source: str = "builtin"
    file: str = ""

    @property
    def template_id(self) -> str:
        """Alias for recipe_id used by TemplateCatalog and AffinityScorer."""
        return self.recipe_id

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def compatible_lanes(self) -> list[LaneKind]:
        lane = _TYPE_TO_LANE.get(self.template_type)
        return [lane] if lane else []

    @property
    def description(self) -> str:
        return ""


class TemplateStore:
    """JSON-backed template store.

    Loads metadata from ``index.json`` at construction. Full recipe data
    is lazy-loaded from individual JSON files on first access and cached.
    """

    def __init__(
        self,
        entries: list[TemplateStoreEntry],
        base_dir: Path,
    ) -> None:
        self._entries_by_id: dict[str, TemplateStoreEntry] = {e.recipe_id: e for e in entries}
        self._base_dir = base_dir
        # Per-entry base directory, defaulting to base_dir. Lets merge() combine
        # entries loaded from different directories (see from_catalog_with_local_extensions)
        # while each entry's recipe file still resolves against the directory it came from.
        self._entry_dirs: dict[str, Path] = dict.fromkeys(self._entries_by_id, base_dir)
        self._cache: dict[str, EffectRecipe] = {}

    @classmethod
    def from_directory(cls, directory: Path) -> TemplateStore:
        """Load a TemplateStore from a directory with index.json.

        Args:
            directory: Path containing ``index.json`` and recipe subdirectories.

        Returns:
            Initialized TemplateStore.

        Raises:
            FileNotFoundError: If index.json is missing.
        """
        index_path = directory / "index.json"
        data = json.loads(index_path.read_text(encoding="utf-8"))
        raw_entries: list[dict[str, Any]] = data.get("entries", [])

        entries: list[TemplateStoreEntry] = []
        for raw in raw_entries:
            tags = raw.get("tags", [])
            entries.append(
                TemplateStoreEntry(
                    recipe_id=raw["recipe_id"],
                    name=raw["name"],
                    template_type=GroupTemplateType(raw["template_type"]),
                    visual_intent=GroupVisualIntent(raw["visual_intent"]),
                    tags=tuple(tags) if isinstance(tags, list) else tags,
                    source=raw.get("source", "builtin"),
                    file=raw.get("file", ""),
                )
            )

        logger.info(f"TemplateStore loaded {len(entries)} entries from {index_path}")
        return cls(entries=entries, base_dir=directory)

    @classmethod
    def from_catalog_with_local_extensions(
        cls,
        catalog_dir: Path,
        local_extensions_dir: Path | None,
    ) -> TemplateStore:
        """Load the tracked catalog, then merge in a local, untracked overlay.

        ``catalog_dir`` (the git-tracked ``catalog/templates/`` root) is loaded
        first and is authoritative. ``local_extensions_dir`` (typically the
        legacy, gitignored ``data/templates/`` overlay a developer may have
        populated locally via ``recipe_builder``'s promotion pipeline) is
        optional: when present, its entries are merged on top, so a developer
        can iterate against locally-staged recipes without promoting them
        into git first. Entries sharing a ``recipe_id`` in both directories
        prefer the local extension.

        Args:
            catalog_dir: Tracked catalog root with ``index.json``. Must exist.
            local_extensions_dir: Optional local overlay directory with its
                own ``index.json``. Silently ignored if absent, identical to
                ``catalog_dir``, or missing its own ``index.json``.

        Returns:
            Merged TemplateStore.
        """
        store = cls.from_directory(catalog_dir)
        if (
            local_extensions_dir is not None
            and local_extensions_dir != catalog_dir
            and (local_extensions_dir / "index.json").exists()
        ):
            store = store.merge(cls.from_directory(local_extensions_dir))
        return store

    def merge(self, other: TemplateStore) -> TemplateStore:
        """Return a new store combining this store's entries with ``other``'s.

        Entries in ``other`` take precedence over entries sharing a
        ``recipe_id`` in ``self``. Each entry's recipe file resolves against
        the base directory it was originally loaded from, so the merged store
        can safely combine entries sourced from different directories.
        """
        merged = TemplateStore(entries=list(self._entries_by_id.values()), base_dir=self._base_dir)
        merged._entry_dirs = dict(self._entry_dirs)
        for recipe_id, entry in other._entries_by_id.items():
            merged._entries_by_id[recipe_id] = entry
            merged._entry_dirs[recipe_id] = other._entry_dirs.get(recipe_id, other._base_dir)
        return merged

    @property
    def entries(self) -> list[TemplateStoreEntry]:
        """All metadata entries (sorted by type and name)."""
        return sorted(
            self._entries_by_id.values(),
            key=lambda e: (e.template_type.value, e.name),
        )

    def has_recipe(self, recipe_id: str) -> bool:
        return recipe_id in self._entries_by_id

    def get_entry(self, recipe_id: str) -> TemplateStoreEntry | None:
        return self._entries_by_id.get(recipe_id)

    def get_recipe(self, recipe_id: str) -> EffectRecipe | None:
        """Load and cache a full EffectRecipe by ID.

        Args:
            recipe_id: Recipe identifier.

        Returns:
            EffectRecipe if found, None if recipe_id is unknown.
        """
        if recipe_id in self._cache:
            return self._cache[recipe_id]

        entry = self._entries_by_id.get(recipe_id)
        if entry is None:
            return None

        base_dir = self._entry_dirs.get(recipe_id, self._base_dir)
        file_path = base_dir / entry.file
        if not file_path.exists():
            logger.warning(f"Recipe file not found: {file_path}")
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            recipe = EffectRecipe.model_validate(data)
            self._cache[recipe_id] = recipe
            return recipe
        except Exception:
            logger.exception(f"Failed to load recipe {recipe_id} from {file_path}")
            return None

    def list_by_type(self, template_type: GroupTemplateType) -> list[TemplateStoreEntry]:
        return [e for e in self.entries if e.template_type == template_type]

    def list_by_lane(self, lane: LaneKind) -> list[TemplateStoreEntry]:
        return [e for e in self.entries if lane in e.compatible_lanes]

    def all_recipe_ids(self) -> list[str]:
        return list(self._entries_by_id.keys())

    def preload_all(self) -> int:
        """Eagerly load all recipes into cache.

        Returns:
            Number of recipes successfully loaded.
        """
        loaded = 0
        for recipe_id in self._entries_by_id:
            if self.get_recipe(recipe_id) is not None:
                loaded += 1
        return loaded
