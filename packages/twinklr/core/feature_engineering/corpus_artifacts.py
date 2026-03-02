"""Corpus-level artifact orchestration for the feature-engineering pipeline.

Extracted from ``FeatureEngineeringPipeline._write_v1_tail_artifacts`` and
related methods (CQ-01) to keep the pipeline module under 500 lines after
ruff formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.artifact_writer import ArtifactWriter
from twinklr.core.feature_engineering.component_factory import ComponentFactory
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models import (
    ColorNarrativeRow,
    EffectPhrase,
    FeatureBundle,
    LayeringFeatureRow,
    PhraseTaxonomyRecord,
    PlannerChangeMode,
    QualityReport,
    SequencerAdapterBundle,
    TargetRoleAssignment,
    TemplateCatalog,
    TemplateRetrievalIndex,
    TransitionGraph,
)
from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.models.clustering import TemplateClusterCatalog
from twinklr.core.feature_engineering.models.metadata import EffectMetadataProfiles
from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.promotion import PromotionReport
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_engineering.models.stacks import EffectStack, EffectStackCatalog
from twinklr.core.feature_engineering.models.vocabulary import VocabularyExtensions
from twinklr.core.feature_engineering.promotion import PromotionPipeline
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync

_ProgressFn = Any  # Callable[[str], None] | None


def write_v1_tail_artifacts(
    *,
    output_root: Path,
    bundles: tuple[FeatureBundle, ...],
    phrases: tuple[EffectPhrase, ...],
    taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    target_roles: tuple[TargetRoleAssignment, ...],
    template_catalogs: tuple[TemplateCatalog, TemplateCatalog] | None,
    stacks: tuple[EffectStack, ...] | None = None,
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    artifact_writer: ArtifactWriter,
    components: ComponentFactory,
    store: FeatureStoreProviderSync,
    progress_fn: _ProgressFn = None,
) -> None:
    """Orchestrate writing of all V1 corpus-level artifacts.

    This is a free function extracted from
    ``FeatureEngineeringPipeline._write_v1_tail_artifacts`` to keep the
    pipeline module concise.

    Args:
        output_root: Root output directory.
        bundles: All feature bundles.
        phrases: All effect phrases.
        taxonomy_rows: All taxonomy rows.
        target_roles: All target-role assignments.
        template_catalogs: Content and orchestration catalogs (or ``None``).
        stacks: Detected effect stacks (or ``None``).
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        artifact_writer: The artifact writer instance.
        components: The lazy component factory.
        store: The feature store.
        progress_fn: Optional progress callback.
    """
    o, w, c, s = options, writer, components, store
    m: dict[str, str] = {}
    ri: TemplateRetrievalIndex | None = None
    tg: TransitionGraph | None = None
    if o.enable_transition_modeling and template_catalogs is not None:
        if progress_fn:
            progress_fn("transition modeling")
        tg = c.transition_modeler.build_graph(
            phrases=phrases, orchestration_catalog=template_catalogs[1]
        )
        m["transition_graph"] = str(w.write_transition_graph(output_root, tg))
        s.upsert_transitions(tg.edges)
    lr: tuple[LayeringFeatureRow, ...] = ()
    if o.enable_layering_features and phrases:
        if progress_fn:
            progress_fn("layering features")
        lr = c.layering.extract(phrases)
        m["layering_features"] = str(w.write_layering_features(output_root, lr))
    cr: tuple[ColorNarrativeRow, ...] = ()
    if o.enable_color_narrative and phrases:
        if progress_fn:
            progress_fn("color narrative")
        cr = c.color_narrative.extract(phrases)
        m["color_narrative"] = str(w.write_color_narrative(output_root, cr))
    # ── Color palette discovery ──────────────────────────────────────
    palette_path: Path | None = None
    if o.enable_color_discovery and phrases:
        if progress_fn:
            progress_fn("color palette discovery")
        enriched_events = [p.model_dump(mode="json") for p in phrases]
        palette_library = c.color_family_discoverer.discover(enriched_events)
        if palette_library:
            palette_path = w.write_color_palette_library(output_root, palette_library)
            m["color_palette_library"] = str(palette_path)
    cap = write_color_arc(
        output_root=output_root,
        phrases=phrases,
        color_rows=cr,
        options=o,
        writer=w,
        components=c,
        palette_library_path=palette_path,
    )
    if cap is not None:
        m["color_arc"] = str(cap)
    pp, pi = write_propensity(
        output_root=output_root, phrases=phrases, options=o, writer=w, components=c
    )
    if pp is not None:
        m["propensity_index"] = str(pp)
    if pi is not None:
        s.upsert_propensity(pi.affinities)
    # ── Effect metadata profiles ─────────────────────────────────────
    stack_catalog: EffectStackCatalog | None = None
    if stacks is not None:
        stack_catalog = _build_stack_catalog(stacks)
    if o.enable_effect_metadata and phrases:
        if progress_fn:
            progress_fn("effect metadata profiles")
        metadata_profiles = c.effect_metadata_builder.build(
            phrases=phrases,
            stacks=stack_catalog,
            propensity=pi,
        )
        m["effect_metadata"] = str(w.write_effect_metadata(output_root, metadata_profiles))
    # ── Vocabulary expansion ─────────────────────────────────────────
    if o.enable_vocabulary_expansion and stack_catalog is not None:
        if progress_fn:
            progress_fn("vocabulary expansion")
        vocab_extensions = c.vocabulary_expander.expand(stack_catalog=stack_catalog)
        m["vocabulary_extensions"] = str(
            w.write_vocabulary_extensions(output_root, vocab_extensions)
        )
    sp = write_style_fingerprint(
        output_root=output_root,
        creator_id=bundles[0].package_id if bundles else "unknown",
        phrases=phrases,
        layering_rows=lr,
        color_rows=cr,
        transition_graph=tg,
        options=o,
        writer=w,
        components=c,
    )
    if sp is not None:
        m["style_fingerprint"] = str(sp)
    qr: QualityReport | None = None
    if o.enable_quality_gates and tg is not None and template_catalogs is not None:
        if progress_fn:
            progress_fn("quality gates")
        qr = c.quality_gates.evaluate(
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
            orchestration_catalog=template_catalogs[1],
            transition_graph=tg,
        )
        m["quality_report"] = str(w.write_quality_report(output_root, qr))
    if phrases:
        m["unknown_diagnostics"] = str(
            w.write_unknown_diagnostics(
                output_root, artifact_writer.build_unknown_diagnostics(phrases)
            )
        )
    mc: MotifCatalog | None = None
    clc: TemplateClusterCatalog | None = None
    if template_catalogs is not None:
        m["content_templates"] = str(output_root / "content_templates.json")
        m["orchestration_templates"] = str(output_root / "orchestration_templates.json")
        if o.enable_template_retrieval_ranking:
            if progress_fn:
                progress_fn("template retrieval ranking")
            ri = c.template_retrieval_ranker.build_index(
                content_catalog=template_catalogs[0],
                orchestration_catalog=template_catalogs[1],
                transition_graph=tg,
            )
            m["template_retrieval_index"] = str(w.write_template_retrieval_index(output_root, ri))
        if o.enable_template_diagnostics:
            diag = c.template_diagnostics.build(
                content_catalog=template_catalogs[0],
                orchestration_catalog=template_catalogs[1],
                taxonomy_rows=taxonomy_rows,
            )
            m["template_diagnostics"] = str(w.write_template_diagnostics(output_root, diag))
        if o.enable_v2_motif_mining:
            if progress_fn:
                progress_fn("motif mining")
            mc = c.motif_miner.mine(
                phrases=phrases,
                taxonomy_rows=taxonomy_rows,
                content_catalog=template_catalogs[0],
                orchestration_catalog=template_catalogs[1],
            )
            m["motif_catalog"] = str(w.write_motif_catalog(output_root, mc))
        # ── Temporal motif mining ────────────────────────────────────
        if o.enable_v2_temporal_motif_mining:
            if progress_fn:
                progress_fn("temporal motif mining")
            temporal_catalog = c.motif_miner.mine_temporal(
                phrases=phrases,
                content_catalog=template_catalogs[0],
                orchestration_catalog=template_catalogs[1],
            )
            w.write_temporal_motif_catalog(output_root, temporal_catalog)
            m["temporal_motif_catalog"] = str(output_root / "temporal_motif_catalog.json")
        if o.enable_v2_clustering:
            if progress_fn:
                progress_fn("template clustering")
            clc = c.template_clusterer.build_clusters(
                content_catalog=template_catalogs[0],
                orchestration_catalog=template_catalogs[1],
                retrieval_index=ri,
            )
            m["cluster_candidates"] = str(w.write_cluster_catalog(output_root, clc))
            m["cluster_review_queue"] = str(w.write_cluster_review_queue(output_root, clc))
    if o.enable_recipe_promotion and template_catalogs is not None:
        if progress_fn:
            progress_fn("recipe promotion")
        rp = run_recipe_promotion(
            output_root=output_root,
            template_catalogs=template_catalogs,
            motif_catalog=mc,
            cluster_catalog=clc,
            propensity_index=pi,
            options=o,
            writer=w,
            store=s,
        )
        if rp is not None:
            m["recipe_catalog"] = str(rp)
    if o.enable_v2_learned_taxonomy and phrases and taxonomy_rows:
        if progress_fn:
            progress_fn("learned taxonomy")
        mdl, rpt = c.learned_taxonomy_trainer.train(phrases=phrases, taxonomy_rows=taxonomy_rows)
        m["taxonomy_model_bundle"] = str(w.write_learned_taxonomy_model(output_root, mdl))
        m["taxonomy_eval_report"] = str(w.write_learned_taxonomy_eval(output_root, rpt))
    if o.enable_v2_ann_retrieval and ri is not None:
        if progress_fn:
            progress_fn("ANN retrieval index")
        ai = c.ann_retrieval_indexer.build_index(ri)
        m["retrieval_ann_index"] = str(w.write_ann_retrieval_index(output_root, ai))
        er = c.ann_retrieval_indexer.evaluate(index=ai, retrieval_index=ri)
        m["retrieval_eval_report"] = str(w.write_ann_retrieval_eval(output_root, er))
    if o.enable_v2_adapter_contracts:
        if progress_fn:
            progress_fn("adapter contracts")
        pls, acc = build_adapter_payloads(
            bundles=bundles,
            retrieval_index=ri,
            transition_graph=tg,
            target_roles=target_roles,
            components=c,
        )
        m["planner_adapter_payloads"] = str(w.write_planner_adapter_payloads(output_root, pls))
        m["planner_adapter_acceptance"] = str(w.write_planner_adapter_acceptance(output_root, acc))
    if qr is not None:
        m["quality_passed"] = str(qr.passed)
    w.write_feature_store_manifest(output_root, m)


def build_adapter_payloads(
    *,
    bundles: tuple[FeatureBundle, ...],
    retrieval_index: TemplateRetrievalIndex | None,
    transition_graph: TransitionGraph | None,
    target_roles: tuple[TargetRoleAssignment, ...],
    components: ComponentFactory,
) -> tuple[tuple[SequencerAdapterBundle, ...], dict[str, object]]:
    """Build sequencer adapter payloads for all bundles.

    Args:
        bundles: All feature bundles.
        retrieval_index: Template retrieval index (or ``None``).
        transition_graph: Transition graph (or ``None``).
        target_roles: All target-role assignments.
        components: The lazy component factory.

    Returns:
        Tuple of adapter bundles and acceptance report dict.
    """
    recs = retrieval_index.recommendations if retrieval_index is not None else ()
    rbs: dict[str, list[TargetRoleAssignment]] = {}
    for row in target_roles:
        rbs.setdefault(row.sequence_file_id, []).append(row)
    pls: list[SequencerAdapterBundle] = []
    viol: list[str] = []
    kw: dict[str, Any] = {"recommendations": recs, "transition_graph": transition_graph}
    for b in sorted(bundles, key=lambda x: (x.package_id, x.sequence_file_id)):
        kw["bundle"], kw["role_assignments"] = b, tuple(rbs.get(b.sequence_file_id, []))
        macro = components.macro_adapter_builder.build(**kw)
        group = components.group_adapter_builder.build(**kw)
        bk = f"{b.package_id}/{b.sequence_file_id}"
        if macro.planner_change_mode is not PlannerChangeMode.CONTRACT_ONLY:
            viol.append(f"{bk}:macro")
        if group.planner_change_mode is not PlannerChangeMode.CONTRACT_ONLY:
            viol.append(f"{bk}:group")
        pls.append(
            SequencerAdapterBundle(
                schema_version=macro.schema_version,
                adapter_version=macro.adapter_version,
                macro=macro,
                group=group,
            )
        )
    n = len(pls)
    return tuple(pls), {
        "schema_version": "v2.4.0",
        "adapter_version": "sequencer_adapter_v1",
        "sequence_count": n,
        "macro_payload_count": n,
        "group_payload_count": n,
        "planner_change_mode_enforced": not viol,
        "contract_only_violations": viol,
        "planner_runtime_changes_applied": False,
    }


def run_recipe_promotion(
    *,
    output_root: Path,
    template_catalogs: tuple[TemplateCatalog, TemplateCatalog],
    motif_catalog: MotifCatalog | None,
    cluster_catalog: TemplateClusterCatalog | None,
    propensity_index: PropensityIndex | None = None,
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    store: FeatureStoreProviderSync,
) -> Path | None:
    """Run recipe promotion and write the catalog.

    Args:
        output_root: Root output directory.
        template_catalogs: Content and orchestration catalogs.
        motif_catalog: Motif catalog (or ``None``).
        cluster_catalog: Cluster catalog (or ``None``).
        propensity_index: Propensity index (or ``None``).
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        store: The feature store.

    Returns:
        Path to written recipe catalog, or ``None`` if no recipes promoted.
    """
    cands = list(template_catalogs[0].templates) + list(template_catalogs[1].templates)
    if not cands:
        return None
    clusters = (
        [
            {
                "cluster_id": c.cluster_id,
                "member_ids": list(c.member_template_ids),
                "keep_id": c.member_template_ids[0] if c.member_template_ids else None,
            }
            for c in cluster_catalog.clusters
        ]
        if cluster_catalog is not None
        else None
    )
    o = options
    res = PromotionPipeline(param_profiles=o.recipe_promotion_param_profiles).run(
        cands,
        min_support=o.recipe_promotion_min_support,
        min_stability=o.recipe_promotion_min_stability,
        clusters=clusters,
        motif_catalog=motif_catalog,
        propensity_index=propensity_index,
        use_stack_synthesis=o.enable_stack_detection,
        adaptive_stability=o.recipe_promotion_adaptive_stability,
        max_per_family=o.recipe_promotion_max_per_family,
    )
    # Write promotion report regardless of whether recipes were promoted
    report = PromotionReport(
        **{k: v for k, v in res.report.items() if k in PromotionReport.model_fields}
    )
    writer.write_promotion_report(output_root, report)
    if not res.promoted_recipes:
        return None
    store.upsert_recipes(tuple(res.promoted_recipes))
    return writer.write_recipe_catalog(output_root, res.promoted_recipes)


def write_template_catalogs(
    *,
    output_root: Path,
    phrases: tuple[EffectPhrase, ...],
    taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    target_roles: tuple[TargetRoleAssignment, ...],
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    components: ComponentFactory,
    store: FeatureStoreProviderSync,
    progress_fn: _ProgressFn = None,
) -> tuple[tuple[TemplateCatalog, TemplateCatalog], tuple[EffectStack, ...] | None] | None:
    """Mine and write content/orchestration template catalogs.

    Args:
        output_root: Root output directory.
        phrases: All effect phrases.
        taxonomy_rows: All taxonomy rows.
        target_roles: All target-role assignments.
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        components: The lazy component factory.
        store: The feature store.
        progress_fn: Optional progress callback.

    Returns:
        Tuple of ``((content_catalog, orchestration_catalog), stacks)``
        or ``None`` when template mining is disabled.
    """
    if not options.enable_template_mining or not phrases:
        return None
    stacks = None
    if options.enable_stack_detection:
        if progress_fn:
            progress_fn("stack detection")
        stacks = components.stack_detector.detect(phrases=phrases)
        writer.write_stack_catalog(output_root, stacks)
        if progress_fn:
            progress_fn("template mining (stack-aware)")
        cc, oc = components.template_miner.mine_stacks(
            stacks=stacks, taxonomy_rows=taxonomy_rows, target_roles=target_roles
        )
    else:
        if progress_fn:
            progress_fn("template mining")
        cc, oc = components.template_miner.mine(
            phrases=phrases, taxonomy_rows=taxonomy_rows, target_roles=target_roles
        )
    writer.write_content_templates(output_root, cc)
    writer.write_orchestration_templates(output_root, oc)
    store.upsert_templates(cc.templates + oc.templates)
    store.upsert_template_assignments(cc.assignments + oc.assignments)
    if stacks is not None:
        store.upsert_stacks(stacks)
    return (cc, oc), stacks


def write_color_arc(
    *,
    output_root: Path,
    phrases: tuple[EffectPhrase, ...],
    color_rows: tuple[ColorNarrativeRow, ...],
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    components: ComponentFactory,
    palette_library_path: Path | None = None,
) -> Path | None:
    """Write colour-arc artifact.

    Args:
        output_root: Root output directory.
        phrases: All effect phrases.
        color_rows: Colour narrative rows.
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        components: The lazy component factory.
        palette_library_path: Path to a discovered palette library file.

    Returns:
        Path to written file, or ``None`` if disabled or no data.
    """
    if not options.enable_color_arc or not color_rows:
        return None
    extractor = (
        ColorArcExtractor(palette_library_path=palette_library_path)
        if palette_library_path is not None
        else components.color_arc
    )
    p = output_root / "color_arc.json"
    writer._write_json(
        p,
        extractor.extract(phrases=phrases, color_narrative=color_rows).model_dump(mode="json"),
    )
    return p


def write_propensity(
    *,
    output_root: Path,
    phrases: tuple[EffectPhrase, ...],
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    components: ComponentFactory,
) -> tuple[Path | None, PropensityIndex | None]:
    """Write propensity index artifact.

    Args:
        output_root: Root output directory.
        phrases: All effect phrases.
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        components: The lazy component factory.

    Returns:
        Tuple of (path, index) or (None, None) if disabled.
    """
    if not options.enable_propensity or not phrases:
        return None, None
    ix = components.propensity_miner.mine(phrases=phrases)
    p = output_root / "propensity_index.json"
    writer._write_json(p, ix.model_dump(mode="json"))
    return p, ix


def write_style_fingerprint(
    *,
    output_root: Path,
    creator_id: str,
    phrases: tuple[EffectPhrase, ...],
    layering_rows: tuple[LayeringFeatureRow, ...],
    color_rows: tuple[ColorNarrativeRow, ...],
    transition_graph: TransitionGraph | None,
    options: FeatureEngineeringPipelineOptions,
    writer: FeatureEngineeringWriter,
    components: ComponentFactory,
) -> Path | None:
    """Write style-fingerprint artifact.

    Args:
        output_root: Root output directory.
        creator_id: Creator identifier.
        phrases: All effect phrases.
        layering_rows: Layering feature rows.
        color_rows: Colour narrative rows.
        transition_graph: Transition graph (or ``None``).
        options: Pipeline configuration options.
        writer: The feature-engineering writer instance.
        components: The lazy component factory.

    Returns:
        Path to written file, or ``None`` if disabled or no data.
    """
    if not options.enable_style_fingerprint or not phrases:
        return None
    p = output_root / "style_fingerprint.json"
    writer._write_json(
        p,
        components.style_fingerprint.extract(
            creator_id=creator_id,
            phrases=phrases,
            layering_rows=layering_rows,
            color_rows=color_rows,
            transition_graph=transition_graph,
        ).model_dump(mode="json"),
    )
    return p


def _build_stack_catalog(stacks: tuple[EffectStack, ...]) -> EffectStackCatalog:
    """Build an ``EffectStackCatalog`` from a raw stacks tuple.

    Args:
        stacks: Detected effect stacks.

    Returns:
        A fully populated ``EffectStackCatalog``.
    """
    single_count = sum(1 for s in stacks if s.layer_count == 1)
    multi_count = sum(1 for s in stacks if s.layer_count > 1)
    max_layers = max((s.layer_count for s in stacks), default=0)
    return EffectStackCatalog(
        total_phrase_count=sum(s.layer_count for s in stacks),
        total_stack_count=len(stacks),
        single_layer_count=single_count,
        multi_layer_count=multi_count,
        max_layer_count=max_layers,
        stacks=stacks,
    )


__all__ = [
    "build_adapter_payloads",
    "run_recipe_promotion",
    "write_color_arc",
    "write_propensity",
    "write_style_fingerprint",
    "write_template_catalogs",
    "write_v1_tail_artifacts",
]
