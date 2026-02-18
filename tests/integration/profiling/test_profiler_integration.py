"""Integration tests for end-to-end sequence pack profiling."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from twinklr.core.profiling.profiler import SequencePackProfiler

ROOT = Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_expected_outputs(output_dir: Path, include_layout: bool) -> None:
    expected = {
        "package_manifest.json",
        "sequence_metadata.json",
        "base_effect_events.json",
        "enriched_effect_events.json",
        "effect_statistics.json",
        "color_palettes.json",
        "asset_inventory.json",
        "shader_inventory.json",
        "lineage_index.json",
        "profile_summary.md",
    }
    if include_layout:
        expected |= {"rgbeffects_profile.json", "layout_semantics.json", "profile_rgbeffects.md"}

    produced = {path.name for path in output_dir.iterdir() if path.is_file()}
    for name in expected:
        assert name in produced


def _baseline_total_models(layout_json: dict | list) -> int:
    if not isinstance(layout_json, dict):
        raise AssertionError("Unexpected baseline layout payload shape")
    if "statistics" in layout_json:
        return int(layout_json["statistics"]["total_models"])
    return int(layout_json["summary"]["model_statistics"]["total_models"])


@pytest.mark.integration
def test_profile_example2_regression(tmp_path: Path) -> None:
    example_zip = ROOT / "data" / "vendor_packages" / "example2.zip"
    baseline_dir = ROOT / "data" / "test" / "example2"
    if not example_zip.exists() or not baseline_dir.exists():
        pytest.skip("example2 fixtures are unavailable")

    baseline_effect_stats = _read_json(baseline_dir / "effect_statistics.json")
    baseline_layout = _read_json(baseline_dir / "rgbeffects_profile.json")

    copied_zip = tmp_path / "example2.zip"
    shutil.copy2(example_zip, copied_zip)

    profiler = SequencePackProfiler()
    output_dir = tmp_path / "out_example2"
    profile = profiler.profile(copied_zip, output_dir)

    assert profile.manifest.sequence_file_id is not None
    assert profile.manifest.rgb_effects_file_id is not None
    assert profile.effect_statistics.total_events == baseline_effect_stats["total_events"]
    assert profile.layout_profile is not None
    assert profile.layout_profile.statistics.total_models == _baseline_total_models(baseline_layout)
    _assert_expected_outputs(output_dir, include_layout=True)

    arch_event = next(
        (event for event in profile.enriched_events if event.target_name == "Arch 1"), None
    )
    assert arch_event is not None
    assert arch_event.target_semantic_tags == ("arch",)
    assert arch_event.target_category is not None


@pytest.mark.integration
def test_profile_example14_xsqz(tmp_path: Path) -> None:
    example_xsqz = ROOT / "data" / "vendor_packages" / "example14.xsqz"
    if not example_xsqz.exists():
        pytest.skip("example14.xsqz fixture is unavailable")

    copied_xsqz = tmp_path / "example14.xsqz"
    shutil.copy2(example_xsqz, copied_xsqz)

    profiler = SequencePackProfiler()
    output_dir = tmp_path / "out_example14"
    profile = profiler.profile(copied_xsqz, output_dir)

    assert profile.manifest.source_extensions == frozenset({".xsqz"})
    assert profile.manifest.sequence_file_id is not None
    _assert_expected_outputs(output_dir, include_layout=profile.layout_profile is not None)

    extracted_dir = copied_xsqz.parent / f"{copied_xsqz.stem}_extracted"
    leftovers = [
        path.name for path in extracted_dir.iterdir() if path.suffix.lower() in {".zip", ".xsqz"}
    ]
    assert leftovers == []


@pytest.mark.integration
def test_profile_layout_only_mode() -> None:
    layout_xml = ROOT / "data" / "test" / "example2" / "extracted" / "xlights_rgbeffects.xml"
    baseline_layout = ROOT / "data" / "test" / "example2" / "rgbeffects_profile.json"
    if not layout_xml.exists() or not baseline_layout.exists():
        pytest.skip("layout-only fixtures are unavailable")

    expected = _read_json(baseline_layout)
    layout_profile = SequencePackProfiler().profile_layout(layout_xml)
    assert layout_profile.statistics.total_models == _baseline_total_models(expected)
