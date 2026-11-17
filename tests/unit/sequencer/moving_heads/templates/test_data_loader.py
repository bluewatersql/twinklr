"""Data-form moving-head template loading, linting, and conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.sequencer.models.enum import (
    TemplateCategory,
    TimingMode,
)
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Movement,
    PhysicalMovementSpec,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.templates.data_loader import (
    PHYSICAL_TEMPLATE_DIR,
    admit_physical_catalog,
    load_template_document,
    load_templates_from_directory,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    InvalidTemplateError,
    TemplateRegistry,
)


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
        movement=Movement(
            physical=PhysicalMovementSpec(
                shape="hold", mode="finite", start_pan_deg=0.0, start_tilt_deg=0.0
            )
        ),
        dimmer=Dimmer(),
    )
    return TemplateDoc(
        enabled=enabled,
        template=Template(
            template_id=template_id,
            version=1,
            name=template_id.replace("_", " ").title(),
            category=TemplateCategory.MEDIUM_ENERGY,
            repeat=RepeatContract(
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


def dump_template_document(document: TemplateDoc) -> str:
    """Canonical JSON of a template document, as a data template file holds it."""
    payload = document.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_doc(directory: Path, doc: TemplateDoc) -> Path:
    path = directory / f"{doc.template.template_id}.json"
    path.write_text(dump_template_document(doc), encoding="utf-8")
    return path


def test_data_template_registers(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    _write_doc(tmp_path, _doc())

    loaded = load_templates_from_directory(tmp_path, registry=registry)

    assert loaded == ["data_only"]
    assert registry.get("Data Only").template.template_id == "data_only"


def test_duplicate_template_id_across_sources_is_loud(tmp_path: Path) -> None:
    registry = TemplateRegistry()
    registry.register(lambda: _doc("collision"), source="python:test")
    _write_doc(tmp_path, _doc("collision"))

    with pytest.raises(
        ValueError,
        match=r"collision.*python:test.*data:.*collision\.json",
    ):
        load_templates_from_directory(tmp_path, registry=registry)


def test_family_catalog_is_admitted_once_into_the_given_registry() -> None:
    """The family catalog loads into the registry it is given, once however many runs
    admit it; its documents' source names the catalog directory."""
    registry = TemplateRegistry()
    loaded = admit_physical_catalog(registry=registry)

    assert loaded == [path.stem for path in sorted(PHYSICAL_TEMPLATE_DIR.glob("*.json"))]
    assert len(loaded) == 7  # six P2.4c families and the P2.5 zoom pilot
    for template_id in loaded:
        source = Path(registry.source(template_id).removeprefix("data:"))
        assert source.parent == PHYSICAL_TEMPLATE_DIR

    # A later run in the same process keeps them.
    assert admit_physical_catalog(registry=registry) == loaded
    assert len(registry.list_all()) == 7


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
