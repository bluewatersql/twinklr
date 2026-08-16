"""Focused composition-test bootstrap.

The production model graph intentionally resolves ``GroupPlanSet``'s holistic
evaluation forward reference when the holistic module is loaded.  The full suite
loads that module before these tests, while this directory in isolation does not.
Import it here so the required focused gate exercises the same resolved model graph.
"""

from twinklr.core.agents.sequencer.group_planner import holistic as _holistic  # noqa: F401
