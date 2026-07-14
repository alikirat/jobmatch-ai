"""AdzunaClient tests.

The correctness tests below fake out the HTTP session entirely, so they run without a
network connection or real credentials, the same way test_store.py fakes motor's client.

The test at the bottom is a real integration test against the live Adzuna API. It's
skipped unless ADZUNA_APP_ID and ADZUNA_APP_KEY are set in the environment (e.g. by
sourcing a `.env`) -- same pattern as the MongoDB integration test in test_store.py.
"""

from __future__ import annotations

import json
import os

import pytest

from agents.ingest import adzuna_client as adzuna_client_module
from agents.ingest.adzuna_client import AdzunaClient, AdzunaError, AdzunaRateLimitError
from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.schemas import RawJobPosting

ADZUNA_RESULT_FIXTURE = {
    "id": "123456789",
    "title": "Full Stack Engineer",
    "company": {"display_name": "Acme Corp"},
    "location": {"display_name": "Austin, TX", "area": ["US", "Texas", "Austin"]},
    "description": (
        "We are looking for a Full Stack Engineer to join our remote-first team building "
        "React and Node.js applications."
    ),
    "redirect_url": "https://www.adzuna.com/details/123456789",
    "salary_min": 95000.0,
    "salary_max": 125000.0,
    "contract_time": "full_time",
    "contract_type": "permanent",
    "category": {"label": "IT Jobs"},
    "created": "2026-07-01T12:00:00Z",
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls: list[dict] = []

    def get(self, url: str, *, params: dict, timeout: float):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self._response


def test_search_maps_adzuna_results_into_the_raw_job_posting_shape():
    session = _FakeSession(_FakeResponse(200, {"results": [ADZUNA_RESULT_FIXTURE]}))
    client = AdzunaClient(app_id="test-id", app_key="test-key", session=session)

    postings = client.search(keywords="full stack engineer", location="Austin, TX")

    assert len(postings) == 1
    posting = postings[0]
    assert posting["title"] == "Full Stack Engineer"
    assert posting["company"] == "Acme Corp"
    assert posting["location"] == "Austin, TX"
    assert posting["work_arrangement"] == "Remote"
    assert posting["salary_range"] == "$95,000 - $125,000 USD"
    assert posting["job_id"] == "adzuna:123456789"
    assert posting["required_skills"] == []
    assert posting["years_required"] is None

    # Must be consumable by RawJobPosting/normalize_posting exactly as-is.
    RawJobPosting.model_validate(posting)
    normalized = normalize_posting(posting)
    assert normalized["title"] == "Full Stack Engineer"
    assert normalized["work_arrangement"] == "remote"
    assert normalized["salary_min"] == 95000
    assert normalized["salary_max"] == 125000
    assert normalized["salary_currency"] == "USD"


def test_search_sends_expected_query_params_and_page_number_in_the_url():
    session = _FakeSession(_FakeResponse(200, {"results": []}))
    client = AdzunaClient(app_id="id123", app_key="key456", session=session)

    postings = client.search(keywords="python", location="Remote", results_per_page=5, page=2)

    assert postings == []
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://api.adzuna.com/v1/api/jobs/us/search/2"
    assert call["params"]["app_id"] == "id123"
    assert call["params"]["app_key"] == "key456"
    assert call["params"]["what"] == "python"
    assert call["params"]["where"] == "Remote"
    assert call["params"]["results_per_page"] == 5


def test_search_omits_optional_params_when_not_provided():
    session = _FakeSession(_FakeResponse(200, {"results": []}))
    client = AdzunaClient(app_id="id", app_key="key", session=session)

    client.search()

    call = session.calls[0]
    assert "what" not in call["params"]
    assert "where" not in call["params"]
    assert call["url"] == "https://api.adzuna.com/v1/api/jobs/us/search/1"


def test_search_raises_rate_limit_error_on_429_without_crashing():
    session = _FakeSession(_FakeResponse(429, text="Too Many Requests"))
    client = AdzunaClient(app_id="id", app_key="key", session=session)

    with pytest.raises(AdzunaRateLimitError, match="rate limit"):
        client.search(keywords="python")


def test_search_raises_adzuna_error_on_other_non_200_status():
    session = _FakeSession(_FakeResponse(500, text="Internal Server Error"))
    client = AdzunaClient(app_id="id", app_key="key", session=session)

    with pytest.raises(AdzunaError, match="500"):
        client.search(keywords="python")


def test_missing_credentials_raise_a_clear_error(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    # Avoid picking up a real local .env, so this test is deterministic on any machine.
    monkeypatch.setattr(adzuna_client_module, "load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(AdzunaError, match="ADZUNA_APP_ID"):
        AdzunaClient()


def test_credentials_are_read_from_the_environment_when_not_passed_explicitly(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "env-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "env-key")
    monkeypatch.setattr(adzuna_client_module, "load_dotenv", lambda *args, **kwargs: None)
    session = _FakeSession(_FakeResponse(200, {"results": []}))

    client = AdzunaClient(session=session)
    client.search()

    assert session.calls[0]["params"]["app_id"] == "env-id"
    assert session.calls[0]["params"]["app_key"] == "env-key"


INTEGRATION_APP_ID = os.environ.get("ADZUNA_APP_ID")
INTEGRATION_APP_KEY = os.environ.get("ADZUNA_APP_KEY")


@pytest.mark.integration
@pytest.mark.skipif(
    not (INTEGRATION_APP_ID and INTEGRATION_APP_KEY),
    reason=(
        "requires ADZUNA_APP_ID and ADZUNA_APP_KEY to be set "
        "(export/source your .env) to hit the real Adzuna API"
    ),
)
def test_search_against_the_real_adzuna_api():
    client = AdzunaClient()
    postings = client.search(keywords="software engineer", location="Remote", results_per_page=1)

    assert isinstance(postings, list)
    if postings:
        RawJobPosting.model_validate(postings[0])
