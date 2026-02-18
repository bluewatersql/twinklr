"""Artifact writing helpers for sequence pack profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from twinklr.core.profiling.models.profile import SequencePackProfile
from twinklr.core.profiling.report import generate_layout_report_md, generate_profile_summary_md


class ProfileArtifactWriter:
    """Write JSON and markdown artifacts for profiling outputs."""

    def _write_json(self, path: Path, obj: BaseModel | dict | list) -> None:
        data: Any
        if isinstance(obj, BaseModel):
            data = obj.model_dump(mode="json", exclude_none=True)
        else:
            data = obj
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_json_bundle(self, output_dir: Path, profile: SequencePackProfile) -> None:
        """Write canonical JSON outputs for a full profile."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(output_dir / "package_manifest.json", profile.manifest)
        self._write_json(output_dir / "sequence_metadata.json", profile.sequence_metadata)
        self._write_json(output_dir / "base_effect_events.json", profile.base_events)
        self._write_json(
            output_dir / "enriched_effect_events.json",
            [event.model_dump(exclude_none=True) for event in profile.enriched_events],
        )
        self._write_json(output_dir / "effect_statistics.json", profile.effect_statistics)
        self._write_json(output_dir / "color_palettes.json", profile.palette_profile)
        self._write_json(
            output_dir / "asset_inventory.json",
            list(profile.asset_inventory.assets),
        )
        self._write_json(
            output_dir / "shader_inventory.json",
            list(profile.asset_inventory.shaders),
        )
        self._write_json(output_dir / "lineage_index.json", profile.lineage)

        if profile.layout_profile is not None:
            self._write_json(output_dir / "rgbeffects_profile.json", profile.layout_profile)
            layout_semantics = {}
            for model in profile.layout_profile.models:
                layout_semantics[model.name] = {
                    "target_kind": "model",
                    "x0": model.position.get("world_x"),
                    "y0": model.position.get("world_y"),
                    "x1": model.position.get("world_x"),
                    "y1": model.position.get("world_y"),
                }
            for group in profile.layout_profile.groups:
                layout_semantics[group.name] = {
                    "target_kind": "group",
                    "x0": None,
                    "y0": None,
                    "x1": None,
                    "y1": None,
                }
            self._write_json(output_dir / "layout_semantics.json", layout_semantics)

    def write_markdown_bundle(self, output_dir: Path, profile: SequencePackProfile) -> None:
        """Write markdown summaries for full/layout profile outputs."""
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "profile_summary.md").write_text(
            generate_profile_summary_md(profile),
            encoding="utf-8",
        )
        if profile.layout_profile is not None:
            (output_dir / "profile_rgbeffects.md").write_text(
                generate_layout_report_md(profile.layout_profile),
                encoding="utf-8",
            )
