"""Top-level orchestration for sequence pack profiling."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.profiling.artifacts import ProfileArtifactWriter
from twinklr.core.profiling.effects.analyzer import compute_effect_statistics
from twinklr.core.profiling.effects.extractor import extract_effect_events
from twinklr.core.profiling.effects.palette import parse_color_palettes
from twinklr.core.profiling.enrich import enrich_events
from twinklr.core.profiling.inventory import build_asset_inventory
from twinklr.core.profiling.layout.profiler import LayoutProfiler
from twinklr.core.profiling.models.events import EffectEventRecord
from twinklr.core.profiling.models.layout import LayoutProfile
from twinklr.core.profiling.models.profile import (
    LineageIndex,
    SequenceMetadata,
    SequencePackProfile,
)
from twinklr.core.profiling.pack.ingestor import ingest_zip


class SequencePackProfiler:
    """Orchestrate package ingestion, parsing, enrichment, and artifact writing."""

    def __init__(
        self,
        *,
        layout_profiler: LayoutProfiler | None = None,
        xsq_parser: XSQParser | None = None,
        artifact_writer: ProfileArtifactWriter | None = None,
    ) -> None:
        self._layout_profiler = layout_profiler or LayoutProfiler()
        self._xsq_parser = xsq_parser or XSQParser()
        self._artifact_writer = artifact_writer or ProfileArtifactWriter()

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

    def profile(self, zip_path: Path, output_dir: Path) -> SequencePackProfile:
        """Run the full profiling pipeline on a zip/xsqz package."""
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
        return profile
