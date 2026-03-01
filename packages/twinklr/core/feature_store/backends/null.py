"""Null (no-op) feature store backend.

``NullFeatureStore`` satisfies the full ``FeatureStoreProviderSync`` protocol
without performing any I/O.  It is the default backend and is useful for
unit-testing pipeline stages that write to the store without needing
persistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.feature_store.models import CorpusStats, ProfileRecord

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.models.phrases import EffectPhrase
    from twinklr.core.feature_engineering.models.propensity import EffectModelAffinity
    from twinklr.core.feature_engineering.models.stacks import EffectStack
    from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord
    from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateAssignment
    from twinklr.core.feature_engineering.models.transitions import TransitionEdge
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


class NullFeatureStore:
    """No-op feature store — all writes are silently discarded, all reads return empty results.

    Satisfies ``FeatureStoreProviderSync`` at runtime (verified by ``isinstance``).
    Lifecycle methods are idempotent and never raise.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """No-op initialisation. Safe to call multiple times."""

    def close(self) -> None:
        """No-op close. Safe to call multiple times."""

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def upsert_phrases(self, phrases: tuple[EffectPhrase, ...]) -> int:
        """Discard phrases and return 0."""
        return 0

    def upsert_templates(self, templates: tuple[MinedTemplate, ...]) -> int:
        """Discard templates and return 0."""
        return 0

    def upsert_template_assignments(self, assignments: tuple[TemplateAssignment, ...]) -> int:
        """Discard template assignments and return 0."""
        return 0

    def upsert_stacks(self, stacks: tuple[EffectStack, ...]) -> int:
        """Discard stacks and return 0."""
        return 0

    def upsert_transitions(self, edges: tuple[TransitionEdge, ...]) -> int:
        """Discard transition edges and return 0."""
        return 0

    def upsert_recipes(self, recipes: tuple[EffectRecipe, ...]) -> int:
        """Discard recipes and return 0."""
        return 0

    def upsert_taxonomy(self, records: tuple[PhraseTaxonomyRecord, ...]) -> int:
        """Discard taxonomy records and return 0."""
        return 0

    def upsert_propensity(self, entries: tuple[EffectModelAffinity, ...]) -> int:
        """Discard propensity entries and return 0."""
        return 0

    def upsert_corpus_metadata(self, corpus_id: str, metadata_json: str) -> int:
        """Discard corpus metadata and return 0."""
        return 0

    # ------------------------------------------------------------------
    # Profile methods
    # ------------------------------------------------------------------

    def upsert_profile(self, profile: ProfileRecord) -> int:
        """Discard profile and return 0."""
        return 0

    def query_profiles(self, fe_status: str | None = None) -> tuple[ProfileRecord, ...]:
        """Return an empty tuple — no profiles stored."""
        return ()

    def query_profile_by_sha(self, sequence_sha256: str) -> ProfileRecord | None:
        """Return None — no profiles stored."""
        return None

    def mark_fe_complete(self, profile_id: str) -> None:
        """No-op — null backend does not track profile status."""

    def mark_fe_error(self, profile_id: str, error: str) -> None:
        """No-op — null backend does not track profile status."""

    def reset_all_fe_status(self) -> None:
        """No-op — null backend does not track profile status."""

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def query_phrases_by_target(
        self,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
    ) -> tuple[EffectPhrase, ...]:
        """Return an empty tuple — no phrases stored."""
        return ()

    def query_phrases_by_family(self, effect_family: str) -> tuple[EffectPhrase, ...]:
        """Return an empty tuple — no phrases stored."""
        return ()

    def query_templates(
        self,
        *,
        effect_family: str | None = None,
        min_support: int = 0,
        min_stability: float = 0.0,
    ) -> tuple[MinedTemplate, ...]:
        """Return an empty tuple — no templates stored."""
        return ()

    def query_stacks_by_target(
        self,
        package_id: str,
        sequence_file_id: str,
        target_name: str,
    ) -> tuple[EffectStack, ...]:
        """Return an empty tuple — no stacks stored."""
        return ()

    def query_stacks_by_signature(self, signature: str) -> tuple[EffectStack, ...]:
        """Return an empty tuple — no stacks stored."""
        return ()

    def query_recipes(
        self,
        *,
        template_type: str | None = None,
    ) -> tuple[EffectRecipe, ...]:
        """Return an empty tuple — no recipes stored."""
        return ()

    def query_transitions(
        self,
        *,
        source_template_id: str | None = None,
    ) -> tuple[TransitionEdge, ...]:
        """Return an empty tuple — no transitions stored."""
        return ()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_corpus_stats(self) -> CorpusStats:
        """Return a zeroed ``CorpusStats`` — nothing has been stored."""
        return CorpusStats()

    def get_schema_version(self) -> str:
        """Return ``"null"`` to identify this as the no-op backend."""
        return "null"

    def store_reference_data(self, data_key: str, data_json: str, version: str) -> None:
        """No-op — reference data is not persisted by the null backend."""

    def load_reference_data(self, data_key: str) -> str | None:
        """Return ``None`` — no reference data is stored by the null backend."""
        return None
