"""LOCAL-ONLY command surface for the P2P-T13 owner protocol.

This module is inert unless invoked explicitly.  The ``run`` command requires both an
owner opt-in flag and an owner-local backend factory; Twinklr does not ship audio,
credentials, xLights automation, or a fake experiment result.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
import importlib
import json
from pathlib import Path
from typing import Any, cast

from twinklr.core.reporting.evaluation.render import write_comparison_report_json
from twinklr.core.reporting.evaluation.three_arm import (
    ArmRunResult,
    BlindRevealKey,
    BlindReviewBundle,
    BlindReviewPacket,
    ComparisonExperimentRunner,
    ComparisonManifest,
    ExperimentBackend,
    HumanRanking,
    build_blind_review,
    compute_comparison_report,
    stage_blind_review_packet,
    validate_calibration,
    verify_blind_packet_bytes,
    write_human_ranking,
    write_reveal_key_after_ranking,
)


def _read_manifest(path: Path) -> ComparisonManifest:
    return ComparisonManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _read_results(path: Path) -> list[ArmRunResult]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("results artifact must be a JSON list")
    return [ArmRunResult.model_validate(item) for item in raw]


def _write_results(path: Path, results: Sequence[ArmRunResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [item.model_dump(mode="json", exclude_computed_fields=True) for item in results],
            indent=2,
        ),
        encoding="utf-8",
    )


def _backend_factory(reference: str) -> Callable[[ComparisonManifest], ExperimentBackend]:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("backend factory must use module:callable syntax")
    factory = getattr(importlib.import_module(module_name), attribute)
    if not callable(factory):
        raise TypeError("backend factory reference is not callable")
    return cast("Callable[[ComparisonManifest], ExperimentBackend]", factory)


async def _run_owner(args: argparse.Namespace) -> None:
    if not args.owner_opt_in:
        raise ValueError("LOCAL-ONLY run requires explicit owner opt-in")
    manifest = _read_manifest(args.manifest)
    manifest.validate_frozen_files()
    validate_calibration(manifest)
    backend = _backend_factory(args.backend_factory)(manifest)
    partial_dir = args.results.parent / f".{args.results.name}.partial-attempts"
    results = await ComparisonExperimentRunner(
        manifest=manifest,
        backend=backend,
        attempt_journal_dir=partial_dir,
    ).run(owner_opt_in=args.owner_opt_in)
    _write_results(args.results, results)


def _prepare_blind(args: argparse.Namespace) -> None:
    results = _read_results(args.results)
    stage_blind_review_packet(
        bundle=build_blind_review(results, seed=args.seed),
        results=results,
        output_dir=args.output_dir,
    )


def _record_ranking(args: argparse.Namespace) -> None:
    packet = BlindReviewPacket.model_validate_json(args.packet.read_text(encoding="utf-8"))
    verify_blind_packet_bytes(packet, expected_staging_parent=args.packet.parent)
    raw_ids: Any = json.loads(args.ordered_ids.read_text(encoding="utf-8"))
    if not isinstance(raw_ids, list) or not all(isinstance(value, str) for value in raw_ids):
        raise ValueError("ordered IDs must be a JSON list of blind ID strings")
    write_human_ranking(
        packet=packet,
        ranking=HumanRanking(
            review_id=packet.review_id,
            packet_sha256=packet.packet_sha256,
            ordered_blind_ids=raw_ids,
            notes=args.notes,
        ),
        output_path=args.ranking,
    )


def _finalize(args: argparse.Namespace) -> None:
    manifest = _read_manifest(args.manifest)
    validate_calibration(manifest)
    results = _read_results(args.results)
    packet = BlindReviewPacket.model_validate_json(args.packet.read_text(encoding="utf-8"))
    verify_blind_packet_bytes(packet, expected_staging_parent=args.packet.parent)
    ranking = HumanRanking.model_validate_json(args.ranking.read_text(encoding="utf-8"))
    regenerated = build_blind_review(results, seed=packet.seed)
    if regenerated.packet.review_id != packet.review_id or (
        regenerated.packet.review_sequence_ids != packet.review_sequence_ids
    ):
        raise ValueError("results do not reproduce the frozen blind packet")
    reveal = BlindRevealKey(
        review_id=packet.review_id,
        packet_sha256=packet.packet_sha256,
        entries=regenerated.reveal.entries,
    )
    write_reveal_key_after_ranking(
        reveal=reveal,
        ranking_path=args.ranking,
        output_path=args.reveal,
    )
    report = compute_comparison_report(
        manifest=manifest,
        results=results,
        blind_review=BlindReviewBundle(packet=packet, reveal=reveal),
        human_ranking=ranking,
    )
    write_comparison_report_json(report, args.report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LOCAL-ONLY P2P-T13 owner workflow")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="execute the calibrated 5N owner-local comparison")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--backend-factory", required=True, help="owner module:callable")
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--owner-opt-in", action="store_true", required=True)
    run.set_defaults(handler=lambda args: asyncio.run(_run_owner(args)))

    blind = commands.add_parser("prepare-blind", help="stage opaque review files only")
    blind.add_argument("--results", type=Path, required=True)
    blind.add_argument("--seed", type=int, required=True)
    blind.add_argument("--output-dir", type=Path, required=True)
    blind.set_defaults(handler=_prepare_blind)

    rank = commands.add_parser("record-ranking", help="persist ranking before unblinding")
    rank.add_argument("--packet", type=Path, required=True)
    rank.add_argument("--ordered-ids", type=Path, required=True)
    rank.add_argument("--ranking", type=Path, required=True)
    rank.add_argument("--notes")
    rank.set_defaults(handler=_record_ranking)

    finalize = commands.add_parser("finalize", help="unblind and write the typed report")
    finalize.add_argument("--manifest", type=Path, required=True)
    finalize.add_argument("--results", type=Path, required=True)
    finalize.add_argument("--packet", type=Path, required=True)
    finalize.add_argument("--ranking", type=Path, required=True)
    finalize.add_argument("--reveal", type=Path, required=True)
    finalize.add_argument("--report", type=Path, required=True)
    finalize.set_defaults(handler=_finalize)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
