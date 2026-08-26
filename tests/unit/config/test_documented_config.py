"""Keep the user guide's curated config tables on the P4-T5 evidence seam."""

from __future__ import annotations

from pathlib import Path
import re

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind

_LEDGER_CELL = re.compile(r"\|\s*`((?:app|job)\.[^`]+)`\s*\|\s*$", re.MULTILINE)


def test_user_guide_config_rows_are_live_registry_paths() -> None:
    """A published knob cannot outlive its declared schema field or effect proof."""
    guide = Path("docs/user-guide.md").read_text(encoding="utf-8")
    documented = _LEDGER_CELL.findall(guide)

    assert documented, "user-guide config tables expose no registry-backed rows"
    assert len(documented) == len(set(documented)), "duplicate config ledger path in user guide"

    for path in documented:
        assert path in CONFIG_EFFECTS, f"documented config path has no P4-T5 record: {path}"
        disposition = CONFIG_EFFECTS[path]
        assert disposition.kind is not ConfigDispositionKind.REMOVED, (
            f"removed config path remains documented: {path}"
        )
        assert disposition.test_nodeid, f"documented config path has no evidence node: {path}"


def test_known_removed_user_guide_knobs_do_not_return() -> None:
    """Regression guard for the dead knobs that made the old guide unsafe."""
    guide = Path("docs/user-guide.md").read_text(encoding="utf-8")
    config_section = guide.split("## Configuration Files", maxsplit=1)[1].split(
        "## Running the Pipeline", maxsplit=1
    )[0]

    for stale_key in (
        "`output_dir`",
        "`agent.token_budget`",
        "`agent.recipe_generation_agent`",
        "`planner_features.enable_shutter`",
        "`planner_features.enable_color`",
        "`planner_features.enable_gobo`",
        "`checkpoint`",
    ):
        assert stale_key not in config_section
