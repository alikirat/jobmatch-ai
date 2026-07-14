from agents.ingest.adzuna_client import AdzunaError, AdzunaRateLimitError
from app.dependencies import get_adzuna_client, get_llm_client
from app.main import app

from .conftest import ExplodingLLMClient


class _FakeAdzunaClient:
    def __init__(self, postings: list[dict]):
        self._postings = postings
        self.calls: list[dict] = []

    def search(self, *, keywords, location, results_per_page, page):
        self.calls.append(
            {
                "keywords": keywords,
                "location": location,
                "results_per_page": results_per_page,
                "page": page,
            }
        )
        return self._postings


class _RateLimitedAdzunaClient:
    def search(self, **kwargs):
        raise AdzunaRateLimitError("Adzuna API rate limit exceeded (HTTP 429). Wait before retrying.")


class _FailingAdzunaClient:
    def search(self, **kwargs):
        raise AdzunaError("Adzuna API request failed with HTTP 500: boom")


def _posting(job_id: str, title: str, sample_job_posting: dict) -> dict:
    return {**sample_job_posting, "job_id": job_id, "title": title}


def test_ingest_adzuna_runs_each_fetched_posting_through_the_scoring_pipeline(
    client, sample_resume, sample_job_posting
):
    postings = [
        _posting("adzuna:1", "Backend Engineer", sample_job_posting),
        _posting("adzuna:2", "Platform Engineer", sample_job_posting),
    ]
    app.dependency_overrides[get_adzuna_client] = lambda: _FakeAdzunaClient(postings)
    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()

    response = client.post(
        "/ingest/adzuna",
        json={"keywords": "backend engineer", "location": "Remote", "resume": sample_resume},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fetched"] == 2
    assert {result["status"] for result in body["results"]} == {"ats_gate_failed"}
    assert {result["dedup_key"] for result in body["results"]} == {"id:adzuna:1", "id:adzuna:2"}


def test_ingest_adzuna_forwards_search_parameters_to_the_client(
    client, sample_resume, sample_job_posting
):
    fake_client = _FakeAdzunaClient([_posting("adzuna:1", "Backend Engineer", sample_job_posting)])
    app.dependency_overrides[get_adzuna_client] = lambda: fake_client
    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()

    client.post(
        "/ingest/adzuna",
        json={
            "keywords": "python",
            "location": "Austin, TX",
            "results_per_page": 5,
            "page": 2,
            "resume": sample_resume,
        },
    )

    assert fake_client.calls == [
        {"keywords": "python", "location": "Austin, TX", "results_per_page": 5, "page": 2}
    ]


def test_ingest_adzuna_respects_the_dedup_cache_across_requests(
    client, sample_resume, sample_job_posting
):
    postings = [_posting("adzuna:1", "Backend Engineer", sample_job_posting)]
    app.dependency_overrides[get_adzuna_client] = lambda: _FakeAdzunaClient(postings)
    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()

    first = client.post(
        "/ingest/adzuna", json={"keywords": "backend", "resume": sample_resume}
    )
    second = client.post(
        "/ingest/adzuna", json={"keywords": "backend", "resume": sample_resume}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["results"] == second.json()["results"]


def test_ingest_adzuna_returns_429_when_adzuna_rate_limits(client, sample_resume):
    app.dependency_overrides[get_adzuna_client] = lambda: _RateLimitedAdzunaClient()

    response = client.post("/ingest/adzuna", json={"keywords": "python", "resume": sample_resume})

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_ingest_adzuna_returns_502_on_other_adzuna_failures(client, sample_resume):
    app.dependency_overrides[get_adzuna_client] = lambda: _FailingAdzunaClient()

    response = client.post("/ingest/adzuna", json={"keywords": "python", "resume": sample_resume})

    assert response.status_code == 502


def test_ingest_adzuna_requires_exactly_one_resume_source(client, sample_resume):
    app.dependency_overrides[get_adzuna_client] = lambda: _FakeAdzunaClient([])

    missing_both = client.post("/ingest/adzuna", json={"keywords": "python"})
    assert missing_both.status_code == 422

    both_provided = client.post(
        "/ingest/adzuna",
        json={"keywords": "python", "resume": sample_resume, "resume_id": "some-id"},
    )
    assert both_provided.status_code == 422


def test_ingest_adzuna_with_unknown_resume_id_returns_404(client):
    app.dependency_overrides[get_adzuna_client] = lambda: _FakeAdzunaClient([])

    response = client.post(
        "/ingest/adzuna", json={"keywords": "python", "resume_id": "does-not-exist"}
    )

    assert response.status_code == 404
