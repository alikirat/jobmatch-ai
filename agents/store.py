"""Key/value stores backing the scoring pipeline's job cache and the backend's resume store.

JsonStore is a local file-backed store used by default in tests and as a lightweight
fallback. MongoStore is the production-grade, MongoDB-backed implementation. Both expose
the same synchronous get/put shape, so either can be passed to `run_scoring_pipeline` or
wired into the FastAPI dependencies with no other call-site changes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, key: str) -> dict | None:
        return self._read_all().get(key)

    def put(self, key: str, value: dict) -> None:
        data = self._read_all()
        data[key] = value
        self._write_all(data)

    def list_all(self) -> list[dict]:
        return list(self._read_all().values())

    def _read_all(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def _write_all(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))


class MongoStore:
    """MongoDB-backed key/value store with the same get/put shape as JsonStore.

    Motor's client is async-only, but get/put here stay synchronous so this is a drop-in
    replacement for JsonStore at existing call sites (the scoring pipeline, the FastAPI
    routes) with no changes required there. Each instance owns a private event loop and
    lazily creates its motor client on that loop, so the client is never driven from more
    than one loop over its lifetime.
    """

    def __init__(self, uri: str, database: str, collection: str) -> None:
        self._uri = uri
        self._database = database
        self._collection_name = collection
        self._loop = asyncio.new_event_loop()
        self._client: Any = None
        self._collection: Any = None

    def get(self, key: str) -> dict | None:
        return self._loop.run_until_complete(self._get(key))

    def put(self, key: str, value: dict) -> None:
        self._loop.run_until_complete(self._put(key, value))

    def list_all(self) -> list[dict]:
        return self._loop.run_until_complete(self._list_all())

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._loop.close()

    async def _get_collection(self) -> Any:
        if self._collection is None:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._client = AsyncIOMotorClient(self._uri)
            self._collection = self._client[self._database][self._collection_name]
        return self._collection

    async def _get(self, key: str) -> dict | None:
        collection = await self._get_collection()
        document = await collection.find_one({"_id": key})
        if document is None:
            return None
        document = dict(document)
        document.pop("_id", None)
        return document

    async def _put(self, key: str, value: dict) -> None:
        collection = await self._get_collection()
        await collection.replace_one({"_id": key}, {"_id": key, **value}, upsert=True)

    async def _list_all(self) -> list[dict]:
        collection = await self._get_collection()
        documents = await collection.find({}).to_list(length=None)
        results = []
        for document in documents:
            document = dict(document)
            document.pop("_id", None)
            results.append(document)
        return results
