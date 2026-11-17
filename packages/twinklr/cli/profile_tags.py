"""The one-line note `twinklr run` and `twinklr show` print for untagged wheel states."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.config.fixtures.instances import FixtureInstance
from twinklr.core.config.fixtures.state_tags import rig_tag_guidance
from twinklr.core.formats.xlights.layout.models.rgb_effects import Model

if TYPE_CHECKING:
    from rich.console import Console

PROFILE_TAGS_FILENAME = "profile_tags.txt"
"""Paste-ready meaning tags for the rig's untagged wheel and shutter states, written
beside a run's output when there are any."""


def report_profile_tags(
    console: Console,
    fixtures: Sequence[FixtureInstance],
    models: Sequence[Model],
    artifact_dir: Path,
) -> None:
    """Note in one line which fixtures have wheel or shutter states without a meaning tag,
    with the paste-ready tags in `PROFILE_TAGS_FILENAME` under `artifact_dir`; print
    nothing and remove an earlier file when every state carries its meaning.

    Untagged states are never guessed at, and this never fails the run: a file that
    cannot be written is replaced by the guidance printed in full.
    """
    guidance = rig_tag_guidance(fixtures, models)
    path = artifact_dir / PROFILE_TAGS_FILENAME
    if not guidance:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            console.print(
                f"WARNING: could not remove {path}: {error}", style="yellow", markup=False
            )
        return
    text = "\n".join(entry.text for entry in guidance)
    fixture_ids = ", ".join(fixture_id for entry in guidance for fixture_id in entry.fixture_ids)
    note = (
        f"NOTE: {fixture_ids}: wheel or shutter states without a meaning tag (hex, pattern, "
        "strobe) cannot carry the planner's colour, gobo or strobe choices; "
    )
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        note += f"{path} could not be written ({error}); the paste-ready tags to confirm:\n{text}"
    else:
        note += f"paste-ready tags to confirm: {path}"
    console.print(note, style="yellow", markup=False, highlight=False, soft_wrap=True)
