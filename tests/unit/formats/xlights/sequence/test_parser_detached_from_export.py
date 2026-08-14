"""`XSQParser` survives P1P-T11 — detached from the export path, not deleted.

Reading a user's sequence is how the corpus profiler learns from real shows. Writing
one derived from a document Twinklr parsed is what damaged the user's file. The parser
keeps the first job and loses the second, so these tests pin *where* it may be used
rather than whether it exists.
"""

from __future__ import annotations

from pathlib import Path

PACKAGES_ROOT = Path(__file__).resolve().parents[5] / "packages" / "twinklr"

_ALLOWED_PARSER_CONSUMERS = {
    # Analysis: reads sequence packs to build the corpus profile.
    "core/profiling/profiler.py",
    # Analysis: fingerprints an existing sequence (duration, effect mix, timing events).
    # Has no caller anywhere in the tree today; listed because it reads, never writes.
    "core/sequencer/analyzer.py",
    # The parser itself and the package that re-exports it.
    "core/formats/xlights/sequence/parser.py",
    "core/formats/xlights/sequence/__init__.py",
}


def _modules_importing(symbol: str) -> set[str]:
    """Modules with an import line naming `symbol` (docstrings do not count)."""
    return {
        str(path.relative_to(PACKAGES_ROOT))
        for path in PACKAGES_ROOT.rglob("*.py")
        if any(
            symbol in line and ("import" in line or line.lstrip().startswith(symbol))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    }


def _modules_naming(symbol: str) -> set[str]:
    return {
        str(path.relative_to(PACKAGES_ROOT))
        for path in PACKAGES_ROOT.rglob("*.py")
        if symbol in path.read_text(encoding="utf-8")
    }


def test_profiler_still_uses_parser() -> None:
    """The analysis consumer is intact — this task detaches, it does not delete."""
    from twinklr.core.profiling.profiler import SequencePackProfiler

    assert SequencePackProfiler()._xsq_parser is not None
    assert "core/profiling/profiler.py" in _modules_importing("XSQParser")


def test_parser_has_no_export_path_consumer() -> None:
    """Nothing outside analysis parses a sequence any more.

    The template branch in the moving-heads exporter was the always-taken path: every
    shipped run parsed the user's `.xsq`, regenerated it and wrote back a lossy copy.
    A new import of `XSQParser` into a render, export or CLI module reintroduces that
    class of defect, so it fails here.
    """
    unexpected = _modules_importing("XSQParser") - _ALLOWED_PARSER_CONSUMERS
    assert unexpected == set(), f"XSQParser used outside the analysis path: {sorted(unexpected)}"


def test_no_module_takes_a_template_sequence() -> None:
    """The retired input leaves no plumbing behind."""
    assert _modules_naming("template_xsq") == set()
    assert _modules_naming("xsq_template_path") == set()
