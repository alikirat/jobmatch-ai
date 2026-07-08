import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.store import JsonStore
from app.dependencies import get_job_store, get_resume_store
from app.main import app

FIXTURES_DIR = Path(__file__).parent.parent.parent / "agents" / "fixtures"


class ScriptedLLMClient:
    """Returns queued responses in order; blows up if called more times than scripted."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self._responses:
            raise AssertionError("LLM called more times than expected")
        return self._responses.pop(0)


class ExplodingLLMClient:
    """Fails the test immediately if the route ever calls the LLM."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("LLM should not have been called")


@pytest.fixture
def sample_resume() -> dict:
    return json.loads((FIXTURES_DIR / "resume.sample.json").read_text())


@pytest.fixture
def sample_job_posting() -> dict:
    return json.loads((FIXTURES_DIR / "job_posting.sample.json").read_text())


@pytest.fixture
def client(tmp_path):
    job_store = JsonStore(tmp_path / "processed_jobs.json")
    resume_store = JsonStore(tmp_path / "resumes.json")

    app.dependency_overrides[get_job_store] = lambda: job_store
    app.dependency_overrides[get_resume_store] = lambda: resume_store

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
