from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module():
    repo_root = Path(__file__).resolve().parents[4]
    module_path = repo_root / "scripts" / "validation" / "validate_artifacts.py"
    spec = importlib.util.spec_from_file_location("validate_artifacts", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_detect_pipeline_from_display_group_plan_set() -> None:
    module = _load_module()

    pipeline = module.detect_pipeline_from_json(
        {
            "schema_version": "group-plan-set.v1",
            "section_plans": [],
        }
    )

    assert pipeline == "display"


def test_detect_pipeline_from_mh_plan_shape() -> None:
    module = _load_module()

    pipeline = module.detect_pipeline_from_json(
        {
            "sections": [
                {"name": "Intro", "start_ms": 0, "end_ms": 1000, "template_id": "tmpl_1"},
            ]
        }
    )

    assert pipeline == "mh"


def test_resolve_sequence_paths_for_display() -> None:
    module = _load_module()
    repo_root = Path("/repo")

    paths = module.resolve_sequence_paths(repo_root=repo_root, sequence_name="11_need_a_favor")

    assert paths["display"]["plan"] == repo_root / "artifacts/11_need_a_favor/group_plan_set.json"
    assert paths["display"]["evaluation"] == (
        repo_root / "artifacts/11_need_a_favor/holistic_evaluation.json"
    )
    assert paths["display"]["xsq"] == (
        repo_root / "artifacts/11_need_a_favor/11_need_a_favor_display.xsq"
    )


def test_validate_display_plan_structure_reports_missing_section_plans() -> None:
    module = _load_module()

    issues = module.validate_display_plan_structure({"schema_version": "group-plan-set.v1"})

    assert any("section_plans" in issue for issue in issues)


def test_validate_display_plan_structure_flags_duplicate_section_and_lane_ids() -> None:
    module = _load_module()

    issues = module.validate_display_plan_structure(
        {
            "schema_version": "group-plan-set.v1",
            "section_plans": [
                {
                    "section_id": "intro",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "lane_plans": [
                        {"lane": "BASE", "coordination_plans": []},
                        {"lane": "BASE", "coordination_plans": []},
                    ],
                },
                {
                    "section_id": "intro",
                    "start_ms": 1000,
                    "end_ms": 2000,
                    "lane_plans": [],
                },
            ],
        }
    )

    assert any("Duplicate section_id" in issue for issue in issues)
    assert any("duplicate lane" in issue.lower() for issue in issues)


def test_validate_display_plan_structure_flags_section_overlap_and_bad_placement() -> None:
    module = _load_module()

    issues = module.validate_display_plan_structure(
        {
            "schema_version": "group-plan-set.v1",
            "section_plans": [
                {
                    "section_id": "a",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "lane_plans": [
                        {
                            "lane": "BASE",
                            "coordination_plans": [
                                {
                                    "targets": [{"type": "group", "id": "TREE"}],
                                    "placements": [
                                        {
                                            "placement_id": "p1",
                                            "target": {"type": "group", "id": "TREE"},
                                            "start": {"bar": 1, "beat": 1},
                                            "duration": "PHRASE",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "section_id": "b",
                    "start_ms": 900,
                    "end_ms": 1500,
                    "lane_plans": [
                        {
                            "lane": "ACCENT",
                            "coordination_plans": [
                                {
                                    "targets": [{"type": "group", "id": "STAR"}],
                                    "placements": [
                                        {
                                            "placement_id": "p1",
                                            "target": {"type": "group", "id": "OTHER"},
                                            "template_id": "tmpl",
                                            "start": {"bar": 1, "beat": 1},
                                            "duration": "HIT",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    )

    assert any("overlap" in issue.lower() for issue in issues)
    assert any("Missing 'template_id'" in issue for issue in issues)
    assert any("Duplicate placement_id" in issue for issue in issues)
    assert any("not listed in coordination targets" in issue for issue in issues)


def test_validate_display_evaluation_structure_flags_bad_fields() -> None:
    module = _load_module()

    issues = module.validate_display_evaluation_structure(
        {
            "status": "SOFT_FAIL",
            "score": 11,
            "summary": "x",
            "cross_section_issues": [
                {
                    "issue_id": "i1",
                    "severity": "BAD",
                    "affected_sections": "intro",
                    "targeted_actions": [1, "ok"],
                }
            ],
            "recommendations": "not-a-list",
            "score_breakdown": {"story_coherence": 12},
        }
    )

    assert any("score out of range" in issue for issue in issues)
    assert any("recommendations" in issue and "list" in issue for issue in issues)
    assert any("Invalid cross_section issue severity" in issue for issue in issues)
    assert any("affected_sections" in issue and "list" in issue for issue in issues)
    assert any("targeted_actions" in issue for issue in issues)
    assert any("score_breakdown.story_coherence" in issue for issue in issues)


def test_normalize_display_name_matches_common_variants() -> None:
    module = _load_module()

    assert module.normalize_display_name("CANDY_CANES") == module.normalize_display_name(
        "Candy Canes"
    )
    assert module.normalize_display_name("Mega-Tree") == module.normalize_display_name("MEGA_TREE")


def test_validate_display_xsq_target_coverage_flags_missing_target_per_section() -> None:
    module = _load_module()

    effects = [
        module.GenericXSQEffect(
            element_name="Arches",
            layer_index=0,
            effect_name="Meteors",
            start_ms=0,
            end_ms=1000,
            ref=1,
        )
    ]
    plan_set = {
        "section_plans": [
            {
                "section_id": "intro",
                "start_ms": 0,
                "end_ms": 1000,
                "lane_plans": [
                    {
                        "lane": "BASE",
                        "coordination_plans": [
                            {
                                "targets": [{"type": "group", "id": "ARCHES"}],
                                "placements": [
                                    {
                                        "placement_id": "p1",
                                        "template_id": "tmpl",
                                        "target": {"type": "group", "id": "CANDY_CANES"},
                                        "start": {"bar": 1, "beat": 1},
                                        "duration": "PHRASE",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    issues = module.validate_display_xsq_target_coverage(effects, plan_set)

    assert any("CANDY_CANES" in issue for issue in issues)


def test_validate_display_xsq_target_coverage_uses_alias_map() -> None:
    module = _load_module()

    effects = [
        module.GenericXSQEffect(
            element_name="Candy Canes",
            layer_index=0,
            effect_name="Bars",
            start_ms=0,
            end_ms=1000,
            ref=1,
        )
    ]
    plan_set = {
        "section_plans": [
            {
                "section_id": "intro",
                "start_ms": 0,
                "end_ms": 1000,
                "lane_plans": [
                    {
                        "lane": "BASE",
                        "coordination_plans": [
                            {
                                "placements": [
                                    {
                                        "placement_id": "p1",
                                        "template_id": "tmpl",
                                        "target": {"type": "group", "id": "CANDY_STRIPES"},
                                        "start": {"bar": 1, "beat": 1},
                                        "duration": "PHRASE",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }
    alias_map = {"CANDY_STRIPES": ["Candy Canes"]}

    issues = module.validate_display_xsq_target_coverage(effects, plan_set, alias_map=alias_map)

    assert not issues


def test_normalize_display_target_alias_map_accepts_strings_and_lists() -> None:
    module = _load_module()

    normalized = module.normalize_display_target_alias_map(
        {"MEGA_TREE": "Mega Tree", "CANDY_STRIPES": ["Candy Canes", "Arches"]}
    )

    assert module.normalize_display_name("MEGA_TREE") in normalized
    assert (
        module.normalize_display_name("Mega Tree")
        in normalized[module.normalize_display_name("MEGA_TREE")]
    )
    assert (
        module.normalize_display_name("Arches")
        in normalized[module.normalize_display_name("CANDY_STRIPES")]
    )


def test_validate_display_plan_structure_flags_bad_start_shape_and_duration_type() -> None:
    module = _load_module()

    issues = module.validate_display_plan_structure(
        {
            "schema_version": "group-plan-set.v1",
            "section_plans": [
                {
                    "section_id": "intro",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "lane_plans": [
                        {
                            "lane": "BASE",
                            "coordination_plans": [
                                {
                                    "targets": [{"type": "group", "id": "ARCHES"}],
                                    "placements": [
                                        {
                                            "placement_id": "p1",
                                            "template_id": "tmpl",
                                            "target": {"type": "group", "id": "ARCHES"},
                                            "start": {"bar": "1"},
                                            "duration": 1,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    assert any("invalid 'start'" in issue.lower() for issue in issues)
    assert any("invalid 'duration'" in issue.lower() for issue in issues)


def test_cross_validate_display_artifacts_flags_unknown_targeted_action_refs() -> None:
    module = _load_module()

    plan_set = {
        "section_plans": [
            {
                "section_id": "intro",
                "start_ms": 0,
                "end_ms": 1000,
                "lane_plans": [
                    {
                        "lane": "BASE",
                        "coordination_plans": [
                            {
                                "placements": [
                                    {
                                        "placement_id": "existing_placement",
                                        "template_id": "tmpl",
                                        "target": {"type": "group", "id": "ARCHES"},
                                        "start": {"bar": 1, "beat": 1},
                                        "duration": "PHRASE",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }
    evaluation = {
        "cross_section_issues": [
            {
                "issue_id": "i1",
                "affected_sections": ["intro"],
                "targeted_actions": [
                    "In section missing_section, replace placement_id missing_placement with template_id foo."
                ],
            }
        ]
    }

    issues = module.cross_validate_display_artifacts(plan_set, evaluation)

    assert any("missing_section" in issue for issue in issues)
    assert any("missing_placement" in issue for issue in issues)


def test_validate_display_xsq_trace_placement_coverage_flags_missing_and_orphan() -> None:
    module = _load_module()

    plan_set = {
        "section_plans": [
            {
                "section_id": "intro",
                "start_ms": 0,
                "end_ms": 1000,
                "lane_plans": [
                    {
                        "lane": "BASE",
                        "coordination_plans": [
                            {
                                "placements": [
                                    {
                                        "placement_id": "p1",
                                        "template_id": "tmpl_a",
                                        "target": {"type": "group", "id": "ARCHES"},
                                        "start": {"bar": 1, "beat": 1},
                                        "duration": "PHRASE",
                                    },
                                    {
                                        "placement_id": "p2",
                                        "template_id": "tmpl_b",
                                        "target": {"type": "group", "id": "MEGA_TREE"},
                                        "start": {"bar": 1, "beat": 2},
                                        "duration": "PHRASE",
                                    },
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }
    trace_payload = {
        "schema_version": "display-xsq-trace.v1",
        "entries": [
            {
                "placement_id": "p1",
                "section_id": "intro",
                "group_id": "ARCHES",
                "template_id": "tmpl_a",
                "element_name": "Arches",
                "layer_index": 0,
                "effect_name": "Bars",
                "start_ms": 0,
                "end_ms": 900,
            },
            {
                "placement_id": "orphan",
                "section_id": "intro",
                "group_id": "STAR",
                "template_id": "tmpl_x",
                "element_name": "Star",
                "layer_index": 1,
                "effect_name": "On",
                "start_ms": 100,
                "end_ms": 200,
            },
        ],
    }

    issues = module.validate_display_xsq_trace_placement_coverage(plan_set, trace_payload)

    assert any("p2" in issue and "no sidecar trace coverage" in issue for issue in issues)
    assert any("orphan" in issue and "unknown placement_id" in issue for issue in issues)


def test_validate_display_xsq_trace_placement_coverage_uses_alias_map_for_targets() -> None:
    module = _load_module()

    plan_set = {
        "section_plans": [
            {
                "section_id": "intro",
                "start_ms": 0,
                "end_ms": 1000,
                "lane_plans": [
                    {
                        "lane": "BASE",
                        "coordination_plans": [
                            {
                                "placements": [
                                    {
                                        "placement_id": "p1",
                                        "template_id": "tmpl_a",
                                        "target": {"type": "group", "id": "CANDY_STRIPES"},
                                        "start": {"bar": 1, "beat": 1},
                                        "duration": "PHRASE",
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }
    trace_payload = {
        "schema_version": "display-xsq-trace.v1",
        "entries": [
            {
                "placement_id": "p1",
                "section_id": "intro",
                "group_id": "CANDY_STRIPES",
                "template_id": "tmpl_a",
                "element_name": "Candy Canes",
                "layer_index": 0,
                "effect_name": "Bars",
                "start_ms": 0,
                "end_ms": 900,
            }
        ],
    }

    no_alias_issues = module.validate_display_xsq_trace_placement_coverage(plan_set, trace_payload)
    alias_issues = module.validate_display_xsq_trace_placement_coverage(
        plan_set,
        trace_payload,
        alias_map={"CANDY_STRIPES": ["Candy Canes"]},
    )

    assert any("element" in issue.lower() and "CANDY_STRIPES" in issue for issue in no_alias_issues)
    assert not alias_issues
