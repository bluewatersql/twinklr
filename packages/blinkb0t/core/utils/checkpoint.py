from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


class CheckpointType(Enum):
    RAW = "raw"
    IMPLEMENTATION = "implementation"
    FINAL = "final"
    EVALUATION = "evaluation"
    SEQUENCE = "sequence"
    AUDIO = "audio"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)

    return str(obj)


class CheckpointManager:
    def __init__(self, *, job_config: JobConfig):
        self.job_config = job_config
        # self.job_config.output_dir}

    def _get_checkpoint_name(self, checkpoint_type: CheckpointType) -> str:
        return f"{self.job_config.project_name}_{checkpoint_type.value}.json"

    def _get_checkpoint_path(self, checkpoint_type: CheckpointType) -> Path:
        checkpoint_folder = self._get_path(checkpoint_type)
        return Path(f"{checkpoint_folder}/{self._get_checkpoint_name(checkpoint_type)}").resolve()

    def _get_path(self, checkpoint_type: CheckpointType) -> str:
        match checkpoint_type:
            case CheckpointType.SEQUENCE | CheckpointType.AUDIO:
                folder = "checkpoints"
            case _:
                folder = "checkpoints/plans"

        return f"{self.job_config.output_dir}/{folder}"

    def write_checkpoint(self, checkpoint_type: CheckpointType, data: dict[str, Any]) -> None:
        checkpoint_path = self._get_checkpoint_path(checkpoint_type)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8"
        )

    def read_checkpoint(self, checkpoint_type: CheckpointType) -> dict[str, Any]:
        checkpoint_path = self._get_checkpoint_path(checkpoint_type)
        logger.debug(f"Reading checkpoint from {checkpoint_path}")
        if checkpoint_path.exists():
            data: Any = json.loads(checkpoint_path.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                logger.debug(
                    f"Invalid checkpoint data for {checkpoint_type}, got {type(data).__name__}"
                )
                raise ValueError(f"Invalid checkpoint data, got {type(data).__name__}")

            return data
        else:
            logger.debug(f"No checkpoint found for {checkpoint_type}")

        return {}


# "artifacts/need_a_favor/checkpoints "
# "artifacts/need_a_favor/checkpoints/plans "
