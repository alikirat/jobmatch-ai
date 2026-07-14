"""FastAPI dependency providers.

Tests override these via `app.dependency_overrides` to point stores at a tmp_path
JsonStore and to inject a stub LLM client, so the test suite never touches a real
MongoDB instance or a live API key.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from fastapi import HTTPException

from agents.ingest.adzuna_client import AdzunaClient, AdzunaError
from agents.llm.client import LLMClient
from agents.store import MongoStore

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "jobmatch")


def get_job_store() -> Iterator[MongoStore]:
    store = MongoStore(uri=MONGODB_URI, database=MONGODB_DATABASE, collection="processed_jobs")
    try:
        yield store
    finally:
        store.close()


def get_resume_store() -> Iterator[MongoStore]:
    store = MongoStore(uri=MONGODB_URI, database=MONGODB_DATABASE, collection="resumes")
    try:
        yield store
    finally:
        store.close()


def get_llm_client() -> LLMClient | None:
    return None


def get_adzuna_client() -> AdzunaClient:
    try:
        return AdzunaClient()
    except AdzunaError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
