"""Generic synchronous adapter for async classes.

Provides SyncAdapter: a universal wrapper that converts async methods into
blocking calls using asyncio.run(), eliminating repetitive sync wrapper boilerplate.
"""

import asyncio
import functools
from typing import Any


class SyncAdapter:
    """Generic synchronous wrapper for async classes.

    Wraps any async object and converts coroutine methods into blocking
    synchronous calls using asyncio.run(). Non-coroutine attributes and
    methods are passed through unchanged.

    Example:
        >>> class MyAsync:
        ...     async def fetch(self) -> str:
        ...         return "data"
        ...
        >>> adapter = SyncAdapter(MyAsync())
        >>> adapter.fetch()  # Blocks until complete
        'data'

    Args:
        async_obj: The async object to wrap.
    """

    def __init__(self, async_obj: Any) -> None:
        """Initialize the adapter with the async object to wrap.

        Args:
            async_obj: The async object whose methods will be wrapped.
        """
        self._async_obj = async_obj

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the wrapped object.

        Coroutine functions are wrapped with asyncio.run(); all other
        attributes are returned as-is.

        Args:
            name: Attribute name to look up on the wrapped object.

        Returns:
            A blocking wrapper if the attribute is a coroutine function,
            otherwise the attribute itself.

        Raises:
            AttributeError: If the attribute does not exist on the wrapped object.
        """
        attr = getattr(self._async_obj, name)
        if asyncio.iscoroutinefunction(attr):

            @functools.wraps(attr)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                """Blocking wrapper that runs the coroutine synchronously."""
                return asyncio.run(attr(*args, **kwargs))

            return sync_wrapper
        return attr
