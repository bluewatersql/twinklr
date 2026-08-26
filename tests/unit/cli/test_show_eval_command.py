"""Offline show-eval registration."""

from twinklr.cli.main import build_arg_parser


def test_show_eval_is_registered_with_manifest_and_output() -> None:
    args = build_arg_parser().parse_args(
        ["show-eval", "show.xsq.evaluation.json", "--out", "report.json"]
    )
    assert args.cmd == "show-eval"
    assert args.manifest == "show.xsq.evaluation.json"
    assert args.out == "report.json"
