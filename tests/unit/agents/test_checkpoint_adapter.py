"""Tests for agent checkpoint adapter (Phase 8 async)."""

from __future__ import annotations

import tempfile

from pydantic import BaseModel
import pytest

from twinklr.core.agents.checkpoint_adapter import (
    load_checkpoint_async,
    save_checkpoint_async,
)
from twinklr.core.caching import CacheKey, FSCache


class _TestCheckpointData(BaseModel):
    """Test model for checkpoint data."""

    value: int
    message: str


class TestSaveCheckpoint:
    """Tests for save_checkpoint_async()."""

    @pytest.mark.asyncio
    async def test_saves_checkpoint_with_type(self) -> None:
        """Saves checkpoint with correct step_id."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            data = _TestCheckpointData(value=42, message="test")

            await save_checkpoint_async(
                project_name="test_project",
                checkpoint_type="raw",
                data=data,
                cache=cache,
            )

            # Verify saved with correct key
            key = CacheKey(
                step_id="agent.raw",
                step_version="1",
                input_fingerprint="test_project",
            )
            loaded = await cache.load(key, _TestCheckpointData)

            assert loaded is not None
            assert loaded.value == 42
            assert loaded.message == "test"

    @pytest.mark.asyncio
    async def test_iteration_appended_to_identifier(self) -> None:
        """Iteration number is appended to identifier when provided."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            data = _TestCheckpointData(value=1, message="iter1")

            await save_checkpoint_async(
                project_name="test_project",
                checkpoint_type="eval",
                data=data,
                cache=cache,
                iteration=1,
            )

            # Load with iteration-specific key (zero-padded)
            key = CacheKey(
                step_id="agent.eval",
                step_version="1",
                input_fingerprint="test_project_iter01",
            )
            loaded = await cache.load(key, _TestCheckpointData)

            assert loaded is not None
            assert loaded.value == 1

    @pytest.mark.asyncio
    async def test_run_id_appended_to_identifier(self) -> None:
        """run_id is appended to identifier when provided."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            data = _TestCheckpointData(value=99, message="run")

            await save_checkpoint_async(
                project_name="test_project",
                checkpoint_type="final",
                data=data,
                cache=cache,
                run_id="run_abc123",
            )

            # Load with run_id-specific key
            key = CacheKey(
                step_id="agent.final",
                step_version="1",
                input_fingerprint="test_project_run_abc123",
            )
            loaded = await cache.load(key, _TestCheckpointData)

            assert loaded is not None
            assert loaded.value == 99


class TestLoadCheckpoint:
    """Tests for load_checkpoint_async()."""

    @pytest.mark.asyncio
    async def test_returns_none_on_miss(self) -> None:
        """Returns None when checkpoint doesn't exist."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            result = await load_checkpoint_async(
                project_name="nonexistent",
                checkpoint_type="raw",
                model_cls=_TestCheckpointData,
                cache=cache,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_loads_saved_checkpoint(self) -> None:
        """Loads previously saved checkpoint."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            # Save checkpoint
            data = _TestCheckpointData(value=777, message="saved")
            await save_checkpoint_async(
                project_name="my_project",
                checkpoint_type="raw",
                data=data,
                cache=cache,
            )

            # Load checkpoint
            loaded = await load_checkpoint_async(
                project_name="my_project",
                checkpoint_type="raw",
                model_cls=_TestCheckpointData,
                cache=cache,
            )

            assert loaded is not None
            assert loaded.value == 777
            assert loaded.message == "saved"

    @pytest.mark.asyncio
    async def test_loads_with_iteration(self) -> None:
        """Loads iteration-specific checkpoint."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            # Save iteration-specific checkpoint
            data = _TestCheckpointData(value=5, message="iter5")
            await save_checkpoint_async(
                project_name="project",
                checkpoint_type="eval",
                data=data,
                cache=cache,
                iteration=5,
            )

            # Load iteration-specific checkpoint
            loaded = await load_checkpoint_async(
                project_name="project",
                checkpoint_type="eval",
                model_cls=_TestCheckpointData,
                cache=cache,
                iteration=5,
            )

            assert loaded is not None
            assert loaded.value == 5
            assert loaded.message == "iter5"
