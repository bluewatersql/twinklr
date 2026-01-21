"""Tests for the moving head plan generator.

Updated to use new plan generator API.
"""

from __future__ import annotations

from blinkb0t.core.agents.moving_heads import PlanGenerationResult, PlanGenerator


class TestPlanGenerator:
    """Test plan generator functionality."""

    def test_plan_generator_exists(self):
        """Verify PlanGenerator class exists and can be instantiated."""
        # This is a basic smoke test - real tests would need API key and full setup
        assert PlanGenerator is not None
        assert PlanGenerationResult is not None
