"""What a real render hands the user (P1P-T11).

The unit tests in `tests/unit/formats/xlights/sequence/test_delivery_formats.py` pin the
three writers in isolation; this one drives the actual `RenderingPipeline` against a
tracked rig and inspects the files that come out — including re-parsing the emitted
`.xsq` with Twinklr's own parser, which the pre-task fresh branch could not survive
because it wrote `media_file=""`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import XLIGHTS_VERSION_STAMP
from twinklr.core.formats.xlights.sequence.parser import XSQParser
from twinklr.core.sequencer.moving_heads.delivery import DeliveryArtifacts
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

MEDIA_FILE = "golden_song.mp3"


@pytest.fixture(scope="module")
def delivery(tmp_path_factory: pytest.TempPathFactory) -> DeliveryArtifacts:
    """Render the deterministic plan on the 4-head rig and write the delivery."""
    output_dir = tmp_path_factory.mktemp("delivery")
    pipeline = RenderingPipeline(
        choreography_plan=build_plan(),
        beat_grid=build_beat_grid(),
        fixture_group=build_fixture_group(RIGS["mh4_minimal"]),
        job_config=JobConfig(),
        output_path=output_dir / "golden_song.xsq",
        media_file=MEDIA_FILE,
        song="Golden Song",
        artist="Twinklr",
    )
    pipeline.render()
    assert pipeline.artifacts is not None
    return pipeline.artifacts


def test_run_writes_all_three_deliverables(delivery: DeliveryArtifacts) -> None:
    """A run produces the sequence, the timing tracks and the mapping hint."""
    assert delivery.xsq_path.exists()
    assert delivery.xmap_path.exists()
    assert delivery.xtiming_paths, "no .xtiming written"
    assert all(path.exists() for path in delivery.xtiming_paths)


def test_fresh_xsq_reparses(delivery: DeliveryArtifacts) -> None:
    """The delivered sequence survives Twinklr's own parser."""
    reparsed = XSQParser().parse(delivery.xsq_path)

    assert reparsed.head.media_file == MEDIA_FILE
    assert reparsed.head.version == XLIGHTS_VERSION_STAMP
    assert reparsed.element_effects, "no effects in the delivered sequence"


def test_fresh_xsq_contains_only_twinklr_models(delivery: DeliveryArtifacts) -> None:
    """Generate-fresh contract: `DisplayElements` names Twinklr's own models only.

    A merged template carried every model in the user's layout plus an emptied Jukebox
    and their per-element display state, all of it regenerated from Twinklr's partial
    view of the document. The delivered file describes only what Twinklr rendered.
    """
    root = ET.parse(delivery.xsq_path).getroot()
    display_elements = root.find("DisplayElements")
    assert display_elements is not None

    models = {
        element.get("name")
        for element in display_elements.findall("Element")
        if element.get("type") != "timing"
    }
    assert models == set(delivery.model_names)
    assert all(name is not None and name.startswith(("Dmx MH", "GROUP - ")) for name in models)

    timing = {
        element.get("name")
        for element in display_elements.findall("Element")
        if element.get("type") == "timing"
    }
    assert all(name is not None and name.startswith("Twinklr ") for name in timing)


def test_xmap_names_emitted_models(delivery: DeliveryArtifacts) -> None:
    """The mapping hint corresponds to what was actually emitted."""
    lines = delivery.xmap_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "false"
    assert [line.split("\t")[0] for line in lines[1:]] == list(delivery.model_names)


def test_xtiming_markers_match_xsq_timing_tracks(delivery: DeliveryArtifacts) -> None:
    """The two deliverables carry the same instants, or a user editing against one
    would be editing against the wrong grid."""
    xsq_root = ET.parse(delivery.xsq_path).getroot()

    for xtiming_path in delivery.xtiming_paths:
        xtiming_root = ET.parse(xtiming_path).getroot()
        track_name = xtiming_root.get("name")

        xsq_element = xsq_root.find(f"ElementEffects/Element[@name='{track_name}']")
        assert xsq_element is not None, f"{track_name} missing from the .xsq"

        assert [
            (e.get("label"), e.get("starttime"), e.get("endtime"))
            for e in xtiming_root.findall("EffectLayer/Effect")
        ] == [
            (e.get("label"), e.get("startTime"), e.get("endTime"))
            for e in xsq_element.findall("EffectLayer/Effect")
        ]


def test_delivery_writes_nothing_outside_its_own_directory(delivery: DeliveryArtifacts) -> None:
    """Only the delivered artifacts appear — no stray temp sequences."""
    written = sorted(path.name for path in delivery.xsq_path.parent.iterdir())
    assert written == sorted(path.name for path in delivery.all_paths)


def test_sections_track_is_delivered(delivery: DeliveryArtifacts) -> None:
    """The section markers the render builds ship as an importable timing track."""
    names = {ET.parse(path).getroot().get("name") for path in delivery.xtiming_paths}
    assert "Twinklr AudioSections" in names
