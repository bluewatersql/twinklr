"""Checkpoint loading and plan extraction."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from blinkb0t.core.reporting.evaluation.models import RunMetadata


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
        return ChoreographyPlan.model_validate(plan_data)
    except Exception as e:
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

        engine_version = importlib.metadata.version("blinkb0t")
    except Exception:
        # Package not installed or version not available
        pass

    return RunMetadata(
        run_id=run_id,
        timestamp=datetime.now().isoformat(),
        git_sha=git_sha,
        engine_version=engine_version,
        checkpoint_path=checkpoint_path,
    )
