"""The evaluation re-render takes no user sequence (P1P-T11).

`rerender_plan` was the third export-path caller and the easiest to miss: it passed the
user's `.xsq` into `RenderingPipeline` as a template and pointed the output at
`temp_eval.xsq` next to their audio, so generating a report both read and wrote sequence
files it had no need to touch.
"""

from __future__ import annotations

import inspect

from twinklr.core.reporting.evaluation.cli import eval_report_cli
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.rerender import rerender_plan


def test_rerender_uses_fresh_path() -> None:
    """No sequence input reaches the re-render, at any layer of the eval stack."""
    for func in (rerender_plan, generate_evaluation_report):
        parameters = inspect.signature(func).parameters
        assert "xsq_path" not in parameters, f"{func.__name__} still takes a sequence"

    assert "template_xsq" not in inspect.getsource(rerender_plan)


def test_rerender_writes_no_sequence_file() -> None:
    """The pipeline is built with no output path, so nothing is exported.

    `tests/unit/reporting/evaluation/test_end_to_end.py` asserts the same thing from the
    outside, by running a real report and finding no `.xsq` anywhere beneath it.
    """
    assert "output_path=None" in inspect.getsource(rerender_plan)


def test_eval_report_cli_has_no_xsq_option() -> None:
    """The retired input is gone from the command the user types too."""
    option_names = {name for param in eval_report_cli.params for name in param.opts}
    assert "--xsq" not in option_names
    assert {"--checkpoint", "--audio", "--fixture", "--out"} <= option_names
