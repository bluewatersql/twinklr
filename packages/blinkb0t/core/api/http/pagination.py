from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CursorPage(BaseModel):
    """Page of results for cursor-based pagination.

    Args:
        items: Items in this page
        next_cursor: Cursor token for the next page (None if last page)
    """

    model_config = {"frozen": True}

    items: Sequence[Any]
    next_cursor: str | None


def iterate_cursor(
    fetch_page: Callable[[str | None], CursorPage],
    *,
    start_cursor: str | None = None,
    max_pages: int | None = None,
) -> Iterator[Any]:
    """Iterate through cursor-paginated results (sync).

    Args:
        fetch_page: Function to fetch a page given a cursor
        start_cursor: Starting cursor (None for first page)
        max_pages: Maximum number of pages to fetch (None for all)

    Yields:
        Individual items from each page
    """
    cursor = start_cursor
    pages = 0
    while True:
        page = fetch_page(cursor)
        yield from page.items
        cursor = page.next_cursor
        pages += 1
        if not cursor:
            return
        if max_pages is not None and pages >= max_pages:
            return


async def iterate_cursor_async(
    fetch_page: Callable[[str | None], Awaitable[CursorPage]],
    *,
    start_cursor: str | None = None,
    max_pages: int | None = None,
) -> AsyncIterator[Any]:
    """Iterate through cursor-paginated results (async).

    Args:
        fetch_page: Async function to fetch a page given a cursor
        start_cursor: Starting cursor (None for first page)
        max_pages: Maximum number of pages to fetch (None for all)

    Yields:
        Individual items from each page
    """
    cursor = start_cursor
    pages = 0
    while True:
        page = await fetch_page(cursor)
        for it in page.items:
            yield it
        cursor = page.next_cursor
        pages += 1
        if not cursor:
            return
        if max_pages is not None and pages >= max_pages:
            return
