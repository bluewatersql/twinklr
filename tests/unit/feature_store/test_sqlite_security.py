"""Tests for SEC-05: SQL identifier validation in SQLiteFeatureStore."""

from __future__ import annotations

import pytest

from twinklr.core.feature_store.backends.sqlite import _validate_identifier


class TestSqlIdentifierValidation:
    """Verify SQL identifier validation prevents injection."""

    def test_valid_identifiers(self) -> None:
        """Normal column/table names should pass validation."""
        valid = ["name", "song_title", "Feature1", "_private", "col_123"]
        for ident in valid:
            assert _validate_identifier(ident) == ident

    def test_rejects_sql_injection(self) -> None:
        """SQL injection attempts must be rejected."""
        malicious = [
            "name; DROP TABLE--",
            "col OR 1=1",
            "name' UNION SELECT",
            "table.column",
            "1; DELETE FROM",
            "name\x00",
        ]
        for ident in malicious:
            with pytest.raises(ValueError, match="Invalid SQL identifier"):
                _validate_identifier(ident)

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("")

    def test_rejects_starts_with_number(self) -> None:
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("123col")

    def test_rejects_special_characters(self) -> None:
        specials = ["col-name", "col.name", "col name", "col@name", "col$name"]
        for ident in specials:
            with pytest.raises(ValueError, match="Invalid SQL identifier"):
                _validate_identifier(ident)
