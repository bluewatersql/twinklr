"""Build group sequencer adapter payloads from FE artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from twinklr.core.feature_engineering.adapters.macro import (
    MacroAdapterBuilder,
    MacroAdapterBuilderOptions,
)
from twinklr.core.feature_engineering.models import (
    FeatureBundle,
    GroupPlannerAdapterPayload,
    PlannerChangeMode,
    RoleBindingContext,
    SequencerAdapterScope,
    TargetRoleAssignment,
    TemplateRecommendation,
    TransitionGraph,
)


@dataclass(frozen=True)
class GroupAdapterBuilderOptions:
    schema_version: str = "v2.4.0"
    adapter_version: str = "sequencer_adapter_v1"
    max_template_constraints: int = 64
    max_transition_constraints: int = 64


class GroupAdapterBuilder:
    """Construct contract-only group adapter payloads (no planner mutation)."""

    def __init__(self, options: GroupAdapterBuilderOptions | None = None) -> None:
        self._options = options or GroupAdapterBuilderOptions()
        self._macro_builder = MacroAdapterBuilder(
            MacroAdapterBuilderOptions(
                schema_version=self._options.schema_version,
                adapter_version=self._options.adapter_version,
                max_template_constraints=self._options.max_template_constraints,
                max_transition_constraints=self._options.max_transition_constraints,
            )
        )

    def build(
        self,
        *,
        bundle: FeatureBundle,
        recommendations: tuple[TemplateRecommendation, ...],
        transition_graph: TransitionGraph | None,
        role_assignments: tuple[TargetRoleAssignment, ...],
    ) -> GroupPlannerAdapterPayload:
        macro_payload = self._macro_builder.build(
            bundle=bundle,
            recommendations=recommendations,
            transition_graph=transition_graph,
            role_assignments=role_assignments,
        )
        return GroupPlannerAdapterPayload(
            schema_version=macro_payload.schema_version,
            adapter_version=macro_payload.adapter_version,
            scope=SequencerAdapterScope.GROUP,
            planner_change_mode=PlannerChangeMode.CONTRACT_ONLY,
            sequence=macro_payload.sequence,
            template_constraints=macro_payload.template_constraints,
            transition_constraints=macro_payload.transition_constraints,
            role_bindings=tuple(
                RoleBindingContext(
                    target_id=row.target_id,
                    target_name=row.target_name,
                    role=row.role,
                    role_confidence=row.role_confidence,
                )
                for row in macro_payload.role_bindings
            ),
        )
