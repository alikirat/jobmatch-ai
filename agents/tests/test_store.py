"""MongoStore tests.

The correctness tests below fake out motor's `AsyncIOMotorClient` entirely, so they run
without Docker or a network connection and exercise MongoStore's get/put contract the
same way the JsonStore tests do.

The tests at the bottom are real integration tests against a live MongoDB. They're
skipped unless `MONGODB_URI` is set in the environment (e.g. by sourcing a `.env` with
`docker compose up` running locally) — see the README for setup.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from agents.store import MongoStore


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.replace_one = AsyncMock(side_effect=self._replace_one)

    async def _find_one(self, query: dict) -> dict | None:
        document = self._docs.get(query["_id"])
        return dict(document) if document is not None else None

    async def _replace_one(self, query: dict, replacement: dict, upsert: bool = False) -> None:
        self._docs[query["_id"]] = dict(replacement)


class _FakeDatabase:
    def __init__(self, collection: _FakeCollection) -> None:
        self._collection = collection

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collection


class _FakeMotorClient:
    """Stands in for `motor.motor_asyncio.AsyncIOMotorClient`."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.collection = _FakeCollection()
        self.closed = False

    def __getitem__(self, name: str) -> _FakeDatabase:
        return _FakeDatabase(self.collection)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def mongo_store():
    with patch("motor.motor_asyncio.AsyncIOMotorClient", _FakeMotorClient):
        store = MongoStore(uri="mongodb://fake", database="testdb", collection="items")
        yield store
        store.close()


def test_get_returns_none_for_a_missing_key(mongo_store):
    assert mongo_store.get("missing") is None


def test_put_then_get_roundtrips_the_value(mongo_store):
    mongo_store.put("job-1", {"status": "scored"})
    assert mongo_store.get("job-1") == {"status": "scored"}


def test_put_overwrites_an_existing_value(mongo_store):
    mongo_store.put("job-1", {"status": "scored"})
    mongo_store.put("job-1", {"status": "ats_gate_failed"})
    assert mongo_store.get("job-1") == {"status": "ats_gate_failed"}


def test_get_does_not_leak_the_mongo_id_field(mongo_store):
    mongo_store.put("job-1", {"status": "scored"})
    assert "_id" not in mongo_store.get("job-1")


def test_close_closes_the_underlying_client(mongo_store):
    mongo_store.put("job-1", {"status": "scored"})  # forces client creation
    client = mongo_store._client
    mongo_store.close()
    assert client.closed is True


INTEGRATION_URI = os.environ.get("MONGODB_URI")


@pytest.mark.integration
@pytest.mark.skipif(
    not INTEGRATION_URI,
    reason=(
        "requires MONGODB_URI to point at a live MongoDB "
        "(run `docker compose up` and export/source your .env)"
    ),
)
def test_put_then_get_roundtrips_against_a_real_mongodb():
    store = MongoStore(uri=INTEGRATION_URI, database="jobmatch_test", collection="integration_test")
    try:
        store.put("integration-key", {"hello": "world"})
        assert store.get("integration-key") == {"hello": "world"}
    finally:
        store.close()
