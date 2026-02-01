"""Agent specifications for GroupPlanner and Judge."""

from twinklr.core.agents.sequencer.group_planner.models import GroupPlan
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict


def get_planner_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.7,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get agent spec for GroupPlanner agent.

    Args:
        model: LLM model to use
        temperature: Sampling temperature
        token_budget: Optional token limit

    Returns:
        AgentSpec configured for GroupPlanner
    """
    return AgentSpec(
        name="group_planner",
        prompt_pack="group_planner",
        response_model=GroupPlan,
        mode=AgentMode.CONVERSATIONAL,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


def get_judge_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get agent spec for GroupPlanner judge.

    Args:
        model: LLM model to use
        temperature: Sampling temperature
        token_budget: Optional token limit

    Returns:
        AgentSpec configured for judge
    """
    return AgentSpec(
        name="group_judge",
        prompt_pack="group_judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


# Module-level spec constants for convenience
GROUPPLANNER_SPEC = get_planner_spec()
GROUP_JUDGE_SPEC = get_judge_spec()
