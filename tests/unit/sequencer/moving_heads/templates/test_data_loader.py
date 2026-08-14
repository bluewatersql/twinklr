"""Data-form moving-head template loading, linting, and conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import (
    FixtureContext,
    SectionRenderIntent,
    TemplateCompileContext,
)
from twinklr.core.sequencer.models.enum import Intensity, TemplateCategory, TimingMode
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import compile_template
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.templates import (
    get_template,
    list_templates,
    load_builtin_templates,
)
from twinklr.core.sequencer.moving_heads.templates.converter import (
    dump_template_document,
    export_registry,
)
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    DEFAULT_DATA_TEMPLATE_DIR,
    load_template_document,
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    InvalidTemplateError,
    TemplateRegistry,
)
from twinklr.core.sequencer.moving_heads.templates.utils import TemplateRoleHelper
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


@pytest.fixture(scope="module", autouse=True)
def _load_builtins() -> None:
    load_builtin_templates()


def _doc(
    template_id: str = "data_only",
    *,
    enabled: bool = True,
    duration_bars: float = 1.0,
    cycle_bars: float = 1.0,
    energy_range: tuple[int, int] | None = (20, 60),
    recommended_sections: list[str] | None = None,
) -> TemplateDoc:
    step = TemplateStep(
        step_id="main",
        timing=StepTiming(
            base_timing=BaseTiming(
                mode=TimingMode.MUSICAL,
                start_offset_bars=0.0,
                duration_bars=duration_bars,
            )
        ),
        geometry=Geometry(geometry_type=GeometryType.ROLE_POSE),
        movement=Movement(movement_type=MovementType.SWEEP_LR, intensity=Intensity.SMOOTH),
        dimmer=Dimmer(dimmer_type=DimmerType.PULSE, intensity=Intensity.SMOOTH),
    )
    return TemplateDoc(
        enabled=enabled,
        template=Template(
            template_id=template_id,
            version=1,
            name=template_id.replace("_", " ").title(),
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.JOINER,
                cycle_bars=cycle_bars,
                loop_step_ids=["main"],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            steps=[step],
            metadata=TemplateMetadata(
                tags=["test"],
                energy_range=energy_range,
                recommended_sections=(
                    ["verse"] if recommended_sections is None else recommended_sections
                ),
                description="Data-only test template.",
            ),
        ),
    )


def _write_doc(directory: Path, doc: TemplateDoc) -> Path:
    path = directory / f"{doc.template.template_id}.json"
    path.write_text(dump_template_document(doc), encoding="utf-8")
    return path


def test_all_builtins_round_trip_through_data_form() -> None:
    infos = list_templates()
    assert len(infos) == 37

    for info in infos:
        original = get_template(info.template_id)
        restored = TemplateDoc.model_validate_json(dump_template_document(original))
        assert restored == original, info.template_id


def test_converter_exports_all_builtins_round_trip_exact(tmp_path: Path) -> None:
    written = export_registry(tmp_path / "first")
    second = export_registry(tmp_path / "second")

    assert len(written) == 37
    assert [path.name for path in written] == sorted(path.name for path in written)
    assert [path.read_bytes() for path in written] == [path.read_bytes() for path in second]
    for path in written:
        restored = load_template_document(path)
        assert restored == get_template(restored.template.template_id)


def test_data_template_registers_and_renders(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    _write_doc(tmp_path, _doc())

    loaded = load_templates_from_directory(tmp_path, registry=registry)

    assert loaded == ["data_only"]
    assert registry.get("Data Only").template.template_id == "data_only"
    assert _emitted_settings(registry.get("data_only"))


def test_duplicate_template_id_across_sources_is_loud(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    registry.register(lambda: _doc("collision"), source="python:test")
    _write_doc(tmp_path, _doc("collision"))

    with pytest.raises(
        ValueError,
        match=r"collision.*python:test.*data:.*collision\.json",
    ):
        load_templates_from_directory(tmp_path, registry=registry)


def _registry_with_python_builtins() -> TemplateRegistry:
    registry = TemplateRegistry()
    for info in list_templates():
        document = get_template(info.template_id)
        registry.register(lambda document=document: document, source="python:builtin")
    return registry


def test_tracked_data_proofs_load_alongside_all_python_builtins_only_with_override() -> None:
    registry = _registry_with_python_builtins()

    with pytest.raises(ValueError, match=r"collision.*python:builtin"):
        load_templates_from_directory(DEFAULT_DATA_TEMPLATE_DIR, registry=registry)

    registry = _registry_with_python_builtins()
    loaded = load_templates_from_directory(
        DEFAULT_DATA_TEMPLATE_DIR,
        registry=registry,
        allow_overrides=True,
    )

    assert loaded == [
        "accent_snap_tunnel_hit",
        "ambient_random_wash",
        "figure8_mirror_strobe",
    ]
    assert len(registry.list_all()) == 37


def test_explicit_override_replaces_python_source(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    original = _doc("replace_me")
    original.template.name = "Legacy Display Name"
    registry.register(lambda: original, source="python:test")
    replacement = _doc("replace_me").model_copy(deep=True)
    replacement.template.name = "Data Replacement"
    _write_doc(tmp_path, replacement)

    load_templates_from_directory(tmp_path, registry=registry, allow_overrides=True)

    assert registry.get("replace_me").template.name == "Data Replacement"
    with pytest.raises(KeyError):
        registry.get("Legacy Display Name")
    assert registry.get("Data Replacement").template.template_id == "replace_me"


def test_valid_disabled_data_template_is_skipped(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    _write_doc(tmp_path, _doc("disabled", enabled=False))

    loaded = load_templates_from_directory(tmp_path, registry=registry)

    assert loaded == []
    assert registry.list_all() == []


def test_invalid_disabled_data_template_is_rejected_before_skip(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    _write_doc(
        tmp_path,
        _doc("disabled_invalid", enabled=False, duration_bars=999.0, cycle_bars=8.0),
    )

    with pytest.raises(InvalidTemplateError, match=r"span 999\.0 bars.*cycle_bars is 8\.0"):
        load_templates_from_directory(tmp_path, registry=registry)

    assert registry.list_all() == []


def _named_doc(template_id: str, name: str) -> TemplateDoc:
    document = _doc(template_id)
    document.template.name = name
    return document


def test_normalized_template_id_collision_is_loud_and_cannot_override() -> None:
    registry = TemplateRegistry()
    registry.register(lambda: _doc("fan-pulse"), source="python:first")

    with pytest.raises(
        ValueError,
        match=r"fan_pulse.*python:first.*data:second",
    ):
        registry.register_document(
            _doc("fan_pulse"),
            source="data:second",
            allow_override=True,
        )

    assert len(registry.list_all()) == 1
    assert registry.get("fan_pulse").template.template_id == "fan-pulse"


def test_duplicate_normalized_display_name_is_loud_with_both_sources() -> None:
    registry = TemplateRegistry()
    registry.register(
        lambda: _named_doc("first", "Shared Display Name"),
        source="python:first",
    )

    with pytest.raises(
        ValueError,
        match=r"shared_display_name.*python:first.*data:second",
    ):
        registry.register_document(
            _named_doc("second", "Shared-Display-Name"),
            source="data:second",
        )


def test_duplicate_normalized_explicit_alias_is_loud_with_both_sources() -> None:
    registry = TemplateRegistry()
    registry.register(
        lambda: _doc("first"),
        aliases=["Special Alias"],
        source="python:first",
    )

    with pytest.raises(
        ValueError,
        match=r"special_alias.*python:first.*data:second",
    ):
        registry.register_document(
            _doc("second"),
            aliases=["Special-Alias"],
            source="data:second",
        )


def test_override_cannot_steal_an_unrelated_alias() -> None:
    registry = TemplateRegistry()
    registry.register(
        lambda: _named_doc("replace_me", "Original Name"),
        source="python:target",
    )
    registry.register(
        lambda: _doc("other"),
        aliases=["Reserved Alias"],
        source="python:other",
    )

    with pytest.raises(
        ValueError,
        match=r"reserved_alias.*python:other.*data:replacement",
    ):
        registry.register_document(
            _named_doc("replace_me", "Replacement Name"),
            aliases=["Reserved-Alias"],
            source="data:replacement",
            allow_override=True,
        )


def test_failed_override_is_atomic_and_preserves_incumbent_registration() -> None:
    registry = TemplateRegistry()
    original = _named_doc("replace_me", "Original Name")
    original.template.metadata.tags = ["original"]
    registry.register(lambda: original, source="python:target")
    registry.register(
        lambda: _doc("other"),
        aliases=["Reserved Alias"],
        source="python:other",
    )

    with pytest.raises(ValueError):
        registry.register_document(
            _named_doc("replace_me", "Replacement Name"),
            aliases=["Reserved Alias"],
            source="data:replacement",
            allow_override=True,
        )

    assert len(registry.list_all()) == 2
    assert registry.get("replace_me").template.name == "Original Name"
    assert registry.get("Original Name").template.metadata.tags == ["original"]
    assert registry.get("Reserved Alias").template.template_id == "other"
    with pytest.raises(KeyError):
        registry.get("Replacement Name")


def test_data_registry_returns_fresh_instances(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    _write_doc(tmp_path, _doc("fresh"))
    load_templates_from_directory(tmp_path, registry=registry)

    first = registry.get("fresh")
    first.template.name = "Mutated"

    assert registry.get("fresh").template.name == "Fresh"


def test_loader_rejects_unknown_fields_with_source_path(tmp_path: Path) -> None:
    payload = json.loads(dump_template_document(_doc()))
    payload["unknown"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=r"bad\.json.*unknown"):
        load_template_document(path)


def test_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"enabled": true, "enabled": false}', encoding="utf-8")

    with pytest.raises(ValueError, match=r"duplicate\.json.*duplicate JSON object key"):
        load_template_document(path)


def test_loader_requires_declared_remainder_policy(tmp_path: Path) -> None:
    payload = json.loads(dump_template_document(_doc()))
    del payload["template"]["repeat"]["remainder_policy"]
    path = tmp_path / "implicit-remainder.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=r"remainder_policy must be declared"):
        load_template_document(path)


def test_linter_rejects_overrunning_template() -> None:
    doc = _doc(duration_bars=2.0, cycle_bars=1.0)

    with pytest.raises(InvalidTemplateError, match=r"span 2\.0 bars.*cycle_bars is 1\.0"):
        TemplateRegistry().register_document(doc, source="data:test")


@pytest.mark.parametrize(
    ("energy_range", "sections", "message"),
    [
        (None, ["verse"], "energy_range"),
        ((80, 20), ["verse"], "ordered"),
        ((20, 80), [], "recommended_sections"),
    ],
)
def test_linter_rejects_missing_annotations(
    energy_range: tuple[int, int] | None,
    sections: list[str],
    message: str,
) -> None:
    doc = _doc(energy_range=energy_range, recommended_sections=sections)

    with pytest.raises(InvalidTemplateError, match=message):
        TemplateRegistry().register_document(doc, source="data:test")


def test_python_factory_and_data_document_share_annotation_linter() -> None:
    doc = _doc(energy_range=None)

    with pytest.raises(InvalidTemplateError, match="energy_range"):
        TemplateRegistry().register(lambda: doc, source="python:test")
    with pytest.raises(InvalidTemplateError, match="energy_range"):
        TemplateRegistry().register_document(doc, source="data:test")


@pytest.mark.parametrize(
    "template_id",
    ["accent_snap_tunnel_hit", "ambient_random_wash", "figure8_mirror_strobe"],
)
def test_axis_template_data_documents_match_python_builtins(template_id: str) -> None:
    restored = load_template_document(DEFAULT_DATA_TEMPLATE_DIR / f"{template_id}.json")

    assert restored == get_template(template_id)


def _emitted_settings(doc: TemplateDoc) -> list[str]:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        shutter_channel=5,
        gobo_channel=6,
        color_map={"open": 0, "blue": 24},
        shutter_map={"open": 255, "strobe_fast": 190},
        gobo_map={"open": 0, "prism": 80},
    )
    config = FixtureConfig(fixture_id="MH1", dmx_mapping=mapping)
    instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")
    fixture = FixtureContext(
        fixture_id="MH1",
        role="OUTER_LEFT",
        calibration={"fixture_config": config},
    )
    registries = create_default_registries()
    cycle_bars = doc.template.repeat.cycle_bars
    context = TemplateCompileContext(
        section_id="section",
        template_id=doc.template.template_id,
        fixtures=[fixture],
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=max(2, int(cycle_bars) + 1)),
        start_bar=1,
        duration_bars=cycle_bars,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        color_registry=registries["color"],
        shutter_registry=registries["shutter"],
        gobo_registry=registries["gobo"],
        intent=SectionRenderIntent(),
    )
    result = compile_template(doc.template, context)
    return [
        DmxSettingsBuilder(instance).build_settings_string(segment) for segment in result.segments
    ]


@pytest.mark.parametrize(
    "template_id",
    ["accent_snap_tunnel_hit", "ambient_random_wash", "figure8_mirror_strobe"],
)
def test_axis_template_data_form_emits_byte_identical_settings(template_id: str) -> None:
    python_doc = get_template(template_id)
    data_doc = load_template_document(DEFAULT_DATA_TEMPLATE_DIR / f"{template_id}.json")

    assert _emitted_settings(data_doc) == _emitted_settings(python_doc)
