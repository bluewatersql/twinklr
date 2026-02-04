"""Generic template registry infrastructure.

Provides a type-safe, factory-based template registry that can be
specialized for different template types (group, asset, etc.).

Pattern: Factory-based registration prevents shared state bugs.
Each get() call materializes a fresh instance from the factory.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


def normalize_key(s: str) -> str:
    """Normalize user-provided keys to stable lookup key.

    Args:
        s: Key to normalize (template_id, name, or alias).

    Returns:
        Normalized key (lowercase, alphanumeric/underscore only).
    """
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s).strip("_")


class TemplateNotFoundError(KeyError):
    """Raised when a template is not found in the registry."""

    pass


@runtime_checkable
class TemplateProtocol(Protocol):
    """Protocol for template types that can be registered.

    All template types must have these common fields.
    """

    template_id: str
    template_version: str
    name: str
    tags: list[str]

    def model_copy(self, *, deep: bool = False) -> TemplateProtocol:
        """Create a copy of the model."""
        ...


# Type variables for generic registry
T = TypeVar("T", bound=TemplateProtocol)
TInfo = TypeVar("TInfo", bound="BaseTemplateInfo")


class BaseTemplateInfo(BaseModel):
    """Base lightweight metadata for listing/search without materializing instances.

    Subclass this for domain-specific info (e.g., GroupTemplateInfo, AssetTemplateInfo).

    Attributes:
        template_id: Unique template identifier.
        version: Template version string.
        name: Human-readable template name.
        tags: Tuple of tags for categorization.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    version: str
    name: str
    tags: tuple[str, ...]


class TemplateRegistry(Generic[T, TInfo]):
    """Generic factory-based template registry.

    Pattern: Factory-based registration prevents shared state bugs.
    Each get() call materializes a fresh instance from the factory.

    Type Parameters:
        T: The template type (e.g., GroupPlanTemplate, AssetTemplate).
        TInfo: The info type for lightweight metadata (e.g., TemplateInfo).

    Example:
        >>> registry = TemplateRegistry[GroupPlanTemplate, TemplateInfo](
        ...     info_factory=lambda t: TemplateInfo(...)
        ... )
        >>> registry.register(my_factory)
        >>> template = registry.get("my_template")
    """

    def __init__(
        self,
        info_factory: Callable[[T], TInfo],
        *,
        name: str = "template",
    ) -> None:
        """Initialize empty registry.

        Args:
            info_factory: Callable that creates TInfo from a template instance.
            name: Human-readable name for error messages (e.g., "group template").
        """
        self._factories_by_id: dict[str, Callable[[], T]] = {}
        self._aliases: dict[str, str] = {}  # alias_key -> template_id
        self._info_by_id: dict[str, TInfo] = {}
        self._info_factory = info_factory
        self._name = name

    def register(
        self,
        factory: Callable[[], T],
        *,
        template_id: str | None = None,
        aliases: Iterable[str] = (),
    ) -> None:
        """Register a template factory.

        Args:
            factory: Callable that returns a template instance.
            template_id: Optional explicit template_id (uses factory's if None).
            aliases: Additional aliases for lookup.

        Raises:
            ValueError: If template_id already registered.
        """
        # Materialize once for validation and metadata extraction
        t = factory()
        tid = template_id or t.template_id

        if tid in self._factories_by_id:
            raise ValueError(f"{self._name.title()} already registered: {tid}")

        self._factories_by_id[tid] = factory

        # Register aliases: id, name, and any provided aliases
        all_aliases = {tid, t.name, *aliases}
        for a in all_aliases:
            self._aliases[normalize_key(a)] = tid

        # Store lightweight info for list/search
        self._info_by_id[tid] = self._info_factory(t)

        logger.debug(f"Registered {self._name}: {tid}")

    def get(self, key: str, *, deep_copy: bool = True) -> T:
        """Lookup template by template_id, name, or alias.

        Args:
            key: Template identifier (id, name, or alias).
            deep_copy: Whether to return a deep copy (default: True).

        Returns:
            Template instance.

        Raises:
            TemplateNotFoundError: If template not found.
        """
        # Normalize key and lookup template_id
        tid = self._aliases.get(normalize_key(key), key)
        factory = self._factories_by_id.get(tid)

        if not factory:
            raise TemplateNotFoundError(f"Unknown {self._name}: {key}")

        # Materialize fresh instance
        t = factory()

        # Return deep copy to prevent shared state
        # mypy doesn't understand that T.model_copy() returns T, not TemplateProtocol
        return t.model_copy(deep=True) if deep_copy else t  # type: ignore[return-value]

    def get_info(self, key: str) -> TInfo | None:
        """Get template info by key without materializing.

        Args:
            key: Template identifier (id, name, or alias).

        Returns:
            TInfo if found, None otherwise.
        """
        tid = self._aliases.get(normalize_key(key), key)
        return self._info_by_id.get(tid)

    def has(self, key: str) -> bool:
        """Check if template exists.

        Args:
            key: Template identifier (id, name, or alias).

        Returns:
            True if template exists.
        """
        tid = self._aliases.get(normalize_key(key), key)
        return tid in self._factories_by_id

    def list_all(self) -> list[TInfo]:
        """List all registered templates.

        Returns:
            List of TInfo, sorted by template_id.
        """
        return sorted(self._info_by_id.values(), key=lambda x: x.template_id)

    def list_ids(self) -> list[str]:
        """List all registered template IDs.

        Returns:
            Sorted list of template_id strings.
        """
        return sorted(self._factories_by_id.keys())

    def __len__(self) -> int:
        """Return number of registered templates."""
        return len(self._factories_by_id)

    def __contains__(self, key: str) -> bool:
        """Check if template exists (supports 'in' operator)."""
        return self.has(key)
