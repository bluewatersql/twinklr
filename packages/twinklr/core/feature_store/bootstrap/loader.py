"""Reference data loader for the SQLite feature store.

Scans a directory for JSON files and upserts each into the ``reference_data``
table.  Missing or empty directories are handled gracefully (returns 0).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class ReferenceDataLoader:
    """Loads reference JSON files into the ``reference_data`` table.

    Args:
        conn: Open SQLite connection with the ``reference_data`` table present.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def load_directory(self, directory: Path) -> int:
        """Scan *directory* for ``*.json`` files and upsert each into the store.

        The ``data_key`` for each file is its stem (filename without extension).
        If the JSON contains a top-level ``"version"`` key its value is stored
        in the ``version`` column; otherwise the version is stored as an empty
        string.

        Args:
            directory: Path to scan.  If the directory does not exist or
                contains no JSON files, 0 is returned without raising.

        Returns:
            Number of files loaded (rows upserted).
        """
        if not directory.is_dir():
            return 0

        json_files = sorted(directory.glob("*.json"))
        if not json_files:
            return 0

        rows: list[tuple[str, str, str]] = []
        for path in json_files:
            raw = path.read_text(encoding="utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            version = ""
            if isinstance(data, dict):
                version = str(data.get("version", ""))

            rows.append((path.stem, raw, version))

        if not rows:
            return 0

        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO reference_data (data_key, data_json, version) "
                "VALUES (?, ?, ?)",
                rows,
            )

        return len(rows)
