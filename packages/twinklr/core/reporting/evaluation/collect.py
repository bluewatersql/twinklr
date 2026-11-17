"""Checkpoint loading and plan extraction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import datetime as dt
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from pydantic import ConfigDict, TypeAdapter, ValidationError, with_config

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, load_plan
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.reporting.evaluation.models import RunMetadata
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

if TYPE_CHECKING:
    from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission


def load_checkpoint(checkpoint_path: Path) -> dict[str, Any]:
    """Load checkpoint JSON file.

    Args:
        checkpoint_path: Path to checkpoint JSON file

    Returns:
        Checkpoint data dictionary

    Raises:
        FileNotFoundError: If checkpoint file doesn't exist
        json.JSONDecodeError: If checkpoint file is not valid JSON

    Example:
        >>> checkpoint = load_checkpoint(Path("artifacts/my_song/checkpoints/plans/final.json"))
        >>> "plan" in checkpoint
        True
    """
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Checkpoint data is not a dict: {type(data)}")
    return data


@with_config(ConfigDict(extra="allow"))
class _RecordedFixture(TypedDict):
    """One fixture's entry in the run trace's `fixtures` (other keys kept as recorded)."""

    fixture_id: str
    xlights_model_name: str
    profile_sha256: str


class _RecordedRig(TypedDict):
    """The rendered rig's identity in a render record's `inputs`."""

    sha256: str
    fields: dict[str, str]
    live_layout: bool


class _RecordedInputs(TypedDict):
    """The input hashes a run's render record carries (`RecordedRender.inputs`)."""

    fixtures: list[_RecordedFixture]
    template_sha256: dict[str, str]
    beat_grid_sha256: str
    renderer_revision: str
    encoder_version: str
    rig: _RecordedRig
    dark_spans: NotRequired[list[list[int]]]


@dataclass(frozen=True)
class RecordedRender:
    """The render a run recorded in its checkpoint (`render`, written by
    `record_render` from `RenderingPipeline.checkpoint_record`): its fingerprint and the
    inputs a re-render needs to be that render.

    Attributes:
        fingerprint: The run's render fingerprint.
        policy: The job's full moving-head render policy.
        beat_grid: The beat grid the run rendered against.
        admission: The pre-planning gate's result, or None when no gate ran.
        dark_spans: The spans the render held every head dark over, as snapped and
            merged (`twinklr show`'s coordination rests); empty when there were none.
        inputs: The run trace's input hashes (`fixtures`, `template_sha256`,
            `beat_grid_sha256`, `renderer_revision`, `encoder_version`, and
            `dark_spans` when there were any) and the rendered rig's identity (`rig`).
    """

    fingerprint: str
    policy: MHRenderPolicy
    beat_grid: BeatGrid
    admission: TemplateAdmission | None
    dark_spans: tuple[tuple[int, int], ...]
    inputs: Mapping[str, Any]


def recorded_render(checkpoint_data: dict) -> RecordedRender:
    """The render the checkpoint records.

    Raises:
        UnsupportedRenderModeError: If the checkpoint records no render (the removed
            second renderer never wrote one), a record written before the cutover to one
            renderer (its policy names `mode`), or a record that does not read back (one written before the record carried the rig's
            identity).
    """
    render = checkpoint_data.get("render")
    if render is None:
        raise UnsupportedRenderModeError(
            "`twinklr eval-report` re-renders a plan only from the render recorded beside "
            "it in the checkpoint (`render`), and this checkpoint records none: the "
            "command that planned it stopped before it delivered its moving-head render, "
            "or could not write the record (it logs a warning when it cannot); re-running "
            "that command records it"
        )
    policy = render.get("policy") if isinstance(render, dict) else None
    if isinstance(policy, dict) and "mode" in policy:
        raise UnsupportedRenderModeError(
            "`twinklr eval-report` cannot re-render this checkpoint: its render record was "
            "written before the cutover to one moving-head renderer (its policy names "
            "`mode`); re-run the command that planned it to plan and record it again"
        )
    try:
        if not isinstance(render, dict):
            raise TypeError(f"expected a mapping, got {type(render).__name__}")
        return _recorded_render(render)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise UnsupportedRenderModeError(
            "`twinklr eval-report` cannot re-render this checkpoint: its render record "
            f"(`render`) is malformed ({type(error).__name__}: {error})"
        ) from error


def _recorded_render(render: dict[str, Any]) -> RecordedRender:
    """The record the render stage writes, read back."""
    from twinklr.core.sequencer.moving_heads.pipeline import TemplateAdmission

    admission = render["admission"]
    return RecordedRender(
        fingerprint=str(render["render_fingerprint"]),
        # Validated here, so a mismatch is compared against well-formed hashes.
        inputs=TypeAdapter(_RecordedInputs).validate_python(render["inputs"]),
        policy=MHRenderPolicy.model_validate(render["policy"]),
        beat_grid=BeatGrid.model_validate(render["beat_grid"]),
        dark_spans=TypeAdapter(tuple[tuple[int, int], ...]).validate_python(
            render.get("dark_spans", ())
        ),
        admission=None
        if admission is None
        else TemplateAdmission(
            admitted=tuple(admission["admitted"]),
            admitted_presets={t: tuple(p) for t, p in admission["admitted_presets"].items()},
            effective_preset=dict(admission["effective_preset"]),
            exclusions=tuple(admission["exclusions"]),
            preset_exclusions=tuple(admission["preset_exclusions"]),
            entry_dips=dict(admission["entry_dips"]),
        ),
    )


def extract_plan(checkpoint_data: dict) -> ChoreographyPlan:
    """Extract ChoreographyPlan from checkpoint data.

    Args:
        checkpoint_data: Checkpoint dictionary (from load_checkpoint)

    Returns:
        Validated ChoreographyPlan instance

    Raises:
        ValueError: If plan data is missing or invalid

    Example:
        >>> checkpoint = load_checkpoint(path)
        >>> plan = extract_plan(checkpoint)
        >>> len(plan.sections) > 0
        True
    """
    plan_data = checkpoint_data.get("plan")
    if not plan_data:
        raise ValueError("No 'plan' field found in checkpoint data")

    try:
        return load_plan(
            plan_data,
            remedy="re-run the command that planned it (`twinklr run` or `twinklr show`) "
            "with checkpoints on",
        )
    except ValidationError as e:
        raise ValueError(f"Failed to validate ChoreographyPlan: {e}") from e


def build_run_metadata(checkpoint_path: Path, checkpoint_data: dict) -> RunMetadata:
    """Build run metadata from checkpoint and environment.

    Gathers provenance information including run ID, timestamp, git SHA,
    and engine version.

    Args:
        checkpoint_path: Path to checkpoint file (for provenance)
        checkpoint_data: Checkpoint dictionary

    Returns:
        RunMetadata with provenance information

    Example:
        >>> metadata = build_run_metadata(path, checkpoint)
        >>> metadata.run_id
        'a3f9b2c1'
    """
    # Extract run ID from checkpoint
    # Try multiple sources: explicit run_id, project_name from context, or checkpoint filename
    run_id = checkpoint_data.get("run_id")
    if not run_id:
        # Try to get project name from context
        context = checkpoint_data.get("context", {})
        run_id = context.get("project_name")
    if not run_id:
        # Fall back to checkpoint filename (without extension)
        run_id = checkpoint_path.stem

    # Get git SHA (if in git repo)
    git_sha = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        git_sha = result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        # Not in git repo or git not available
        pass

    # Get engine version
    engine_version = "unknown"
    try:
        import importlib.metadata

        engine_version = importlib.metadata.version("twinklr")
    except Exception:
        # Package not installed or version not available
        pass

    return RunMetadata(
        run_id=run_id,
        timestamp=datetime.now(dt.UTC).isoformat(),
        git_sha=git_sha,
        engine_version=engine_version,
        checkpoint_path=checkpoint_path,
    )
