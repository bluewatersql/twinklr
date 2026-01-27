from __future__ import annotations

import json
import logging
import uuid
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
        self.run_id: str | None = None  # Unique ID for current orchestration run

    def start_run(self) -> str:
        """Start a new orchestration run and generate unique run ID.

        Returns:
            The generated run ID (UUID4 hex)
        """
        self.run_id = uuid.uuid4().hex[:8]  # Short 8-char hex ID
        logger.info(f"Started orchestration run: {self.run_id}")
        return self.run_id

    def _get_checkpoint_name(self, checkpoint_type: CheckpointType) -> str:
        return f"{self.job_config.project_name}_{checkpoint_type.value}.json"

    def _get_checkpoint_path(self, checkpoint_type: CheckpointType) -> Path:
        checkpoint_folder = self._get_path(checkpoint_type)
        return Path(f"{checkpoint_folder}/{self._get_checkpoint_name(checkpoint_type)}").resolve()

    def _get_iteration_checkpoint_path(
        self, checkpoint_type: CheckpointType, iteration: int
    ) -> Path:
        """Get path for iteration-specific checkpoint.

        Args:
            checkpoint_type: Type of checkpoint
            iteration: Iteration number (1-indexed)

        Returns:
            Path to iteration checkpoint file
        """
        checkpoint_folder = self._get_path(checkpoint_type)
        run_prefix = f"{self.run_id}_" if self.run_id else ""
        filename = f"{self.job_config.project_name}_{run_prefix}iter{iteration:02d}_{checkpoint_type.value}.json"
        return Path(f"{checkpoint_folder}/{filename}").resolve()

    def _get_path(self, checkpoint_type: CheckpointType) -> str:
        match checkpoint_type:
            case CheckpointType.SEQUENCE | CheckpointType.AUDIO:
                folder = "checkpoints"
            case _:
                folder = "checkpoints/plans"

        return f"{self.job_config.output_dir}/{folder}"

    def write_checkpoint(self, checkpoint_type: CheckpointType, data: dict[str, Any]) -> None:
        """Write checkpoint to default location (for FINAL, SEQUENCE, AUDIO)."""
        checkpoint_path = self._get_checkpoint_path(checkpoint_type)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8"
        )

    def write_iteration_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        data: dict[str, Any],
        iteration: int,
    ) -> None:
        """Write iteration-specific checkpoint.

        Args:
            checkpoint_type: Type of checkpoint (RAW or EVALUATION)
            data: Data to checkpoint
            iteration: Iteration number (1-indexed)
        """
        checkpoint_path = self._get_iteration_checkpoint_path(checkpoint_type, iteration)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Add metadata
        checkpoint_data = {
            "run_id": self.run_id,
            "iteration": iteration,
            "checkpoint_type": checkpoint_type.value,
            **data,
        }

        checkpoint_path.write_text(
            json.dumps(checkpoint_data, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        logger.debug(f"Saved iteration checkpoint: {checkpoint_path.name}")

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
