"""P3-T3: user layout is the display graph's only topology source."""

from pathlib import Path

import pytest

from twinklr.core.formats.xlights.layout import load_layout
from twinklr.core.formats.xlights.layout.choreography import layout_to_choreography
from twinklr.core.formats.xlights.layout.models.rgb_effects import (
    Layout,
    Model,
    ModelGroup,
    ModelGroups,
    Models,
)
from twinklr.core.sequencer.vocabulary.display import DisplayElementKind, GroupArrangement
from twinklr.core.sequencer.vocabulary.spatial import HorizontalZone, VerticalZone

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


def test_layout_groups_and_unclaimed_models_become_planner_groups() -> None:
    graph, mapping = layout_to_choreography(
        load_layout(FIXTURES / "display_layout_a.xml"), graph_id="layout_a"
    )

    assert [group.id for group in graph.groups] == ["YARD_ARCHES", "MEGA_TREE"]
    arches, tree = graph.groups
    assert arches.element_kind is DisplayElementKind.ARCH
    assert arches.arrangement is GroupArrangement.HORIZONTAL_ROW
    assert arches.fixture_count == 2
    assert tree.element_kind is DisplayElementKind.TREE
    assert tree.fixture_count == 1
    assert arches.pixel_fraction == pytest.approx(100 / 900)
    assert tree.pixel_fraction == pytest.approx(800 / 900)
    assert sum(group.pixel_fraction for group in graph.groups) == pytest.approx(1.0)
    assert arches.position is not None
    assert arches.position.horizontal is HorizontalZone.CENTER
    assert arches.position.vertical is VerticalZone.GROUND
    assert tree.position is not None
    assert tree.position.vertical is VerticalZone.TOP
    assert mapping.entries[0].group_name == "Yard Arches"
    assert mapping.entries[0].model_names == []
    assert mapping.entries[1].group_name is None
    assert mapping.entries[1].model_names == ["Mega Tree"]
    assert mapping.resolve("YARD_ARCHES") == ["Yard Arches"]
    assert mapping.resolve("MEGA_TREE") == ["Mega Tree"]


def test_two_layouts_produce_different_graphs_and_mappings() -> None:
    graph_a, mapping_a = layout_to_choreography(load_layout(FIXTURES / "display_layout_a.xml"))
    graph_b, mapping_b = layout_to_choreography(load_layout(FIXTURES / "display_layout_b.xml"))

    assert graph_a != graph_b
    assert mapping_a != mapping_b
    assert [group.id for group in graph_b.groups] == ["WINDOWS", "ROOF_ACCENTS"]


def test_adapter_rejects_layout_without_targetable_models() -> None:
    try:
        layout_to_choreography(Layout())
    except ValueError as error:
        assert "no targetable models" in str(error)
    else:
        raise AssertionError("empty layouts must not reach the planner")


def test_recursive_membership_is_strict_and_ids_are_collision_safe() -> None:
    layout = Layout(
        models=Models(
            model=[
                Model(name="A", DisplayAs="Arches"),
                Model(name="B", DisplayAs="Star"),
                Model(name="roof star", DisplayAs="Star", Active="0"),
            ]
        ),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="Roof Star", models="A"),
                ModelGroup(name="Roof-Star", models="Roof Star,B"),
            ]
        ),
    )
    graph, mapping = layout_to_choreography(layout)

    assert [group.id for group in graph.groups] == ["ROOF_STAR", "ROOF_STAR_2"]
    assert graph.groups[1].element_kind is DisplayElementKind.GROUP
    assert graph.groups[0].pixel_fraction == pytest.approx(0.5)
    assert graph.groups[1].pixel_fraction == pytest.approx(1.0)
    assert mapping.resolve("ROOF_STAR_2") == ["Roof-Star"]
    assert all("roof star" not in entry.model_names for entry in mapping.entries)


def test_known_inactive_group_member_is_omitted_but_group_remains_targetable() -> None:
    layout = Layout(
        models=Models(
            model=[
                Model(name="Active", DisplayAs="Arches"),
                Model(name="Inactive", DisplayAs="Star", Active="0"),
            ]
        ),
        modelGroups=ModelGroups(
            modelGroup=[ModelGroup(name="Mixed Active State", models="Active,Inactive")]
        ),
    )

    graph, mapping = layout_to_choreography(layout)

    assert [group.id for group in graph.groups] == ["MIXED_ACTIVE_STATE"]
    assert graph.groups[0].fixture_count == 1
    assert mapping.resolve("MIXED_ACTIVE_STATE") == ["Mixed Active State"]


def test_unknown_nested_member_is_actionable() -> None:
    layout = Layout(modelGroups=ModelGroups(modelGroup=[ModelGroup(name="Broken", models="Nope")]))
    try:
        layout_to_choreography(layout)
    except ValueError as error:
        assert "Broken" in str(error)
        assert "Nope" in str(error)
    else:
        raise AssertionError("unknown recursive membership must fail")


def test_recursive_membership_cycle_is_actionable() -> None:
    layout = Layout(
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="A", models="B"),
                ModelGroup(name="B", models="A"),
            ]
        )
    )
    try:
        layout_to_choreography(layout)
    except ValueError as error:
        assert "cycle" in str(error)
        assert "A -> B -> A" in str(error)
    else:
        raise AssertionError("membership cycles must fail")


def test_duplicate_active_model_names_are_rejected() -> None:
    layout = Layout(
        models=Models(
            model=[Model(name="Same", DisplayAs="Star"), Model(name="Same", DisplayAs="Arches")]
        )
    )
    with pytest.raises(ValueError, match="duplicate raw model names"):
        layout_to_choreography(layout)


def test_duplicate_model_group_names_are_rejected() -> None:
    layout = Layout(
        models=Models(model=[Model(name="A", DisplayAs="Star")]),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="Same", models="A"),
                ModelGroup(name="Same", models="A"),
            ]
        ),
    )
    with pytest.raises(ValueError, match="duplicate model-group names"):
        layout_to_choreography(layout)


def test_duplicate_inactive_model_names_are_rejected() -> None:
    layout = Layout(
        models=Models(
            model=[
                Model(name="Same", DisplayAs="Star", Active="0"),
                Model(name="Same", DisplayAs="Arches", Active="0"),
            ]
        )
    )
    with pytest.raises(ValueError, match="duplicate raw model names"):
        layout_to_choreography(layout)


def test_model_and_group_raw_name_intersection_is_rejected() -> None:
    layout = Layout(
        models=Models(model=[Model(name="Shared", DisplayAs="Star")]),
        modelGroups=ModelGroups(modelGroup=[ModelGroup(name="Shared", models="Shared")]),
    )
    with pytest.raises(ValueError, match="used by both a model and model group"):
        layout_to_choreography(layout)


def test_layout_written_by_xlights_2026_loads(tmp_path: Path) -> None:
    """xLights 2026 stamps `type="rgb_effects"` on the `models` and `modelGroups`
    containers. Rejecting unknown container attributes made every layout saved by a
    current xLights unloadable, so `twinklr display` could not start."""
    layout_file = tmp_path / "xlights_rgbeffects.xml"
    layout_file.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xrgb>
  <models type="rgb_effects">
    <model name="Arch 1" DisplayAs="Arches" parm1="1" parm2="50" WorldPosX="0" WorldPosY="0"/>
    <model name="Arch 2" DisplayAs="Arches" parm1="1" parm2="50" WorldPosX="50" WorldPosY="0"/>
  </models>
  <modelGroups type="rgb_effects">
    <modelGroup name="61 - Arches" models="Arch 1,Arch 2" LayoutGroup="Default"/>
  </modelGroups>
</xrgb>
""",
        encoding="utf-8",
    )

    layout = load_layout(layout_file)

    assert layout.models is not None
    assert [model.name for model in layout.models.model] == ["Arch 1", "Arch 2"]
    assert layout.modelGroups is not None
    assert layout.modelGroups.modelGroup[0].get_model_list() == ["Arch 1", "Arch 2"]


def _model(name: str, display_as: str = "Single Line", **extra: str) -> Model:
    return Model.model_validate({"name": name, "DisplayAs": display_as, **extra})


def test_dmx_fixtures_and_their_shadow_models_are_not_display_targets() -> None:
    """A pixel effect on a moving head, a fogger, or a model laid over a fixture's
    channels writes arbitrary values to that fixture."""
    layout = Layout(
        models=Models(
            model=[
                _model("Arch 1", "Arches"),
                _model("Dmx MH1", "DmxMovingHeadAdv"),
                _model("Dmx Fogger", "DmxGeneral"),
                _model("DMX MH Pan", StartChannel="@Dmx MH1:11"),
            ]
        ),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="90 - Moving Heads", models="Dmx MH1"),
                ModelGroup(name="Everything", models="Arch 1,Dmx MH1,Dmx Fogger"),
            ]
        ),
    )

    graph, mapping = layout_to_choreography(layout)

    assert [group.id for group in graph.groups] == ["EVERYTHING"]
    assert graph.groups[0].fixture_count == 1
    assert not mapping.has_entry("DMX_MH_PAN")


def test_zone_targets_resolve_to_a_real_layout_group() -> None:
    """A plan that targets the YARD zone used to emit an element literally named
    "YARD", which no layout contains."""
    layout = Layout(
        models=Models(
            model=[_model("Arch 1", "Arches"), _model("Arch 2", "Arches"), _model("Stake 1")]
        ),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="61 - Arches", models="Arch 1,Arch 2"),
                ModelGroup(name="14 - ALL Yard", models="Arch 1,Arch 2,Stake 1"),
                ModelGroup(name="14z - ALL Yard (Background)", models="Arch 1,Arch 2,Stake 1"),
            ]
        ),
    )

    _, mapping = layout_to_choreography(layout)

    assert mapping.resolve("YARD") == ["14 - ALL Yard"]


def test_a_named_fixture_group_keeps_its_dmx_members() -> None:
    """The combined show hands the dedicated moving-head group to the moving-head
    renderer, so that one group stays in the graph."""
    layout = Layout(
        models=Models(model=[_model("Arch 1", "Arches"), _model("Dmx MH1", "DmxMovingHeadAdv")]),
        modelGroups=ModelGroups(
            modelGroup=[
                ModelGroup(name="90 - Moving Heads", models="Dmx MH1"),
                ModelGroup(name="90b - Moving Heads Left", models="Dmx MH1"),
            ]
        ),
    )

    graph, mapping = layout_to_choreography(layout, fixture_groups=frozenset({"90 - Moving Heads"}))

    assert [group.id for group in graph.groups] == ["GROUP_90_MOVING_HEADS", "ARCH_1"]
    assert mapping.resolve("GROUP_90_MOVING_HEADS") == ["90 - Moving Heads"]
