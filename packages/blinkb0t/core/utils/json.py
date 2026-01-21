"""JSON utilities with numpy and Path support."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """JSON serializer for types not supported by default.

    Handles:
    - pathlib.Path -> str
    - numpy arrays -> list
    - numpy scalars -> Python scalars
    """
    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)

    return str(obj)


def write_json(path: str | Path, obj: Any) -> None:
    """Write object to JSON file with pretty formatting.

    Args:
        path: Output file path
        obj: Object to serialize (must be JSON-serializable)
    """
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )


def read_json(path: str | Path) -> dict[str, Any]:
    """Read and parse JSON file.

    Args:
        path: Input file path

    Returns:
        Parsed JSON as dictionary
    """
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
    return data


def write_log(job_config: JobConfig, name: str, data: dict[str, Any]) -> None:
    """Write a log entry to the job configuration output directory.

    Args:
        job_config: Job configuration
        name: Name of the log entry
        data: Dictionary to write to the log
    """
    if job_config.debug:
        write_json(f"{job_config.output_dir}/{name}_{job_config.project_name}.json", data)
