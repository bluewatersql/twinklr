"""Warnings a moving-head render logs, held back for a render nobody sees.

The played rule for transitions renders the plan a second time without them
(`pipeline.RenderingPipeline`); that render's warnings are the first render's own, so it
renders inside `held()` and every warning or note the render path logs through `warn` or
`note` is collected there instead; a render that plays again (a transition given up on a
head to keep a hit) holds each pass's lines and logs only the last pass's (`replay`). The flag lives in a context variable: scoped to that
render's call, never the process's logger state.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from logging import INFO, WARNING, Logger

_HELD: ContextVar[list[tuple[int, str]] | None] = ContextVar(
    "moving_head_render_held", default=None
)


@contextmanager
def held() -> Iterator[list[tuple[int, str]]]:
    """Collect, instead of logging, what the render inside logs (each line with its
    level); yields the collection."""
    collected: list[tuple[int, str]] = []
    token = _HELD.set(collected)
    try:
        yield collected
    finally:
        _HELD.reset(token)


def warn(logger: Logger, message: str, *args: object) -> None:
    """`logger.warning`, or held where the render runs inside `held()`."""
    _log(logger, WARNING, message, *args)


def note(logger: Logger, message: str, *args: object) -> None:
    """`logger.info`, or held where the render runs inside `held()`."""
    _log(logger, INFO, message, *args)


def replay(logger: Logger, collected: list[tuple[int, str]]) -> None:
    """Log what `held()` collected (held again where this runs inside `held()`)."""
    for level, line in collected:
        _log(logger, level, "%s", line)


def _log(logger: Logger, level: int, message: str, *args: object) -> None:
    collected = _HELD.get()
    if collected is None:
        logger.log(level, message, *args, stacklevel=3)
    else:
        collected.append((level, message % args if args else message))
