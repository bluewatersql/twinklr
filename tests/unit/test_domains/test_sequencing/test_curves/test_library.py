"""Tests for CurveLibrary class.

Following TDD - these tests are written BEFORE implementation.
"""

from __future__ import annotations

import pytest


def test_curve_library_initialization() -> None:
    """Test CurveLibrary can be initialized."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()
    assert library is not None


def test_curve_library_register_curve() -> None:
    """Test registering a curve definition."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    curve_def = CurveDefinition(
        id="test_sine",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
        description="Test sine curve",
    )

    library.register(curve_def)

    # Should be able to retrieve it
    retrieved = library.get("test_sine")
    assert retrieved is not None
    assert retrieved.id == "test_sine"
    assert retrieved.source == CurveSource.NATIVE


def test_curve_library_get_nonexistent() -> None:
    """Test getting a non-existent curve returns None."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()

    result = library.get("nonexistent_curve")
    assert result is None


def test_curve_library_list_all() -> None:
    """Test listing all curves in library."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    # Register multiple curves
    library.register(
        CurveDefinition(
            id="sine1",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )
    library.register(
        CurveDefinition(
            id="ramp1",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.RAMP.value,
        )
    )

    all_curves = library.list_all()
    assert len(all_curves) == 2
    assert any(c.id == "sine1" for c in all_curves)
    assert any(c.id == "ramp1" for c in all_curves)


def test_curve_library_filter_by_source() -> None:
    """Test filtering curves by source type."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    # Register native curves
    library.register(
        CurveDefinition(
            id="sine_native",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    # Register custom curves
    library.register(
        CurveDefinition(
            id="cosine_custom",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.COSINE.value,
        )
    )

    # Filter by NATIVE
    native_curves = library.list_by_source(CurveSource.NATIVE)
    assert len(native_curves) == 1
    assert native_curves[0].id == "sine_native"

    # Filter by CUSTOM
    custom_curves = library.list_by_source(CurveSource.CUSTOM)
    assert len(custom_curves) == 1
    assert custom_curves[0].id == "cosine_custom"


def test_curve_library_duplicate_id_raises_error() -> None:
    """Test registering duplicate curve ID raises error."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    curve_def = CurveDefinition(
        id="duplicate_test",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
    )

    library.register(curve_def)

    # Try to register same ID again
    with pytest.raises(ValueError, match="already registered"):
        library.register(curve_def)


def test_curve_library_has_curve() -> None:
    """Test checking if library has a curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    library.register(
        CurveDefinition(
            id="test_curve",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    assert library.has("test_curve") is True
    assert library.has("nonexistent") is False


def test_curve_library_count() -> None:
    """Test getting count of curves in library."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    assert library.count() == 0

    library.register(
        CurveDefinition(
            id="curve1",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    assert library.count() == 1

    library.register(
        CurveDefinition(
            id="curve2",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.RAMP.value,
        )
    )

    assert library.count() == 2


def test_curve_library_clear() -> None:
    """Test clearing all curves from library."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    library.register(
        CurveDefinition(
            id="curve1",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    assert library.count() == 1

    library.clear()

    assert library.count() == 0
    assert library.get("curve1") is None


def test_curve_library_load_from_json_dict() -> None:
    """Test loading curves from JSON dictionary."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()

    curves_data = [
        {
            "id": "sine_smooth",
            "source": "native",
            "base_curve": "sine",
            "description": "Smooth sine wave",
        },
        {
            "id": "ramp_fast",
            "source": "native",
            "base_curve": "ramp",
            "description": "Fast ramp",
        },
    ]

    library.load_from_dict(curves_data)

    assert library.count() == 2
    assert library.has("sine_smooth")
    assert library.has("ramp_fast")


def test_curve_library_export_to_dict() -> None:
    """Test exporting curves to JSON dictionary."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()

    library.register(
        CurveDefinition(
            id="test_curve",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            description="Test curve",
        )
    )

    exported = library.export_to_dict()

    assert len(exported) == 1
    assert exported[0]["id"] == "test_curve"
    assert exported[0]["source"] == "native"
    assert exported[0]["base_curve"] == "sine"
