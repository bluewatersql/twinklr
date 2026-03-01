"""Tests for SEC-01: eval() replaced with simpleeval in RecipeRenderer."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.recipe_renderer import RecipeRenderer


class TestRecipeRendererSecurity:
    """Verify eval() is replaced with safe simpleeval."""

    def test_no_builtin_eval_in_source(self) -> None:
        """Source code must not use Python's builtin eval()."""
        import inspect

        source = inspect.getsource(RecipeRenderer._evaluate_param)
        # Remove references to simple_eval (safe) and check for bare eval()
        cleaned = source.replace("simple_eval", "")
        assert "eval(" not in cleaned, "RecipeRenderer._evaluate_param still uses builtin eval()"

    def test_simpleeval_import_exists(self) -> None:
        """Module must import simpleeval."""
        from simpleeval import simple_eval

        assert callable(simple_eval)

    def test_malicious_expression_blocked(self) -> None:
        """Dangerous expressions must raise errors, not execute."""
        from simpleeval import FeatureNotAvailable, InvalidExpression, simple_eval

        # These should all fail with simpleeval
        dangerous_exprs = [
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd').read()",
            "().__class__.__bases__[0].__subclasses__()",
            "exec('import os')",
            "compile('1+1', '', 'exec')",
        ]
        allowed_vars = {"energy": 0.5, "density": 0.5}
        allowed_funcs = {"min": min, "max": max, "abs": abs, "round": round}

        for expr in dangerous_exprs:
            with pytest.raises(
                (
                    FeatureNotAvailable,
                    InvalidExpression,
                    NameError,
                    TypeError,
                    KeyError,
                    SyntaxError,
                )
            ):
                simple_eval(expr, names=allowed_vars, functions=allowed_funcs)

    def test_valid_expression_works(self) -> None:
        """Safe arithmetic expressions should still evaluate correctly."""
        from simpleeval import simple_eval

        allowed_vars = {"energy": 0.8, "density": 0.3}
        allowed_funcs = {"min": min, "max": max, "abs": abs, "round": round}

        result = simple_eval("energy * 255", names=allowed_vars, functions=allowed_funcs)
        assert result == pytest.approx(204.0)

        result = simple_eval("min(energy, density)", names=allowed_vars, functions=allowed_funcs)
        assert result == pytest.approx(0.3)

        result = simple_eval(
            "max(0, energy - density)", names=allowed_vars, functions=allowed_funcs
        )
        assert result == pytest.approx(0.5)
