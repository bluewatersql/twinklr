"""SQLite feature store backend.

Persists all feature engineering artifacts to a local SQLite database.
Satisfies the ``FeatureStoreProviderSync`` protocol.

Usage::

    from twinklr.core.feature_store.backends.sqlite import SQLiteFeatureStore
    from twinklr.core.feature_store.models import FeatureStoreConfig
    from pathlib import Path

    cfg = FeatureStoreConfig(backend="sqlite", db_path=Path("my.db"))
    store = SQLiteFeatureStore(cfg)
    store.initialize()
    try:
        store.upsert_phrases(phrases)
    finally:
        store.close()
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.propensity import EffectModelAffinity
from twinklr.core.feature_engineering.models.stacks import EffectStack
from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord
from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateAssignment
from twinklr.core.feature_engineering.models.transitions import TransitionEdge
from twinklr.core.feature_store.bootstrap.loader import ReferenceDataLoader
from twinklr.core.feature_store.bootstrap.schema import SchemaBootstrapper
from twinklr.core.feature_store.models import (
    CorpusStats,
    FeatureStoreConfig,
    FeatureStoreSchemaError,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


class SQLiteFeatureStore:
    """SQLite-backed feature store.

    Implements the full ``FeatureStoreProviderSync`` contract using a local
    SQLite database file.  Schema is managed by ``SchemaBootstrapper``; the
    backend itself contains no hardcoded table DDL.

    Args:
        config: Feature store configuration.
    """

    def __init__(self, config: FeatureStoreConfig) -> None:
        self._config = config
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Open the SQLite connection, apply schema bootstrap if configured.

        Raises:
            FeatureStoreSchemaError: If the stored schema version does not
                match the configured ``schema_version``.
        """
        db_path: Path = self._config.db_path  # type: ignore[assignment]
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys=ON")
        if self._config.enable_wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        self._conn = conn

        if self._config.auto_bootstrap:
            SchemaBootstrapper(conn, self._config.schema_dir).bootstrap(self._config.schema_version)

        if self._config.reference_data_dir is not None:
            ReferenceDataLoader(conn).load_directory(self._config.reference_data_dir)

        # Version integrity check.
        stored = SchemaBootstrapper(conn, self._config.schema_dir).get_version()
        if stored != self._config.schema_version:
            raise FeatureStoreSchemaError(
                f"Schema version mismatch: stored={stored!r}, "
                f"expected={self._config.schema_version!r}. "
                "Run a migration or recreate the database."
            )

    def close(self) -> None:
        """Close the SQLite connection. Safe to call multiple times."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def upsert_phrases(self, phrases: tuple[EffectPhrase, ...]) -> int:
        """Persist effect phrases, inserting or updating by primary key.

        Args:
            phrases: Tuple of ``EffectPhrase`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not phrases:
            return 0
        rows = [
            (
                p.phrase_id,
                p.package_id,
                p.sequence_file_id,
                p.effect_family,
                p.target_name,
                json.dumps(p.model_dump(mode="json")),
            )
            for p in phrases
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO phrases "
                "(phrase_id, package_id, sequence_file_id, effect_family, target_name, data_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(phrases)

    def upsert_templates(self, templates: tuple[MinedTemplate, ...]) -> int:
        """Persist mined templates, inserting or updating by ``template_id``.

        Args:
            templates: Tuple of ``MinedTemplate`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not templates:
            return 0
        rows = [
            (
                t.template_id,
                t.template_kind.value,
                t.effect_family,
                t.support_count,
                t.cross_pack_stability,
                json.dumps(t.model_dump(mode="json")),
            )
            for t in templates
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO templates "
                "(template_id, template_kind, effect_family, support_count, "
                "cross_pack_stability, data_json) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(templates)

    def upsert_template_assignments(self, assignments: tuple[TemplateAssignment, ...]) -> int:
        """Persist per-phrase template assignments.

        Args:
            assignments: Tuple of ``TemplateAssignment`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not assignments:
            return 0
        rows = [
            (
                a.package_id,
                a.sequence_file_id,
                a.phrase_id,
                a.template_id,
                json.dumps(a.model_dump(mode="json")),
            )
            for a in assignments
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO template_assignments "
                "(package_id, sequence_file_id, phrase_id, template_id, data_json) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
        return len(assignments)

    def upsert_stacks(self, stacks: tuple[EffectStack, ...]) -> int:
        """Persist effect stacks.

        Args:
            stacks: Tuple of ``EffectStack`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not stacks:
            return 0
        rows = [
            (
                s.stack_id,
                s.package_id,
                s.sequence_file_id,
                s.target_name,
                s.stack_signature,
                json.dumps(s.model_dump(mode="json")),
            )
            for s in stacks
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO stacks "
                "(stack_id, package_id, sequence_file_id, target_name, stack_signature, data_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(stacks)

    def upsert_transitions(self, edges: tuple[TransitionEdge, ...]) -> int:
        """Persist transition graph edges.

        Args:
            edges: Tuple of ``TransitionEdge`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not edges:
            return 0
        rows = [
            (
                e.source_template_id,
                e.target_template_id,
                json.dumps(e.model_dump(mode="json")),
            )
            for e in edges
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO transitions "
                "(source_template_id, target_template_id, data_json) VALUES (?, ?, ?)",
                rows,
            )
        return len(edges)

    def upsert_recipes(self, recipes: tuple[EffectRecipe, ...]) -> int:
        """Persist effect recipes.

        Args:
            recipes: Tuple of ``EffectRecipe`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not recipes:
            return 0
        rows = [
            (
                r.recipe_id,
                r.template_type.value,
                r.visual_intent.value,
                json.dumps(r.model_dump(mode="json")),
            )
            for r in recipes
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO recipes "
                "(recipe_id, template_type, visual_intent, data_json) VALUES (?, ?, ?, ?)",
                rows,
            )
        return len(recipes)

    def upsert_taxonomy(self, records: tuple[PhraseTaxonomyRecord, ...]) -> int:
        """Persist phrase taxonomy records.

        Args:
            records: Tuple of ``PhraseTaxonomyRecord`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not records:
            return 0
        rows = [
            (
                r.phrase_id,
                r.package_id,
                r.sequence_file_id,
                json.dumps(r.model_dump(mode="json")),
            )
            for r in records
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO taxonomy "
                "(phrase_id, package_id, sequence_file_id, data_json) VALUES (?, ?, ?, ?)",
                rows,
            )
        return len(records)

    def upsert_propensity(self, entries: tuple[EffectModelAffinity, ...]) -> int:
        """Persist effect-model affinity (propensity) entries.

        Args:
            entries: Tuple of ``EffectModelAffinity`` records to upsert.

        Returns:
            Number of rows processed.
        """
        if not entries:
            return 0
        rows = [
            (
                e.effect_family,
                e.model_type,
                json.dumps(e.model_dump(mode="json")),
            )
            for e in entries
        ]
        with self._conn:  # type: ignore[union-attr]
            self._conn.executemany(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO propensity "
                "(effect_family, model_type, data_json) VALUES (?, ?, ?)",
                rows,
            )
        return len(entries)

    def upsert_corpus_metadata(self, corpus_id: str, metadata_json: str) -> int:
        """Persist corpus-level metadata as a JSON blob.

        Args:
            corpus_id: Unique identifier for the corpus run.
            metadata_json: Serialised JSON metadata string.

        Returns:
            Number of rows inserted or updated (always 1).
        """
        with self._conn:  # type: ignore[union-attr]
            self._conn.execute(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO corpus_metadata (corpus_id, metadata_json) VALUES (?, ?)",
                (corpus_id, metadata_json),
            )
        return 1

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def query_phrases_by_target(
        self,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
    ) -> tuple[EffectPhrase, ...]:
        """Return all phrases for a specific target in a sequence.

        Args:
            package_id: Package identifier.
            sequence_file_id: Sequence file identifier.
            target_name: Display model target name.

        Returns:
            Tuple of matching ``EffectPhrase`` records.
        """
        rows = self._conn.execute(  # type: ignore[union-attr]
            "SELECT data_json FROM phrases "
            "WHERE package_id=? AND sequence_file_id=? AND target_name=?",
            (package_id, sequence_file_id, target_name),
        ).fetchall()
        return tuple(EffectPhrase.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_phrases_by_family(self, effect_family: str) -> tuple[EffectPhrase, ...]:
        """Return all phrases belonging to a given effect family.

        Args:
            effect_family: Effect family slug (e.g. ``"color_wash"``).

        Returns:
            Tuple of matching ``EffectPhrase`` records.
        """
        rows = self._conn.execute(  # type: ignore[union-attr]
            "SELECT data_json FROM phrases WHERE effect_family=?",
            (effect_family,),
        ).fetchall()
        return tuple(EffectPhrase.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_templates(
        self,
        *,
        effect_family: str | None = None,
        min_support: int = 0,
        min_stability: float = 0.0,
    ) -> tuple[MinedTemplate, ...]:
        """Return templates matching optional filter criteria.

        Args:
            effect_family: Restrict to a specific effect family slug.
            min_support: Minimum ``support_count`` threshold.
            min_stability: Minimum ``cross_pack_stability`` threshold.

        Returns:
            Tuple of matching ``MinedTemplate`` records.
        """
        clauses = ["support_count >= ?", "cross_pack_stability >= ?"]
        params: list[Any] = [min_support, min_stability]

        if effect_family is not None:
            clauses.append("effect_family = ?")
            params.append(effect_family)

        sql = f"SELECT data_json FROM templates WHERE {' AND '.join(clauses)}"
        rows = self._conn.execute(sql, params).fetchall()  # type: ignore[union-attr]
        return tuple(MinedTemplate.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_stacks_by_target(
        self,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
    ) -> tuple[EffectStack, ...]:
        """Return all stacks for a specific target in a sequence.

        Args:
            package_id: Package identifier.
            sequence_file_id: Sequence file identifier.
            target_name: Display model target name.

        Returns:
            Tuple of matching ``EffectStack`` records.
        """
        rows = self._conn.execute(  # type: ignore[union-attr]
            "SELECT data_json FROM stacks "
            "WHERE package_id=? AND sequence_file_id=? AND target_name=?",
            (package_id, sequence_file_id, target_name),
        ).fetchall()
        return tuple(EffectStack.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_stacks_by_signature(self, signature: str) -> tuple[EffectStack, ...]:
        """Return all stacks matching a given stack signature.

        Args:
            signature: Canonical stack signature string.

        Returns:
            Tuple of matching ``EffectStack`` records.
        """
        rows = self._conn.execute(  # type: ignore[union-attr]
            "SELECT data_json FROM stacks WHERE stack_signature=?",
            (signature,),
        ).fetchall()
        return tuple(EffectStack.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_recipes(
        self,
        *,
        template_type: str | None = None,
    ) -> tuple[EffectRecipe, ...]:
        """Return recipes matching optional filter criteria.

        Args:
            template_type: Restrict to a specific ``GroupTemplateType`` value.

        Returns:
            Tuple of matching ``EffectRecipe`` records.
        """
        if template_type is not None:
            rows = self._conn.execute(  # type: ignore[union-attr]
                "SELECT data_json FROM recipes WHERE template_type=?",
                (template_type,),
            ).fetchall()
        else:
            rows = self._conn.execute(  # type: ignore[union-attr]
                "SELECT data_json FROM recipes"
            ).fetchall()
        return tuple(EffectRecipe.model_validate(json.loads(r["data_json"])) for r in rows)

    def query_transitions(
        self,
        *,
        source_template_id: str | None = None,
    ) -> tuple[TransitionEdge, ...]:
        """Return transition edges matching optional filter criteria.

        Args:
            source_template_id: Restrict to edges originating from this template.

        Returns:
            Tuple of matching ``TransitionEdge`` records.
        """
        if source_template_id is not None:
            rows = self._conn.execute(  # type: ignore[union-attr]
                "SELECT data_json FROM transitions WHERE source_template_id=?",
                (source_template_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(  # type: ignore[union-attr]
                "SELECT data_json FROM transitions"
            ).fetchall()
        return tuple(TransitionEdge.model_validate(json.loads(r["data_json"])) for r in rows)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_corpus_stats(self) -> CorpusStats:
        """Return aggregate row counts for all entity types.

        Returns:
            A ``CorpusStats`` instance with counts from each table.
        """
        conn = self._conn  # type: ignore[union-attr]

        def _count(table: str) -> int:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return int(row[0])

        return CorpusStats(
            phrase_count=_count("phrases"),
            template_count=_count("templates"),
            stack_count=_count("stacks"),
            transition_count=_count("transitions"),
            recipe_count=_count("recipes"),
            taxonomy_count=_count("taxonomy"),
            propensity_count=_count("propensity"),
        )

    def get_schema_version(self) -> str:
        """Return the stored schema version string.

        Returns:
            Version string from ``schema_info``, or ``"unknown"`` if not set.
        """
        row = self._conn.execute(  # type: ignore[union-attr]
            "SELECT value FROM schema_info WHERE key='version'"
        ).fetchone()
        if row is None:
            return "unknown"
        return str(row[0])

    def store_reference_data(self, data_key: str, data_json: str, version: str) -> None:
        """Persist versioned reference data as a JSON blob.

        Args:
            data_key: Logical key identifying the reference dataset.
            data_json: Serialised JSON string.
            version: Version label for this snapshot.
        """
        with self._conn:  # type: ignore[union-attr]
            self._conn.execute(  # type: ignore[union-attr]
                "INSERT OR REPLACE INTO reference_data (data_key, data_json, version) "
                "VALUES (?, ?, ?)",
                (data_key, data_json, version),
            )

    def load_reference_data(self, data_key: str) -> str | None:
        """Load the most recent reference data for the given key.

        Args:
            data_key: Logical key identifying the reference dataset.

        Returns:
            Serialised JSON string, or ``None`` if the key is not found.
        """
        row = self._conn.execute(  # type: ignore[union-attr]
            "SELECT data_json FROM reference_data WHERE data_key=?",
            (data_key,),
        ).fetchone()
        if row is None:
            return None
        return str(row["data_json"])
