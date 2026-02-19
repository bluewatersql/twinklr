from __future__ import annotations

from twinklr.core.feature_engineering.models.adapters import (
    GroupPlannerAdapterPayload,
    MacroPlannerAdapterPayload,
    PlannerChangeMode,
    RoleBindingContext,
    SequenceAdapterContext,
    SequencerAdapterBundle,
    SequencerAdapterScope,
    TemplateConstraint,
    TransitionConstraint,
)
from twinklr.core.feature_engineering.models.bundle import AudioStatus
from twinklr.core.feature_engineering.models.templates import TemplateKind
from twinklr.core.feature_engineering.models.transitions import TransitionType


def _sequence_context() -> SequenceAdapterContext:
    return SequenceAdapterContext(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        sequence_name="Song A",
        artist="Artist A",
        sequence_sha256="abc123",
        audio_status=AudioStatus.FOUND_IN_MUSIC_DIR,
    )


def _template_constraint() -> TemplateConstraint:
    return TemplateConstraint(
        template_id="t1",
        template_kind=TemplateKind.CONTENT,
        retrieval_score=0.8,
        support_count=12,
        support_ratio=0.4,
        transition_flow_norm=0.6,
        effect_family="on",
        role="lead",
        motion_class="sweep",
        energy_class="mid",
    )


def _transition_constraint() -> TransitionConstraint:
    return TransitionConstraint(
        source_template_id="t1",
        target_template_id="t2",
        transition_type=TransitionType.HARD_CUT,
        edge_count=5,
    )


def _role_binding() -> RoleBindingContext:
    return RoleBindingContext(
        target_id="target-1",
        target_name="MegaTree",
        role="lead",
        role_confidence=0.9,
    )


def test_macro_and_group_adapter_contracts_are_contract_only() -> None:
    macro = MacroPlannerAdapterPayload(
        schema_version="v2.4.0",
        adapter_version="sequencer_adapter_v1",
        scope=SequencerAdapterScope.MACRO,
        planner_change_mode=PlannerChangeMode.CONTRACT_ONLY,
        sequence=_sequence_context(),
        template_constraints=(_template_constraint(),),
        transition_constraints=(_transition_constraint(),),
        role_bindings=(_role_binding(),),
    )
    group = GroupPlannerAdapterPayload(
        schema_version="v2.4.0",
        adapter_version="sequencer_adapter_v1",
        scope=SequencerAdapterScope.GROUP,
        planner_change_mode=PlannerChangeMode.CONTRACT_ONLY,
        sequence=_sequence_context(),
        template_constraints=(_template_constraint(),),
        transition_constraints=(_transition_constraint(),),
        role_bindings=(_role_binding(),),
    )

    bundle = SequencerAdapterBundle(
        schema_version="v2.4.0",
        adapter_version="sequencer_adapter_v1",
        macro=macro,
        group=group,
    )

    assert bundle.macro.planner_change_mode is PlannerChangeMode.CONTRACT_ONLY
    assert bundle.group.planner_change_mode is PlannerChangeMode.CONTRACT_ONLY
    assert bundle.macro.scope is SequencerAdapterScope.MACRO
    assert bundle.group.scope is SequencerAdapterScope.GROUP
