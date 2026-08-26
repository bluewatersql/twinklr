"""Rendered-output coverage for every runtime agent prompt pack."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

import pytest

from twinklr.core.agents.prompts import PromptPackLoader
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict

AGENT_ROOT = Path(__file__).parents[4] / "packages" / "twinklr" / "core" / "agents"


def _audio_profile() -> dict[str, Any]:
    section = {
        "section_id": "chorus_1",
        "name": "chorus",
        "type": "chorus",
        "start_ms": 0,
        "end_ms": 8_000,
        "duration_ms": 8_000,
        "confidence": 0.94,
        "characteristics": ["building", "peak"],
        "energy_curve": [
            {"t_ms": 0, "energy": 0.62},
            {"t_ms": 8_000, "energy": 0.91},
        ],
    }
    return {
        "song_identity": {
            "title": "Populated Context Song",
            "artist": "Test Artist",
            "duration_ms": 8_000,
            "bpm": 128.0,
            "key": "C major",
            "time_signature": "4/4",
        },
        "structure": {"sections": [section]},
        "energy_profile": {
            "macro_energy": {"value": "HIGH"},
            "peaks": [{"start_ms": 6_000, "end_ms": 7_000, "energy": 0.91}],
        },
        "creative_guidance": {
            "recommended_layer_count": 2,
            "recommended_motion_density": {"value": "BUSY"},
            "recommended_contrast": {"value": "HIGH"},
            "palette_color_guidance": ["cool blue", "white accent"],
            "cautions": ["Preserve headroom for the final hit at 7.0 seconds."],
        },
        "planner_hints": {
            "section_objectives": [
                {
                    "section_id": "chorus_1",
                    "objectives": ["Use broad motion for the hook at 6.0 seconds."],
                }
            ],
            "avoid_patterns": ["Do not repeat the intro look."],
            "emphasize_groups": ["front"],
        },
    }


def _lyric_context() -> dict[str, Any]:
    return {
        "has_lyrics": True,
        "has_narrative": True,
        "characters": ["winter traveler"],
        "themes": ["returning home", "celebration"],
        "genre_markers": ["holiday pop"],
        "mood_arc": "Longing grows into celebration.",
        "recommended_visual_themes": ["Blue snowfall becoming warm white"],
        "key_phrases": [
            {
                "text": "light the way home",
                "timestamp_ms": 6_000,
                "section_id": "chorus_1",
                "visual_hint": "Open a white fan from center on home.",
                "emphasis": "HIGH",
            }
        ],
        "story_beats": [
            {
                "beat_type": "climax",
                "description": "The traveler sees home.",
                "visual_opportunity": "Reveal the full display.",
                "timestamp_range": [6_000, 7_000],
                "section_id": "chorus_1",
            }
        ],
        "silent_sections": [
            {"start_ms": 0, "end_ms": 500, "duration_ms": 500, "section_id": "chorus_1"}
        ],
        "lyric_density": "MED",
        "vocal_coverage_pct": 0.82,
        "timed_word_coverage_pct": 0.91,
        "moment_cues": [
            {
                "cue_id": "chorus-home",
                "timestamp_ms": 6_000,
                "section_id": "chorus_1",
                "emphasis": "HIGH",
                "text": "light the way home",
                "visual_hint": "Open a white fan from center on home.",
            }
        ],
    }


def _macro_plan() -> dict[str, Any]:
    section_ref = {
        "section_id": "chorus_1",
        "name": "chorus",
        "start_ms": 0,
        "end_ms": 8_000,
    }
    return {
        "sections": [
            {
                "section": section_ref,
                "energy_target": {"value": "HIGH"},
                "motion_density": {"value": "BUSY"},
                "choreography_style": {"value": "HYBRID"},
                "palette_role": {"stop_id": "winter", "override": None},
                "theme": {
                    "theme_id": "theme.winter",
                    "scope": {"value": "SECTION"},
                    "tags": ["snow"],
                    "palette_id": "core.winter",
                },
                "motif_ids": ["snowfall"],
                "focal_roles": [
                    {
                        "target": {"type": {"value": "group"}, "id": "front"},
                        "role": {"value": "LEAD"},
                    },
                    {
                        "target": {"type": {"value": "zone"}, "id": "house"},
                        "role": {"value": "SUPPORT"},
                    },
                ],
                "call_response_pairs": [],
                "coordination_intent": {"value": "UNIFIED"},
                "notes": "Open wide at the hook.",
            }
        ],
        "palette_arc": [
            {
                "stop_id": "winter",
                "palette": {"palette_id": "core.winter"},
                "applies_from_section_id": "chorus_1",
                "transition": {"value": "HOLD"},
            }
        ],
        "motif_continuity": [
            {
                "motif_id": "snowfall",
                "section_ids": ["chorus_1"],
                "evolution": {"value": "INTRODUCE"},
                "description": "Snowfall grows toward the hook.",
            }
        ],
        "focal_arc": [
            {
                "section_id": "chorus_1",
                "lead_target": {"type": {"value": "group"}, "id": "front"},
            }
        ],
    }


def _display_graph() -> dict[str, Any]:
    group = {
        "id": "front",
        "role": "HERO",
        "fixture_count": 4,
        "model_count": 4,
        "detail_capability": "HIGH",
        "tags": ["house"],
        "split_membership": ["left"],
        "position": {"horizontal": "CENTER", "vertical": "MID", "depth": "NEAR", "zone": "house"},
        "arrangement": "fan",
        "element_kind": "moving_head",
        "pixel_fraction": 0.8,
        "prominence": "hero",
    }
    return {
        "groups": [group],
        "groups_by_role": {"HERO": ["front"]},
        "groups_by_split": {"left": ["front"]},
        "groups_by_tag": {"house": ["front"]},
    }


def _catalogs() -> dict[str, Any]:
    template = {
        "template_id": "gtpl_rhythm_wave",
        "name": "Wave",
        "compatible_lanes": [{"value": "RHYTHM"}],
        "affinity_tags": ["snowfall"],
        "tags": ["wide"],
        "role": "motion",
        "detail": "A broad wave.",
        "position": "full",
    }
    return {
        "template_catalog": {"entries": [template]},
        "template_catalog_full": {
            "entries": [template, {**template, "template_id": "gtpl_base_glow"}]
        },
        "palette_catalog": [
            {"id": "core.winter", "title": "Winter", "description": "Cool blue and white."}
        ],
        "motif_catalog": [{"id": "snowfall", "description": "Falling snow.", "energy": "medium"}],
        "theme_catalog": [{"theme_id": "theme.winter", "title": "Winter Homecoming"}],
    }


def _base_variables() -> dict[str, Any]:
    catalogs = _catalogs()
    profile = _audio_profile()
    lyrics = _lyric_context()
    macro = _macro_plan()
    graph = _display_graph()
    return {
        "response_schema": '{"type":"object"}',
        "taxonomy": get_taxonomy_dict(),
        "iteration": 0,
        "learning_context": "Preserve readable focal hierarchy.",
        "feedback": "Keep the hook broad and resolve prior timing feedback.",
        "revision_request": {
            "priority": "high",
            "focus_areas": ["timing"],
            "specific_fixes": ["Move the hit to bar 4."],
            "avoid": ["template thrash"],
        },
        "audio_profile": profile,
        "lyric_context": lyrics,
        "macro_plan": macro,
        "display_groups": graph["groups"],
        "display_graph": graph,
        "available_zone_ids": ["house"],
        "available_split_ids": ["left"],
        **catalogs,
    }


def _pack_cases() -> list[tuple[str, Path, str, dict[str, Any]]]:
    base = _base_variables()
    asset = {
        "response_schema": base["response_schema"],
        "background": "transparent",
        "builtin_prompt": "A traveler carrying a lantern.",
        "category": "image_cutout",
        "color_guidance": "Use cool blue with a white lantern.",
        "content_tags": ["traveler", "lantern"],
        "height": 512,
        "mood": "hopeful",
        "motif_description": "A snowfall motif.",
        "motif_id": "snowfall",
        "motif_usage_notes": "Frame the traveler.",
        "narrative_description": "A winter traveler approaches home.",
        "narrative_subject": "winter traveler",
        "palette_colors": [{"name": "ice blue", "hex": "#77AAFF"}],
        "palette_id": "core.winter",
        "scene_context": ["Snow falls behind the traveler."],
        "song_title": "Populated Context Song",
        "story_context": "The traveler sees home.",
        "style_tags": ["bold", "clean"],
        "target_roles": ["hero"],
        "theme_id": "theme.winter",
        "width": 512,
    }
    lyrics = {
        "response_schema": base["response_schema"],
        "duration_ms": 8_000,
        "has_lyrics": True,
        "text": "Light the way home",
        "words": [{"text": "Light", "start_ms": 6_000}],
        "phrases": [{"text": "Light the way home", "start_ms": 6_000, "end_ms": 7_000}],
        "sections": [{"section_id": "chorus_1", "name": "chorus", "start_ms": 0, "end_ms": 8_000}],
        "quality": {
            "source_kind": "aligned",
            "source_confidence": 0.95,
            "vocal_presence_pct": 0.82,
            "timed_word_coverage_pct": 0.91,
        },
    }
    audio_profile = {
        "response_schema": base["response_schema"],
        "shaped_context": {
            "audio_path": "fixtures/song.wav",
            "duration_ms": 8_000,
            "tempo": {"bpm": 128.0, "confidence": 0.96, "time_signature": "4/4"},
            "key": {"key": "C", "mode": "major", "confidence": 0.91},
            "sections": base["audio_profile"]["structure"]["sections"],
            "energy": {
                "overall": 0.76,
                "peaks": [{"start_ms": 6_000, "end_ms": 7_000, "energy": 0.91}],
                "section_profiles": [
                    {
                        **base["audio_profile"]["structure"]["sections"][0],
                        "mean_energy": 0.72,
                        "peak_energy": 0.91,
                    }
                ],
            },
            "lyrics": {"has_plain_lyrics": True, "has_timed_words": True, "lyric_confidence": 0.95},
            "phonemes": {"available": True, "confidence": 0.88},
        },
    }
    group_planner = {
        **deepcopy(base),
        "arc_keyframe": {"contrast": "high", "saturation": "cool", "temperature": "cold"},
        "available_bars": 4,
        "choreography_style": "HYBRID",
        "color_arc": {
            "contrast_target": "high",
            "palette_id": "core.winter",
            "shift_timing": "bar 4",
        },
        "color_narrative_row": {
            "contrast_shift_from_prev": "increase",
            "dominant_color_class": "cool",
            "hue_family_movement": "blue to white",
        },
        "display_graph_spatial": {
            "horizontal": [{"id": "front", "position": "center", "role": "hero", "detail": "high"}]
        },
        "display_graph_splits": {"left": ["front"]},
        "display_graph_zones": [{"zone": "house", "group_ids": ["front"]}],
        "end_ms": 8_000,
        "energy_target": "HIGH",
        "motif_catalog_summary": "snowfall: Falling snow.",
        "motif_ids": ["snowfall"],
        "macro_input": {
            "macro_section": {
                "coordination_intent": "CALL_RESPONSE",
                "call_response_pairs": [
                    {
                        "call": {"type": "group", "id": "front"},
                        "response": {"type": "zone", "id": "house"},
                        "step_unit": "BEAT",
                        "step_duration": 1,
                    }
                ],
            },
            "palette_stop": {
                "stop_id": "winter",
                "applies_from_section_id": "chorus_1",
                "transition": "CROSSFADE",
            },
            "resolved_palette": {"palette_id": "core.winter", "role": "PRIMARY"},
            "motif_threads": [
                {
                    "motif_id": "snowfall",
                    "section_ids": ["chorus_1"],
                    "evolution": "INTRODUCE",
                    "description": "Snowfall grows toward the hook.",
                }
            ],
            "focal_assignment": {
                "section_id": "chorus_1",
                "lead_target": {"type": "group", "id": "front"},
            },
        },
        "motion_density": "BUSY",
        "notes": "Open wide at the hook.",
        "palette_ref_json": '{"palette_id":"core.winter"}',
        "lead_targets": ["front"],
        "propensity_hints": {
            "affinities": [{"effect_family": "wave", "frequency": 3, "model_type": "moving_head"}]
        },
        "recipe_catalog": {
            "entries": [
                {
                    "recipe_id": "recipe.wave",
                    "name": "Wave Stack",
                    "template_type": "layered",
                    "layer_count": 2,
                    "composition": "foundation plus wave",
                    "model_affinities": [{"model_type": "moving_head", "score": 0.9}],
                }
            ]
        },
        "support_targets": ["house"],
        "section_duration_bars": 4,
        "section_duration_beats": 16,
        "section_id": "chorus_1",
        "section_max_bar": 4,
        "section_name": "chorus",
        "start_ms": 0,
        "style_constraints": {
            "recipe_preferences": {"wave": 0.9},
            "color_tendencies": {
                "contrast_preference": "high",
                "palette_complexity": "simple",
                "temperature_preference": "cool",
            },
            "layering_style": {
                "blend_mode_preference": "normal",
                "max_layers": 3,
                "mean_layers": 2,
            },
            "timing_style": {"beat_alignment_strictness": "strict", "density_preference": "active"},
            "transition_style": {
                "overlap_tendency": "low",
                "preferred_gap_ms": 0,
                "variety_score": 0.8,
            },
        },
        "theme_ref": {"theme_id": "theme.winter", "scope": "SECTION", "tags": ["snow"]},
        "theme_ref_json": '{"theme_id":"theme.winter","scope":"SECTION","tags":["snow"]}',
    }
    section_judge = {
        **deepcopy(group_planner),
        "iteration": 1,
        "plan": {
            "section_id": "chorus_1",
            "theme": {"theme_id": "theme.winter", "scope": "SECTION", "tags": ["snow"]},
            "palette": {"palette_id": "core.winter"},
            "motif_ids": ["snowfall"],
            "lane_plans": [],
        },
        "priority_roles": ["hero"],
    }
    holistic = {
        **deepcopy(base),
        "completeness_check": {
            "status": "PASSED",
            "expected_count": 1,
            "present_count": 1,
            "missing": [],
            "extra": [],
            "reason": "All sections present.",
        },
        "global_palette_alternates": ["core.peppermint"],
        "global_palette_id": "core.winter",
        "global_palette_primary": "#77AAFF",
        "global_theme_id": "theme.winter",
        "global_theme_tags": ["snow"],
        "group_hierarchy": {"front": ["left_head", "right_head"]},
        "group_plan_set": {"plan_set_id": "show-1", "section_plans": []},
        "macro_plan_summary": {
            "macro_plan": deepcopy(base["macro_plan"]),
            "expected_section_ids": ["chorus_1"],
        },
        "macro_palette_arc": deepcopy(base["macro_plan"]["palette_arc"]),
        "macro_motif_continuity": deepcopy(base["macro_plan"]["motif_continuity"]),
        "macro_focal_arc": deepcopy(base["macro_plan"]["focal_arc"]),
        "section_count": 1,
        "section_ids": ["chorus_1"],
        "section_theme_summary": [
            {
                "section_id": "chorus_1",
                "theme_id": "theme.winter",
                "scope": "SECTION",
                "tags": ["snow"],
                "palette_id": "core.winter",
                "motif_ids": ["snowfall"],
            }
        ],
        "story_notes": "The traveler reaches home.",
    }
    corrector = {
        **deepcopy(base),
        "actionable_issues": [
            {
                "issue_id": "timing_1",
                "severity": "WARN",
                "description": "Move the hit.",
                "recommendation": "Align it to bar 4.",
                "targeted_actions": [
                    {
                        "action_type": "ADJUST_TIMING",
                        "section_id": "chorus_1",
                        "description": "Move hit to bar 4.",
                        "lane": "ACCENT",
                        "target": "front",
                        "template_id": "gtpl_rhythm_wave",
                        "replacement_template_id": None,
                        "palette_id": None,
                        "bar": 4,
                        "beat": 1,
                    }
                ],
            }
        ],
        "affected_sections_json": '{"chorus_1": {"section_id": "chorus_1"}}',
        "holistic_evaluation": {
            "score": 6.8,
            "status": "SOFT_FAIL",
            "summary": "One timing fix remains.",
        },
        "section_summaries": [
            {
                "section_id": "chorus_1",
                "theme": {"theme_id": "theme.winter"},
                "palette": {"palette_id": "core.winter"},
                "motif_ids": ["snowfall"],
                "template_ids_by_lane": {"accent": ["gtpl_rhythm_wave"]},
            }
        ],
        "strengths": ["Clear hook focus."],
    }
    moving = {
        **deepcopy(base),
        "available_templates": ["template-with-join-key"],
        "fixture_count": 4,
        "fixture_groups": [{"group_id": "front", "fixture_count": 4}],
        "genre": ["pop", "holiday"],
        "macro_plan": [
            {
                "section_id": "chorus_1",
                "energy_target": "HIGH",
                "motion_density": "BUSY",
                "choreography_style": "ABSTRACT",
                "palette_id": "core.holiday",
                "motif_ids": ["hook"],
                "coordination_intent": "UNIFIED",
                "notes": "Keep movement expansive.",
            }
        ],
        "macro_palette_arc": deepcopy(base["macro_plan"]["palette_arc"]),
        "macro_motif_continuity": deepcopy(base["macro_plan"]["motif_continuity"]),
        "macro_focal_arc": deepcopy(base["macro_plan"]["focal_arc"]),
        "plan": {"sections": [], "overall_strategy": "Build to the hook."},
        "preserve_elements": ["Broad hook sweep"],
        "previous_feedback": ["Keep the hook broad."],
        "previous_issues": [
            {"issue_id": "timing_1", "message": "Move the hit.", "severity": "WARN"}
        ],
        "revision_focus": ["timing"],
        "sections": [{"section_id": "chorus_1", "name": "chorus", "start_bar": 1, "end_bar": 8}],
        "song_artist": "Test Artist",
        "song_title": "Populated Context Song",
        "template_descriptions": [
            {
                "template_id": "template-with-join-key",
                "name": "Join Key Template",
                "description": "A populated template description.",
                "energy_range": [60, 90],
                "tags": ["wide", "chorus"],
                "recommended_sections": ["chorus", "drop"],
            }
        ],
        "tempo": 128.0,
        "time_signature": "4/4",
        "total_bars": 8,
    }
    show_vision = {
        "capability": '{"has_display":true,"has_moving_heads":true,"cross_part_applicable":true}',
        "claims_json": (
            '{"focal_arc":[{"section_id":"chorus_1","lead_target":"front"}],'
            '"sections":[{"section_id":"chorus_1"}]}'
        ),
        "trace_summary_json": ('{"display":{"entry_count":4},"moving_head":{"entry_count":4}}'),
        "frame_manifest": "Frame 1: 0 ms\nFrame 2: 6000 ms",
    }
    return [
        (
            "asset_prompt_enricher",
            AGENT_ROOT / "assets" / "prompts",
            "asset_prompt_enricher",
            asset,
        ),
        ("lyrics", AGENT_ROOT / "audio" / "lyrics" / "prompts", "lyrics", lyrics),
        (
            "audio_profile",
            AGENT_ROOT / "audio" / "profile" / "prompts",
            "audio_profile",
            audio_profile,
        ),
        (
            "group_planner",
            AGENT_ROOT / "sequencer" / "group_planner" / "prompts",
            "planner",
            group_planner,
        ),
        (
            "section_judge",
            AGENT_ROOT / "sequencer" / "group_planner" / "prompts",
            "section_judge",
            section_judge,
        ),
        (
            "holistic_judge",
            AGENT_ROOT / "sequencer" / "group_planner" / "prompts",
            "holistic_judge",
            holistic,
        ),
        (
            "holistic_corrector",
            AGENT_ROOT / "sequencer" / "group_planner" / "prompts",
            "holistic_corrector",
            corrector,
        ),
        ("macro_planner", AGENT_ROOT / "sequencer" / "macro_planner" / "prompts", "planner", base),
        ("macro_judge", AGENT_ROOT / "sequencer" / "macro_planner" / "prompts", "judge", base),
        (
            "moving_head_planner",
            AGENT_ROOT / "sequencer" / "moving_heads" / "prompts",
            "planner",
            moving,
        ),
        (
            "moving_head_judge",
            AGENT_ROOT / "sequencer" / "moving_heads" / "prompts",
            "judge",
            moving,
        ),
        (
            "show_vision_judge",
            AGENT_ROOT / "prompts",
            "show_vision_judge",
            show_vision,
        ),
    ]


@pytest.mark.parametrize(("case_id", "base_path", "pack_name", "variables"), _pack_cases())
def test_every_pack_renders_against_populated_context(
    case_id: str,
    base_path: Path,
    pack_name: str,
    variables: dict[str, Any],
) -> None:
    """Render every runtime pack with non-empty branches and strict undefineds."""
    rendered = PromptPackLoader(base_path=base_path).load_and_render(pack_name, variables)

    assert rendered["system"].strip(), case_id
    assert rendered["user"].strip(), case_id
    if (base_path / pack_name / "developer.j2").exists():
        assert rendered["developer"].strip(), case_id
    if case_id == "moving_head_planner":
        assert "Recommended sections: chorus, drop" in rendered["user"]
        assert "Use broad motion for the hook" in rendered["user"]
        assert "Longing grows into celebration." in rendered["user"]
        assert "light the way home" in rendered["user"]
        assert "chorus-home" in rendered["user"]


def test_phantom_lyric_fields_are_absent_from_runtime_tree() -> None:
    """Pin the exact silent Jinja typo class without matching this test itself."""
    repository = Path(__file__).parents[4]
    forbidden = ("narrative" + "_arc", "key" + "_moments")
    matches: list[str] = []
    for root in (repository / "packages", repository / "tests"):
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".j2"}:
                continue
            if any(name in path.read_text() for name in forbidden):
                matches.append(str(path.relative_to(repository)))
    assert matches == []


def test_all_refinement_templates_render_with_populated_context() -> None:
    """Exercise every runtime refinement branch, not only initial user templates."""
    cases = {case_id: (path, pack, variables) for case_id, path, pack, variables in _pack_cases()}
    for case_id in ("group_planner", "macro_planner", "moving_head_planner"):
        path, pack, variables = cases[case_id]
        refinement_variables = deepcopy(variables)
        refinement_variables["iteration"] = 1
        rendered = PromptPackLoader(base_path=path).load_and_render(pack, refinement_variables)
        expected_heading = (
            "Revise the Typed MacroPlan" if case_id == "macro_planner" else "Refinement Request"
        )
        assert expected_heading in rendered["user"], case_id


def test_populated_matrix_covers_every_runtime_pack() -> None:
    """Keep the populated-context matrix exhaustive as runtime packs evolve."""
    covered = {(base_path / pack_name).resolve() for _, base_path, pack_name, _ in _pack_cases()}
    discovered = {
        system_prompt.parent.resolve()
        for system_prompt in AGENT_ROOT.glob("**/prompts/*/system.j2")
    }

    assert len(discovered) == 12
    assert covered == discovered


def test_deleted_prompt_contracts_and_literal_enum_fallbacks_do_not_return() -> None:
    """Guard deleted solicitations and the known hand-authored fallback drift sites."""
    prompt_text = "\n".join(
        path.read_text() for path in sorted(AGENT_ROOT.glob("**/prompts/**/*.j2"))
    ).lower()
    forbidden = (
        "asset usage",
        "recommended_asset_usage",
        "estimated_effort",
        "issueeffort",
        "issuescope",
        "suggestedaction",
        "score breakdown",
        "score_breakdown",
        "overall_assessment",
        "lanekind:** base, rhythm, accent",
        "coordinationmode:** unified",
        "intensitylevel:** whisper",
        "effectduration:** hit",
        "targettype:** group, zone, split",
    )
    assert not [fragment for fragment in forbidden if fragment in prompt_text]

    # Dynamic schema/taxonomy expressions are the only place a prompt may enumerate
    # response enum values. Normal musical words that also happen to be enum values are
    # excluded; two or more remaining values on a literal line is an authored list.
    ambiguous_prose_values = {"AND", "bars", "beats", "end", "start"}
    enum_values = {
        value
        for values in get_taxonomy_dict().values()
        for value in values
        if value not in ambiguous_prose_values
    }
    literal_lists: list[str] = []
    for prompt_path in sorted(AGENT_ROOT.glob("**/prompts/**/*.j2")):
        for line_number, line in enumerate(prompt_path.read_text().splitlines(), 1):
            if "taxonomy." in line or line.lstrip().startswith("{%"):  # injected or control
                continue
            matches = {
                value
                for value in enum_values
                if re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])",
                    line,
                )
            }
            if len(matches) >= 2:
                literal_lists.append(f"{prompt_path}:{line_number}: {sorted(matches)}")
    assert literal_lists == []
