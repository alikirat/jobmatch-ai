"""Local JSON-file key/value store.

Placeholder for MongoDB — same get/put shape, so callers (the scoring pipeline's job cache,
the backend's resume store, etc.) can swap to a Mongo-backed store later without changing
call sites.
"""

from __future__ import annotations

import json
from pathlib import Path


class JsonStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, key: str) -> dict | None:
        return self._read_all().get(key)

    def put(self, key: str, value: dict) -> None:
        data = self._read_all()
        data[key] = value
        self._write_all(data)

    def _read_all(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def _write_all(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))
