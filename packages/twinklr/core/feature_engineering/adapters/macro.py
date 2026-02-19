"""Build macro sequencer adapter payloads from FE artifacts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models import (
    FeatureBundle,
    MacroPlannerAdapterPayload,
    PlannerChangeMode,
    RoleBindingContext,
    SequenceAdapterContext,
    SequencerAdapterScope,
    TargetRoleAssignment,
    TemplateConstraint,
    TemplateRecommendation,
    TransitionConstraint,
    TransitionGraph,
    TransitionType,
)


@dataclass(frozen=True)
class MacroAdapterBuilderOptions:
    schema_version: str = "v2.4.0"
    adapter_version: str = "sequencer_adapter_v1"
    max_template_constraints: int = 64
    max_transition_constraints: int = 64


class MacroAdapterBuilder:
    """Construct contract-only macro adapter payloads (no planner mutation)."""

    def __init__(self, options: MacroAdapterBuilderOptions | None = None) -> None:
        self._options = options or MacroAdapterBuilderOptions()

    def build(
        self,
        *,
        bundle: FeatureBundle,
        recommendations: tuple[TemplateRecommendation, ...],
        transition_graph: TransitionGraph | None,
        role_assignments: tuple[TargetRoleAssignment, ...],
    ) -> MacroPlannerAdapterPayload:
        sequence = SequenceAdapterContext(
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            sequence_name=bundle.song,
            artist=bundle.artist or None,
            sequence_sha256=bundle.sequence_sha256,
            audio_status=bundle.audio.audio_status,
        )
        roles = {row.role.value for row in role_assignments}
        template_constraints = tuple(
            TemplateConstraint(
                template_id=row.template_id,
                template_kind=row.template_kind,
                retrieval_score=row.retrieval_score,
                support_count=row.support_count,
                support_ratio=row.support_ratio,
                transition_flow_norm=row.transition_flow_norm,
                effect_family=row.effect_family,
                role=row.role,
                motion_class=row.motion_class,
                energy_class=row.energy_class,
            )
            for row in self._select_templates(recommendations=recommendations, role_allowlist=roles)
        )
        transition_constraints = (
            self._to_transition_constraints(transition_graph) if transition_graph is not None else ()
        )
        role_bindings = tuple(
            RoleBindingContext(
                target_id=row.target_id,
                target_name=row.target_name,
                role=row.role.value,
                role_confidence=row.role_confidence,
            )
            for row in sorted(
                role_assignments,
                key=lambda item: (
                    item.role.value,
                    item.target_name.lower(),
                    item.target_id,
                ),
            )
        )
        return MacroPlannerAdapterPayload(
            schema_version=self._options.schema_version,
            adapter_version=self._options.adapter_version,
            scope=SequencerAdapterScope.MACRO,
            planner_change_mode=PlannerChangeMode.CONTRACT_ONLY,
            sequence=sequence,
            template_constraints=template_constraints,
            transition_constraints=transition_constraints,
            role_bindings=role_bindings,
        )

    def _select_templates(
        self,
        *,
        recommendations: tuple[TemplateRecommendation, ...],
        role_allowlist: set[str],
    ) -> tuple[TemplateRecommendation, ...]:
        if not recommendations:
            return ()

        ranked = sorted(
            recommendations,
            key=lambda item: (
                -item.retrieval_score,
                item.template_kind.value,
                item.template_id,
            ),
        )
        if not role_allowlist:
            return tuple(ranked[: self._options.max_template_constraints])

        in_role = [row for row in ranked if row.role is not None and row.role in role_allowlist]
        role_neutral = [row for row in ranked if row.role is None]
        selected: list[TemplateRecommendation] = []
        selected.extend(in_role)
        if len(selected) < self._options.max_template_constraints:
            needed = self._options.max_template_constraints - len(selected)
            selected.extend(role_neutral[:needed])
        return tuple(selected[: self._options.max_template_constraints])

    def _to_transition_constraints(
        self, transition_graph: TransitionGraph
    ) -> tuple[TransitionConstraint, ...]:
        rows: list[TransitionConstraint] = []
        for edge in sorted(
            transition_graph.edges,
            key=lambda item: (-item.edge_count, item.source_template_id, item.target_template_id),
        ):
            rows.append(
                TransitionConstraint(
                    source_template_id=edge.source_template_id,
                    target_template_id=edge.target_template_id,
                    transition_type=self._dominant_transition_type(edge.transition_type_distribution),
                    edge_count=edge.edge_count,
                )
            )
            if len(rows) >= self._options.max_transition_constraints:
                break
        return tuple(rows)

    @staticmethod
    def _dominant_transition_type(
        distribution: dict[TransitionType, int],
    ) -> TransitionType:
        if not distribution:
            return TransitionType.HARD_CUT
        grouped: defaultdict[int, list[TransitionType]] = defaultdict(list)
        for transition_type, count in distribution.items():
            grouped[count].append(transition_type)
        max_count = max(grouped)
        candidates = sorted(grouped[max_count], key=lambda item: item.value)
        return candidates[0]
