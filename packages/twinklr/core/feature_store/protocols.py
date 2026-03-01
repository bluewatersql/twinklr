"""Feature store provider protocol definitions.

All backend implementations must satisfy ``FeatureStoreProviderSync`` to be
usable by the pipeline.  The protocol is ``@runtime_checkable`` so callers
can guard with ``isinstance(store, FeatureStoreProviderSync)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.models.phrases import EffectPhrase
    from twinklr.core.feature_engineering.models.propensity import EffectModelAffinity
    from twinklr.core.feature_engineering.models.stacks import EffectStack
    from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord
    from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateAssignment
    from twinklr.core.feature_engineering.models.transitions import TransitionEdge
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

from twinklr.core.feature_store.models import CorpusStats, ProfileRecord


@runtime_checkable
class FeatureStoreProviderSync(Protocol):
    """Synchronous feature store provider contract.

    All methods are synchronous (blocking I/O).  Backends that need async
    support should run operations in a thread executor and wrap this interface.

    Lifecycle::

        store.initialize()
        try:
            store.upsert_phrases(phrases)
            results = store.query_templates()
        finally:
            store.close()
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Open the backend connection and apply any pending schema migrations."""
        ...

    def close(self) -> None:
        """Release backend resources. Safe to call multiple times (idempotent)."""
        ...

    # ------------------------------------------------------------------
    # Write methods — return row count affected
    # ------------------------------------------------------------------

    def upsert_phrases(self, phrases: tuple[EffectPhrase, ...]) -> int:
        """Persist effect phrases, inserting or updating by primary key.

        Args:
            phrases: Tuple of ``EffectPhrase`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_templates(self, templates: tuple[MinedTemplate, ...]) -> int:
        """Persist mined templates, inserting or updating by ``template_id``.

        Args:
            templates: Tuple of ``MinedTemplate`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_template_assignments(self, assignments: tuple[TemplateAssignment, ...]) -> int:
        """Persist per-phrase template assignments.

        Args:
            assignments: Tuple of ``TemplateAssignment`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_stacks(self, stacks: tuple[EffectStack, ...]) -> int:
        """Persist effect stacks.

        Args:
            stacks: Tuple of ``EffectStack`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_transitions(self, edges: tuple[TransitionEdge, ...]) -> int:
        """Persist transition graph edges.

        Args:
            edges: Tuple of ``TransitionEdge`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_recipes(self, recipes: tuple[EffectRecipe, ...]) -> int:
        """Persist effect recipes.

        Args:
            recipes: Tuple of ``EffectRecipe`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_taxonomy(self, records: tuple[PhraseTaxonomyRecord, ...]) -> int:
        """Persist phrase taxonomy records.

        Args:
            records: Tuple of ``PhraseTaxonomyRecord`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_propensity(self, entries: tuple[EffectModelAffinity, ...]) -> int:
        """Persist effect-model affinity (propensity) entries.

        Args:
            entries: Tuple of ``EffectModelAffinity`` records to upsert.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    def upsert_corpus_metadata(self, corpus_id: str, metadata_json: str) -> int:
        """Persist corpus-level metadata as a JSON blob.

        Args:
            corpus_id: Unique identifier for the corpus run.
            metadata_json: Serialised JSON metadata string.

        Returns:
            Number of rows inserted or updated.
        """
        ...

    # ------------------------------------------------------------------
    # Profile methods
    # ------------------------------------------------------------------

    def upsert_profile(self, profile: ProfileRecord) -> int:
        """Persist a profile record, inserting or updating by profile_id.

        Args:
            profile: ProfileRecord to upsert. Uses INSERT OR REPLACE semantics.

        Returns:
            Number of rows inserted or updated (always 1 on success).
        """
        ...

    def query_profiles(self, fe_status: str | None = None) -> tuple[ProfileRecord, ...]:
        """Return profiles matching optional fe_status filter.

        Args:
            fe_status: Restrict to profiles with this status ('pending', 'complete',
                'error'). If None, return all profiles.

        Returns:
            Tuple of matching ProfileRecord instances.
        """
        ...

    def query_profile_by_sha(self, sequence_sha256: str) -> ProfileRecord | None:
        """Return the profile with matching sequence_sha256, or None if not found.

        Args:
            sequence_sha256: SHA256 hash of the sequence content.

        Returns:
            ProfileRecord if found, None otherwise.
        """
        ...

    def mark_fe_complete(self, profile_id: str) -> None:
        """Mark a profile as feature-engineering complete.

        Sets fe_status='complete' and fe_completed_at=datetime('now').

        Args:
            profile_id: Primary key of the profile to update.
        """
        ...

    def mark_fe_error(self, profile_id: str, error: str) -> None:
        """Mark a profile as feature-engineering error.

        Sets fe_status='error' and fe_error to the provided message.

        Args:
            profile_id: Primary key of the profile to update.
            error: Error message to store.
        """
        ...

    def reset_all_fe_status(self) -> None:
        """Reset all profiles to fe_status='pending' for force reprocessing.

        Clears fe_error and fe_completed_at on all profiles.
        """
        ...

    # ------------------------------------------------------------------
    # Read methods — return immutable tuples
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
            target_name: Display model target name (e.g. ``"MegaTree"``).

        Returns:
            Tuple of matching ``EffectPhrase`` records.
        """
        ...

    def query_phrases_by_family(self, effect_family: str) -> tuple[EffectPhrase, ...]:
        """Return all phrases belonging to a given effect family.

        Args:
            effect_family: Effect family slug (e.g. ``"color_wash"``).

        Returns:
            Tuple of matching ``EffectPhrase`` records.
        """
        ...

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
        ...

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
        ...

    def query_stacks_by_signature(self, signature: str) -> tuple[EffectStack, ...]:
        """Return all stacks matching a given stack signature.

        Args:
            signature: Canonical stack signature string.

        Returns:
            Tuple of matching ``EffectStack`` records.
        """
        ...

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
        ...

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
        ...

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_corpus_stats(self) -> CorpusStats:
        """Return aggregate row counts for all entity types in the store.

        Returns:
            A ``CorpusStats`` instance (all zeros on an empty store).
        """
        ...

    def get_schema_version(self) -> str:
        """Return the schema version string for this backend.

        Returns:
            A semver string such as ``"1.0.0"``, or ``"null"`` for the no-op backend.
        """
        ...

    def store_reference_data(self, data_key: str, data_json: str, version: str) -> None:
        """Persist versioned reference data as a JSON blob.

        Args:
            data_key: Logical key identifying the reference dataset.
            data_json: Serialised JSON string.
            version: Version label for this snapshot.
        """
        ...

    def load_reference_data(self, data_key: str) -> str | None:
        """Load the most recent reference data for the given key.

        Args:
            data_key: Logical key identifying the reference dataset.

        Returns:
            Serialised JSON string, or ``None`` if the key is not found.
        """
        ...
