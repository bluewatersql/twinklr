"""Top-level orchestration for sequence pack profiling."""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.models import ProfileRecord
from twinklr.core.feature_store.protocols import FeatureStoreProviderSync
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.profiling.artifacts import ProfileArtifactWriter
from twinklr.core.profiling.effects.analyzer import compute_effect_statistics
from twinklr.core.profiling.effects.extractor import extract_effect_events
from twinklr.core.profiling.effects.palette import parse_color_palettes
from twinklr.core.profiling.enrich import enrich_events
from twinklr.core.profiling.inventory import build_asset_inventory
from twinklr.core.profiling.layout.profiler import LayoutProfiler
from twinklr.core.profiling.models.effects import EffectStatistics
from twinklr.core.profiling.models.events import BaseEffectEventsFile, EffectEventRecord
from twinklr.core.profiling.models.layout import LayoutProfile
from twinklr.core.profiling.models.pack import PackageManifest
from twinklr.core.profiling.models.palette import ColorPaletteProfile
from twinklr.core.profiling.models.profile import (
    AssetInventory,
    EnrichedEventRecord,
    LineageIndex,
    SequenceMetadata,
    SequencePackProfile,
)
from twinklr.core.profiling.pack.ingestor import ingest_zip, sha256_file


class SequencePackProfiler:
    """Orchestrate package ingestion, parsing, enrichment, and artifact writing."""

    def __init__(
        self,
        *,
        layout_profiler: LayoutProfiler | None = None,
        xsq_parser: XSQParser | None = None,
        artifact_writer: ProfileArtifactWriter | None = None,
        store: FeatureStoreProviderSync | None = None,
    ) -> None:
        self._layout_profiler = layout_profiler or LayoutProfiler()
        self._xsq_parser = xsq_parser or XSQParser()
        self._artifact_writer = artifact_writer or ProfileArtifactWriter()
        self._store: FeatureStoreProviderSync = store or NullFeatureStore()

    def profile_layout(self, xml_path: Path) -> LayoutProfile:
        """Profile a standalone rgb effects layout file."""
        return self._layout_profiler.profile(xml_path)

    def profile_effects(self, events: list[EffectEventRecord] | tuple[EffectEventRecord, ...]):
        """Compute effect statistics from already-extracted events."""
        return compute_effect_statistics(events)

    @staticmethod
    def _derive_song_title(raw_song: str, media_file: str, sequence_filename: str) -> str:
        """Return song title with practical fallbacks for sparse XSQ metadata."""
        if raw_song.strip():
            return raw_song.strip()

        if media_file.strip():
            media_name = media_file.replace("\\", "/").split("/")[-1]
            if media_name:
                stem = Path(media_name).stem
                if stem:
                    return stem

        return Path(sequence_filename).stem

    def profile(
        self,
        zip_path: Path,
        output_dir: Path,
        *,
        force: bool = False,
    ) -> SequencePackProfile:
        """Run the full profiling pipeline on a zip/xsqz package.

        If a store is configured and the zip SHA256 matches an existing profile
        (and profile_dir exists on disk), returns the existing profile without
        re-profiling. Use force=True to override skip logic.

        Args:
            zip_path: Path to .zip or .xsqz package.
            output_dir: Directory for profile artifacts (JSON, markdown).
            force: If True, always run full pipeline; ignore skip logic.

        Returns:
            SequencePackProfile (new or loaded from disk).

        Raises:
            ValueError: No sequence file found in package manifest.
        """
        if not force:
            existing = self._check_existing(zip_path, output_dir)
            if existing is not None:
                return existing

        manifest, extracted_dir = ingest_zip(zip_path)

        files_by_id = {entry.file_id: entry for entry in manifest.files}

        layout_profile = None
        rgb_entry = files_by_id.get(manifest.rgb_effects_file_id or "")
        if rgb_entry is not None:
            layout_profile = self._layout_profiler.profile(extracted_dir / rgb_entry.filename)

        sequence_entry = files_by_id.get(manifest.sequence_file_id or "")
        if sequence_entry is None:
            raise ValueError("No sequence file found in package manifest")

        sequence_path = extracted_dir / sequence_entry.filename
        sequence = self._xsq_parser.parse(sequence_path)

        base_events = extract_effect_events(
            sequence=sequence,
            package_id=manifest.package_id,
            sequence_file_id=sequence_entry.file_id,
            sequence_sha256=sequence_entry.sha256,
        )
        enriched_events = enrich_events(base_events.events, layout_profile)
        effect_statistics = compute_effect_statistics(base_events.events)
        palette_profile = parse_color_palettes(sequence)
        asset_inventory = build_asset_inventory(manifest)

        sequence_metadata = SequenceMetadata(
            package_id=manifest.package_id,
            sequence_file_id=sequence_entry.file_id,
            sequence_sha256=sequence_entry.sha256,
            xlights_version=sequence.version,
            sequence_duration_ms=sequence.sequence_duration_ms,
            media_file=sequence.media_file,
            image_dir=sequence.head.image_dir,
            song=self._derive_song_title(
                raw_song=sequence.head.song,
                media_file=sequence.media_file,
                sequence_filename=sequence_entry.filename,
            ),
            artist=sequence.head.artist,
            album=sequence.head.album,
            author=sequence.head.author,
        )

        rgb_lineage = None
        layout_id = None
        rgb_sha256 = None
        if rgb_entry is not None and layout_profile is not None:
            rgb_lineage = {
                "file_id": rgb_entry.file_id,
                "filename": rgb_entry.filename,
            }
            layout_id = layout_profile.metadata.file_sha256
            rgb_sha256 = rgb_entry.sha256

        profile = SequencePackProfile(
            manifest=manifest,
            sequence_metadata=sequence_metadata,
            layout_profile=layout_profile,
            effect_statistics=effect_statistics,
            palette_profile=palette_profile,
            asset_inventory=asset_inventory,
            base_events=base_events,
            enriched_events=enriched_events,
            lineage=LineageIndex(
                package_id=manifest.package_id,
                zip_sha256=manifest.zip_sha256,
                sequence_file={
                    "file_id": sequence_entry.file_id,
                    "filename": sequence_entry.filename,
                },
                rgb_effects_file=rgb_lineage,
                layout_id=layout_id,
                rgb_sha256=rgb_sha256,
            ),
        )

        self._artifact_writer.write_json_bundle(Path(output_dir), profile)
        self._artifact_writer.write_markdown_bundle(Path(output_dir), profile)
        self._register_profile(profile, output_dir)
        return profile

    def _check_existing(
        self,
        zip_path: Path,
        output_dir: Path,
    ) -> SequencePackProfile | None:
        """Return an existing profile if skip conditions are met, else None.

        Args:
            zip_path: Path to the source zip archive.
            output_dir: Expected output directory for profile artifacts.

        Returns:
            A loaded SequencePackProfile if skip conditions are met, else None.
        """
        # Store check (non-Null store)
        if not isinstance(self._store, NullFeatureStore):
            zip_sha = self._compute_zip_sha(zip_path)
            records = self._store.query_profiles()
            record = next((r for r in records if r.zip_sha256 == zip_sha), None)
            if record is not None:
                profile_dir = Path(record.profile_path)
                if profile_dir.exists():
                    return self._load_existing_profile(profile_dir)
            # Store configured — no file fallback
            return None

        # File fallback (NullFeatureStore or no store)
        metadata_path = output_dir / "sequence_metadata.json"
        if metadata_path.exists():
            return self._load_existing_profile(output_dir)

        return None

    def _register_profile(
        self,
        profile: SequencePackProfile,
        output_dir: Path,
    ) -> None:
        """Register a newly profiled sequence in the feature store.

        Args:
            profile: The completed SequencePackProfile to register.
            output_dir: Directory where profile artifacts were written.
        """
        from datetime import UTC, datetime

        record = ProfileRecord(
            profile_id=f"{profile.manifest.package_id}/{profile.sequence_metadata.sequence_file_id}",
            package_id=profile.manifest.package_id,
            sequence_file_id=profile.sequence_metadata.sequence_file_id,
            profile_path=str(output_dir.resolve()),
            zip_sha256=profile.lineage.zip_sha256,
            sequence_sha256=profile.sequence_metadata.sequence_sha256,
            song=profile.sequence_metadata.song,
            artist=profile.sequence_metadata.artist,
            duration_ms=profile.sequence_metadata.sequence_duration_ms,
            effect_total_events=len(profile.base_events.events),
            fe_status="pending",
            profiled_at=datetime.now(UTC).isoformat(),
        )
        self._store.upsert_profile(record)

    def _load_existing_profile(self, profile_dir: Path) -> SequencePackProfile:
        """Load a SequencePackProfile from on-disk JSON artifacts.

        Args:
            profile_dir: Directory containing profile JSON artifacts.

        Returns:
            A SequencePackProfile reconstructed from the artifact files.
        """
        manifest = PackageManifest.model_validate(
            json.loads((profile_dir / "package_manifest.json").read_text(encoding="utf-8"))
        )
        sequence_metadata = SequenceMetadata.model_validate(
            json.loads((profile_dir / "sequence_metadata.json").read_text(encoding="utf-8"))
        )
        base_events = BaseEffectEventsFile.model_validate(
            json.loads((profile_dir / "base_effect_events.json").read_text(encoding="utf-8"))
        )
        enriched_events = tuple(
            EnrichedEventRecord.model_validate(ev)
            for ev in json.loads(
                (profile_dir / "enriched_effect_events.json").read_text(encoding="utf-8")
            )
        )
        effect_statistics = EffectStatistics.model_validate(
            json.loads((profile_dir / "effect_statistics.json").read_text(encoding="utf-8"))
        )
        palette_profile = ColorPaletteProfile.model_validate(
            json.loads((profile_dir / "color_palettes.json").read_text(encoding="utf-8"))
        )
        asset_inventory_path = profile_dir / "asset_inventory.json"
        shader_inventory_path = profile_dir / "shader_inventory.json"
        assets = tuple(
            json.loads(asset_inventory_path.read_text(encoding="utf-8"))
            if asset_inventory_path.exists()
            else []
        )
        shaders = tuple(
            json.loads(shader_inventory_path.read_text(encoding="utf-8"))
            if shader_inventory_path.exists()
            else []
        )
        asset_inventory = AssetInventory(assets=assets, shaders=shaders)
        lineage = LineageIndex.model_validate(
            json.loads((profile_dir / "lineage_index.json").read_text(encoding="utf-8"))
        )

        layout_profile: LayoutProfile | None = None
        rgbeffects_path = profile_dir / "rgbeffects_profile.json"
        if rgbeffects_path.exists():
            layout_profile = LayoutProfile.model_validate(
                json.loads(rgbeffects_path.read_text(encoding="utf-8"))
            )

        return SequencePackProfile(
            manifest=manifest,
            sequence_metadata=sequence_metadata,
            layout_profile=layout_profile,
            effect_statistics=effect_statistics,
            palette_profile=palette_profile,
            asset_inventory=asset_inventory,
            base_events=base_events,
            enriched_events=enriched_events,
            lineage=lineage,
        )

    def _compute_zip_sha(self, zip_path: Path) -> str:
        """Return SHA-256 hex digest of the source archive.

        Args:
            zip_path: Path to the zip/xsqz archive.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        return sha256_file(zip_path)
