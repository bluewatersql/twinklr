"""Tests for template context building for LLM choreography planning.

These tests verify that template context is built correctly for the new
template-driven LLM paradigm where the LLM selects template_id + preset_id.
"""


from blinkb0t.core.sequencer.moving_heads.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
    PhaseOffsetMode,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplatePreset,
    TemplateStep,
)


def create_test_template_doc() -> TemplateDoc:
    """Create a test TemplateDoc for testing."""
    template = Template(
        template_id="fan_pulse",
        version=1,
        name="Fan Pulse",
        category="movement",
        roles=["FRONT_LEFT", "FRONT_RIGHT"],
        groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
        repeat=RepeatContract(
            repeatable=True,
            mode=RepeatMode.PING_PONG,
            cycle_bars=4.0,
            loop_step_ids=["main"],
        ),
        defaults={"intensity": "SMOOTH"},
        steps=[
            TemplateStep(
                step_id="main",
                target="all",
                timing=StepTiming(
                    base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
                    phase_offset=PhaseOffset(
                        mode=PhaseOffsetMode.GROUP_ORDER,
                        group="all",
                        spread_bars=0.5,
                    ),
                ),
                geometry=Geometry(
                    geometry_id="ROLE_POSE",
                    pan_pose_by_role={"FRONT_LEFT": "LEFT", "FRONT_RIGHT": "RIGHT"},
                ),
                movement=Movement(movement_id="SWEEP_LR", intensity="SMOOTH", cycles=2.0),
                dimmer=Dimmer(dimmer_id="PULSE", min_norm=0.2, max_norm=1.0, cycles=4.0),
            )
        ],
        metadata=TemplateMetadata(
            tags=["energetic", "sweep", "chase"],
            energy_range=(60, 100),
            description="Fan formation with left-right sweep and pulsing dimmer",
        ),
    )
    presets = [
        TemplatePreset(
            preset_id="CHILL",
            name="Chill",
            defaults={"intensity": "SLOW"},
            step_patches={},
        ),
        TemplatePreset(
            preset_id="PEAK",
            name="Peak Energy",
            defaults={"intensity": "FAST"},
            step_patches={},
        ),
    ]
    return TemplateDoc(template=template, presets=presets)


class TestBuildTemplateContextForLLM:
    """Test cases for build_template_context_for_llm function."""

    def test_builds_context_from_single_template(self) -> None:
        """Test building context from a single template doc."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])

        assert len(context) == 1
        entry = context[0]

        # Core identifiers
        assert entry["template_id"] == "fan_pulse"
        assert entry["name"] == "Fan Pulse"
        assert entry["category"] == "movement"

    def test_includes_template_metadata(self) -> None:
        """Test that metadata (description, tags, energy_range) is included."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])
        entry = context[0]

        assert entry["description"] == "Fan formation with left-right sweep and pulsing dimmer"
        assert entry["energy_range"] == (60, 100)
        assert "energetic" in entry["tags"]

    def test_includes_presets(self) -> None:
        """Test that presets are included with their IDs and names."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])
        entry = context[0]

        assert "presets" in entry
        presets = entry["presets"]
        assert len(presets) == 2

        preset_ids = [p["preset_id"] for p in presets]
        assert "CHILL" in preset_ids
        assert "PEAK" in preset_ids

    def test_includes_pattern_summary(self) -> None:
        """Test that pattern/behavior summary is included for LLM reasoning."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])
        entry = context[0]

        # Should include movement and dimmer patterns for choreography reasoning
        assert "movement_patterns" in entry or "patterns" in entry or "behavior" in entry

    def test_handles_multiple_templates(self) -> None:
        """Test building context from multiple template docs."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        # Create two different template docs
        doc1 = create_test_template_doc()

        # Create second template with different ID
        template2 = Template(
            template_id="static_hold",
            version=1,
            name="Static Hold",
            category="static",
            roles=["FRONT_LEFT"],
            groups={"all": ["FRONT_LEFT"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["main"]),
            steps=[
                TemplateStep(
                    step_id="main",
                    target="all",
                    timing=StepTiming(
                        base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0)
                    ),
                    geometry=Geometry(geometry_id="ROLE_POSE"),
                    movement=Movement(movement_id="HOLD"),
                    dimmer=Dimmer(dimmer_id="CONSTANT"),
                )
            ],
        )
        doc2 = TemplateDoc(template=template2, presets=[])

        context = build_template_context_for_llm([doc1, doc2])

        assert len(context) == 2
        template_ids = [c["template_id"] for c in context]
        assert "fan_pulse" in template_ids
        assert "static_hold" in template_ids

    def test_handles_template_without_presets(self) -> None:
        """Test handling templates that have no presets."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template = Template(
            template_id="simple_template",
            version=1,
            name="Simple",
            category="simple",
            roles=["FRONT_LEFT"],
            groups={"all": ["FRONT_LEFT"]},
            repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["main"]),
            steps=[
                TemplateStep(
                    step_id="main",
                    target="all",
                    timing=StepTiming(
                        base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0)
                    ),
                    geometry=Geometry(geometry_id="ROLE_POSE"),
                    movement=Movement(movement_id="HOLD"),
                    dimmer=Dimmer(dimmer_id="CONSTANT"),
                )
            ],
        )
        doc = TemplateDoc(template=template, presets=[])

        context = build_template_context_for_llm([doc])
        entry = context[0]

        assert entry["presets"] == []

    def test_handles_empty_template_list(self) -> None:
        """Test handling empty template list."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        context = build_template_context_for_llm([])
        assert context == []


class TestTemplateContextCompactness:
    """Test that template context is compact for token efficiency."""

    def test_context_excludes_step_details(self) -> None:
        """Test that detailed step data is excluded (not needed for selection)."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])
        entry = context[0]

        # Should NOT include full step details (LLM doesn't need them for selection)
        assert "steps" not in entry or len(str(entry.get("steps", []))) < 200

    def test_context_excludes_group_definitions(self) -> None:
        """Test that full group definitions are excluded."""
        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])
        entry = context[0]

        # Should NOT include full group definitions
        assert "groups" not in entry

    def test_context_is_json_serializable(self) -> None:
        """Test that context is JSON serializable."""
        import json

        from blinkb0t.core.agents.moving_heads.context import build_template_context_for_llm

        template_doc = create_test_template_doc()
        context = build_template_context_for_llm([template_doc])

        # Should not raise
        json_str = json.dumps(context)
        assert len(json_str) > 0


class TestContextShaperWithNewTemplates:
    """Test ContextShaper integration with new template format."""

    def test_shape_for_plan_includes_new_template_format(self) -> None:
        """Test that shape_for_plan works with new template context format."""
        # This test verifies integration - actual implementation may vary
        # TODO: Add integration test when ContextShaper is updated
