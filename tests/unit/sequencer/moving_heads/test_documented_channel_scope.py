"""Lock the grep-verifiable template counts published by the overview."""

from pathlib import Path
import re


def test_overview_channel_scope_matches_builtin_sources() -> None:
    builtins = Path("packages/twinklr/core/sequencer/moving_heads/templates/builtins")
    sources = [
        path.read_text(encoding="utf-8")
        for path in sorted(builtins.glob("*.py"))
        if path.name != "__init__.py"
    ]

    assert len(sources) == 37
    assert sum(bool(re.search(r"\bdimmer\s*=", source)) for source in sources) == 37
    for optional_channel in ("color", "shutter", "gobo"):
        assert sum(bool(re.search(rf"\b{optional_channel}\s*=", source)) for source in sources) == 1

    overview = Path("docs/overview.md").read_text(encoding="utf-8")
    assert "In the 37 Python builtins, every" in overview
    assert "one template each declares color, shutter, or" in overview
