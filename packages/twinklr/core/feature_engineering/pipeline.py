"""V1.0 feature-engineering orchestration facade."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering import corpus_artifacts as _ca
from twinklr.core.feature_engineering.artifact_writer import ArtifactWriter
from twinklr.core.feature_engineering.audio_discovery import (
    AudioAnalyzerLike,
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.component_factory import ComponentFactory
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.constants import FEATURE_BUNDLE_SCHEMA_VERSION
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    ColorNarrativeRow,
    EffectPhrase,
    FeatureBundle,
    LayeringFeatureRow,
    MusicLibraryIndex,
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
    TemplateCatalog,
    TransitionGraph,
)
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_store.models import ProfileRecord
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync

__all__ = ["FeatureEngineeringPipeline", "FeatureEngineeringPipelineOptions"]
_ReturnT = tuple[
    list[FeatureBundle], list[EffectPhrase], list[PhraseTaxonomyRecord], list[TargetRoleAssignment]
]


@dataclass(frozen=True)
class _ProfileOutputs:
    bundle: FeatureBundle
    phrases: tuple[EffectPhrase, ...]
    taxonomy_rows: tuple[PhraseTaxonomyRecord, ...]
    target_roles: tuple[TargetRoleAssignment, ...]


class FeatureEngineeringPipeline:
    """Execute V1.0 contracts and audio discovery/analysis."""

    def __init__(
        self,
        *,
        options: FeatureEngineeringPipelineOptions | None = None,
        analyzer: AudioAnalyzerLike | None = None,
        writer: FeatureEngineeringWriter | None = None,
        music_library_index: MusicLibraryIndex | None = None,
    ) -> None:
        self._options = options or FeatureEngineeringPipelineOptions()
        from twinklr.core.feature_store.backends.null import NullFeatureStore
        from twinklr.core.feature_store.factory import create_feature_store

        if self._options.feature_store_config is not None:
            self._store: FeatureStoreProviderSync = create_feature_store(
                self._options.feature_store_config
            )
        else:
            self._store = NullFeatureStore()
        self._discovery = AudioDiscoveryService(
            AudioDiscoveryOptions(
                confidence_threshold=self._options.confidence_threshold,
                extracted_search_roots=self._options.extracted_search_roots,
                music_repo_roots=self._options.music_repo_roots,
            ),
            music_library_index=music_library_index,
        )
        self._analyzer = analyzer
        iw = writer or FeatureEngineeringWriter()
        self._writer = iw
        self._artifact_writer = ArtifactWriter(writer=iw)
        self._components = ComponentFactory(self._options)
        self._store_lock = threading.Lock()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object at {path}")
        return data

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                val = json.loads(line)
                if not isinstance(val, dict):
                    raise ValueError(f"Expected JSON object line in {path}")
                rows.append(val)
        return rows

    def run_profile(self, profile_dir: Path, output_dir: Path) -> FeatureBundle:
        self._store.initialize()
        try:
            return self._run_profile_internal(profile_dir, output_dir).bundle
        finally:
            self._store.close()

    def _finalize_corpus(
        self,
        output_root: Path,
        corpus_id: str,
        bundles: list[FeatureBundle],
        phrases: list[EffectPhrase],
        taxonomy: list[PhraseTaxonomyRecord],
        roles: list[TargetRoleAssignment],
        progress_fn: Callable[[str], None] | None = None,
    ) -> None:
        ph, tx, ro = tuple(phrases), tuple(taxonomy), tuple(roles)
        tc = self._write_template_catalogs(
            output_root=output_root,
            phrases=ph,
            taxonomy_rows=tx,
            target_roles=ro,
            progress_fn=progress_fn,
        )
        _ca.write_v1_tail_artifacts(
            output_root=output_root,
            bundles=tuple(bundles),
            phrases=ph,
            taxonomy_rows=tx,
            target_roles=ro,
            template_catalogs=tc,
            options=self._options,
            writer=self._writer,
            artifact_writer=self._artifact_writer,
            components=self._components,
            store=self._store,
            progress_fn=progress_fn,
        )
        self._store.upsert_corpus_metadata(
            corpus_id, json.dumps({"sequence_count": len(bundles), "output_root": str(output_root)})
        )

    def run(
        self, output_root: Path, *, force: bool = False, corpus_id: str | None = None
    ) -> list[FeatureBundle]:
        """Store-driven incremental FE run."""
        self._store.initialize()
        try:
            if force:
                self._store.reset_all_fe_status()
            all_b = self._load_existing_bundles(
                self._store.query_profiles(fe_status="complete"), output_root
            )
            results: list[_ProfileOutputs] = []
            for prof in self._store.query_profiles(fe_status="pending"):
                try:
                    results.append(
                        self._run_profile_internal(
                            Path(prof.profile_path),
                            output_root / prof.package_id / prof.sequence_file_id,
                        )
                    )
                except Exception as exc:
                    self._store.mark_fe_error(prof.profile_id, str(exc))
                    if self._options.fail_fast:
                        raise
                    continue
                self._store.mark_fe_complete(prof.profile_id)
            nb, np, nt, nr = self._collect(results)
            all_b.extend(nb)
            if nb:
                self._finalize_corpus(output_root, corpus_id or output_root.name, all_b, np, nt, nr)
            return all_b
        finally:
            self._store.close()

    def run_corpus(
        self,
        corpus_dir: Path,
        output_root: Path,
        *,
        progress_fn: Callable[[str], None] | None = None,
        max_workers: int | None = None,
    ) -> list[FeatureBundle]:
        """Run FE over profiles listed in sequence_index.jsonl (PERF-21)."""
        self._store.initialize()
        try:
            idx = corpus_dir / "sequence_index.jsonl"
            if not idx.exists():
                raise FileNotFoundError(f"Corpus index not found: {idx}")
            rows = self._read_jsonl(idx)
            for row in rows:
                pk, sq = str(row.get("package_id", "")), str(row.get("sequence_file_id", ""))
                self._store.upsert_profile(
                    ProfileRecord(
                        profile_id=f"{pk}/{sq}",
                        package_id=pk,
                        sequence_file_id=sq,
                        profile_path=str(row.get("profile_path", "")),
                        fe_status="pending",
                    )
                )
            if max_workers is not None and max_workers > 1:
                ab, ap, at, ar = self._corpus_parallel(rows, output_root, max_workers, progress_fn)
            else:
                ab, ap, at, ar = self._corpus_sequential(rows, output_root, progress_fn)
            if ab:
                self._finalize_corpus(output_root, corpus_dir.name, ab, ap, at, ar, progress_fn)
            return ab
        finally:
            self._store.close()

    @staticmethod
    def _collect(outputs: list[_ProfileOutputs]) -> _ReturnT:
        ab = [o.bundle for o in outputs]
        ap = [p for o in outputs for p in o.phrases]
        at = [t for o in outputs for t in o.taxonomy_rows]
        ar = [r for o in outputs for r in o.target_roles]
        return ab, ap, at, ar

    def _corpus_sequential(
        self,
        rows: list[dict[str, Any]],
        output_root: Path,
        progress_fn: Callable[[str], None] | None,
    ) -> _ReturnT:
        results: list[_ProfileOutputs] = []
        total = len(rows)
        for i, row in enumerate(rows, 1):
            pk, sq = str(row.get("package_id", "")), str(row.get("sequence_file_id", ""))
            if progress_fn:
                progress_fn(f"sequence [{i}/{total}] {pk}/{sq}")
            try:
                results.append(
                    self._run_profile_internal(
                        Path(str(row.get("profile_path", ""))), output_root / pk / sq
                    )
                )
            except Exception as exc:
                self._store.mark_fe_error(f"{pk}/{sq}", str(exc))
                if self._options.fail_fast:
                    raise
        return self._collect(results)

    def _corpus_parallel(
        self,
        rows: list[dict[str, Any]],
        output_root: Path,
        max_workers: int,
        progress_fn: Callable[[str], None] | None,
    ) -> _ReturnT:
        def _proc(row: dict[str, Any]) -> _ProfileOutputs | None:
            pk, sq = str(row.get("package_id", "")), str(row.get("sequence_file_id", ""))
            try:
                return self._run_profile_internal(
                    Path(str(row.get("profile_path", ""))), output_root / pk / sq
                )
            except Exception as exc:
                with self._store_lock:
                    self._store.mark_fe_error(f"{pk}/{sq}", str(exc))
                if self._options.fail_fast:
                    raise
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futs = {executor.submit(_proc, r): r for r in rows}
            results = [fut.result() for fut in as_completed(futs)]
        return self._collect([o for o in results if o is not None])

    def _run_profile_internal(self, profile_dir: Path, output_dir: Path) -> _ProfileOutputs:
        md = self._read_json(profile_dir / "sequence_metadata.json")
        li = self._read_json(profile_dir / "lineage_index.json")
        dur = md.get("sequence_duration_ms")
        disc = self._discovery.discover_audio(
            AudioDiscoveryContext(
                profile_dir=profile_dir,
                media_file=str(md.get("media_file") or ""),
                song=str(md.get("song") or ""),
                artist=str(md.get("artist") or ""),
                sequence_filename=str(li.get("sequence_file", {}).get("filename") or ""),
                sequence_duration_ms=int(dur) if dur else None,
            )
        )
        disc = self._discovery.run_audio_analysis(
            disc,
            analyzer=self._analyzer,
            analyzer_version=self._options.analyzer_version,
            force_reprocess=self._options.force_reprocess_audio,
            audio_required=self._options.audio_required,
        )
        bundle = FeatureBundle(
            schema_version=FEATURE_BUNDLE_SCHEMA_VERSION,
            source_profile_path=str(profile_dir),
            package_id=str(md.get("package_id")),
            sequence_file_id=str(md.get("sequence_file_id")),
            sequence_sha256=str(md.get("sequence_sha256")),
            song=str(md.get("song") or ""),
            artist=str(md.get("artist") or ""),
            audio=disc,
        )
        self._writer.write_audio_discovery_json(output_dir, disc)
        self._writer.write_feature_bundle_json(output_dir, bundle)
        ae, ee = self._align(
            profile_dir,
            output_dir,
            bundle.package_id,
            bundle.sequence_file_id,
            disc.audio_path,
            disc.analyzer_error,
        )
        ph = self._encode(output_dir, bundle.package_id, bundle.sequence_file_id, ae, ee)
        tx = self._classify(output_dir, bundle.package_id, bundle.sequence_file_id, ph)
        tr = self._assign_roles(output_dir, bundle.package_id, bundle.sequence_file_id, ee, ph, tx)
        return _ProfileOutputs(bundle=bundle, phrases=ph, taxonomy_rows=tx, target_roles=tr)

    def _align(
        self,
        profile_dir: Path,
        output_dir: Path,
        pkg: str,
        seq: str,
        audio_path: str | None,
        analyzer_error: str | None,
    ) -> tuple[tuple[AlignedEffectEvent, ...], list[dict[str, Any]]]:
        if not self._options.enable_alignment:
            return (), []
        ep = profile_dir / "enriched_effect_events.json"
        if not ep.exists():
            return (), []
        ee = json.loads(ep.read_text(encoding="utf-8"))
        if not isinstance(ee, list):
            raise ValueError(f"Expected list in {ep}")
        af = None
        if audio_path is not None and analyzer_error is None and self._analyzer is not None:
            af = getattr(
                self._analyzer.analyze_sync(
                    audio_path, force_reprocess=self._options.force_reprocess_audio
                ),
                "features",
                None,
            )
            if not isinstance(af, dict):
                raise ValueError("Audio analyzer returned invalid bundle without features")
        ae = self._components.alignment.align_events(
            package_id=pkg, sequence_file_id=seq, events=ee, audio_features=af
        )
        self._writer.write_aligned_events(output_dir, ae)
        return ae, ee

    def _encode(
        self,
        output_dir: Path,
        pkg: str,
        seq: str,
        ae: tuple[AlignedEffectEvent, ...],
        ee: list[dict[str, Any]],
    ) -> tuple[EffectPhrase, ...]:
        if not self._options.enable_phrase_encoding or not ae:
            return ()
        ph = self._components.phrase_encoder.encode(
            package_id=pkg, sequence_file_id=seq, aligned_events=ae, enriched_events=ee
        )
        self._writer.write_effect_phrases(output_dir, ph)
        with self._store_lock:
            self._store.upsert_phrases(ph)
        return ph

    def _classify(
        self, output_dir: Path, pkg: str, seq: str, phrases: tuple[EffectPhrase, ...]
    ) -> tuple[PhraseTaxonomyRecord, ...]:
        if not self._options.enable_taxonomy or not phrases:
            return ()
        rows = self._components.taxonomy_classifier.classify(
            phrases=phrases, package_id=pkg, sequence_file_id=seq
        )
        self._writer.write_phrase_taxonomy(output_dir, rows)
        with self._store_lock:
            self._store.upsert_taxonomy(rows)
        return rows

    def _assign_roles(
        self,
        output_dir: Path,
        pkg: str,
        seq: str,
        ee: list[dict[str, Any]],
        phrases: tuple[EffectPhrase, ...],
        tx: tuple[PhraseTaxonomyRecord, ...],
    ) -> tuple[TargetRoleAssignment, ...]:
        if not self._options.enable_target_roles or not ee:
            return ()
        rows = self._components.target_roles.assign(
            package_id=pkg,
            sequence_file_id=seq,
            enriched_events=ee,
            phrases=phrases,
            taxonomy_rows=tx,
        )
        self._writer.write_target_roles(output_dir, rows)
        return rows

    def _write_template_catalogs(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        target_roles: tuple[TargetRoleAssignment, ...],
        progress_fn: Callable[[str], None] | None = None,
    ) -> tuple[TemplateCatalog, TemplateCatalog] | None:
        return _ca.write_template_catalogs(
            output_root=output_root,
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
            options=self._options,
            writer=self._writer,
            components=self._components,
            store=self._store,
            progress_fn=progress_fn,
        )

    def _write_color_arc(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
    ) -> Path | None:
        return _ca.write_color_arc(
            output_root=output_root,
            phrases=phrases,
            color_rows=color_rows,
            options=self._options,
            writer=self._writer,
            components=self._components,
        )

    def _write_propensity(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
    ) -> tuple[Path | None, PropensityIndex | None]:
        return _ca.write_propensity(
            output_root=output_root,
            phrases=phrases,
            options=self._options,
            writer=self._writer,
            components=self._components,
        )

    def _write_style_fingerprint(
        self,
        *,
        output_root: Path,
        creator_id: str,
        phrases: tuple[EffectPhrase, ...],
        layering_rows: tuple[LayeringFeatureRow, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
        transition_graph: TransitionGraph | None,
    ) -> Path | None:
        return _ca.write_style_fingerprint(
            output_root=output_root,
            creator_id=creator_id,
            phrases=phrases,
            layering_rows=layering_rows,
            color_rows=color_rows,
            transition_graph=transition_graph,
            options=self._options,
            writer=self._writer,
            components=self._components,
        )

    def _load_existing_bundles(
        self, profiles: tuple[ProfileRecord, ...], output_root: Path
    ) -> list[FeatureBundle]:
        out: list[FeatureBundle] = []
        for p in profiles:
            bp = output_root / p.package_id / p.sequence_file_id / "feature_bundle.json"
            if bp.exists():
                try:
                    out.append(FeatureBundle.model_validate(json.loads(bp.read_text("utf-8"))))
                except Exception:
                    pass
        return out
