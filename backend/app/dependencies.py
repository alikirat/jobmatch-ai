"""FastAPI dependency providers.

Tests override these via `app.dependency_overrides` to point stores at a tmp_path and to
inject a stub LLM client, so the test suite never touches real files or a live API key.
"""

from __future__ import annotations

from pathlib import Path

from agents.llm.client import LLMClient
from agents.store import JsonStore

DATA_DIR = Path(__file__).parent.parent / "data"


def get_job_store() -> JsonStore:
    return JsonStore(DATA_DIR / "processed_jobs.json")


def get_resume_store() -> JsonStore:
    return JsonStore(DATA_DIR / "resumes.json")


def get_llm_client() -> LLMClient | None:
    return None
