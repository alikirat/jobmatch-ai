import json

from app.dependencies import get_llm_client
from app.main import app

from .conftest import ExplodingLLMClient, ScriptedLLMClient


def _score(client, posting, resume):
    response = client.post("/score", json={"posting": posting, "resume": resume})
    assert response.status_code == 200
    return response.json()


def test_jobs_queue_is_empty_when_nothing_has_been_scored(client):
    response = client.get("/jobs/queue")

    assert response.status_code == 200
    assert response.json() == {"jobs": []}


def test_jobs_queue_returns_only_scored_jobs_pending_review(
    client, sample_resume, sample_job_posting
):
    resume_with_kubernetes = {**sample_resume, "skills": [*sample_resume["skills"], "Kubernetes"]}

    app.dependency_overrides[get_llm_client] = lambda: ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "strong",
                    "matched_skills": ["python", "kubernetes"],
                    "missing_skills": [],
                    "reasoning": "Meets all required skills.",
                }
            ),
        ]
    )
    scored = _score(client, sample_job_posting, resume_with_kubernetes)
    assert scored["status"] == "scored"

    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()
    failed_posting = {**sample_job_posting, "job_id": "posting-b", "title": "Different Title"}
    failed = _score(client, failed_posting, sample_resume)
    assert failed["status"] == "ats_gate_failed"

    response = client.get("/jobs/queue")

    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["dedup_key"] == scored["dedup_key"]
    assert jobs[0]["company"] == sample_job_posting["company"]
    assert jobs[0]["review_status"] == "pending"


def test_jobs_queue_excludes_jobs_already_swiped(client, sample_resume, sample_job_posting):
    resume_with_kubernetes = {**sample_resume, "skills": [*sample_resume["skills"], "Kubernetes"]}
    app.dependency_overrides[get_llm_client] = lambda: ScriptedLLMClient(
        [
            json.dumps(
                {"fit_tier": "strong", "matched_skills": [], "missing_skills": [], "reasoning": "n/a"}
            ),
        ]
    )
    scored = _score(client, sample_job_posting, resume_with_kubernetes)

    patch_response = client.patch(f"/jobs/{scored['dedup_key']}/status", json={"status": "swiped_left"})

    assert patch_response.status_code == 200
    assert patch_response.json()["review_status"] == "swiped_left"

    queue_response = client.get("/jobs/queue")
    assert queue_response.json() == {"jobs": []}


def test_get_job_detail_returns_the_full_pipeline_result(client, sample_resume, sample_job_posting):
    resume_with_kubernetes = {**sample_resume, "skills": [*sample_resume["skills"], "Kubernetes"]}
    app.dependency_overrides[get_llm_client] = lambda: ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "strong",
                    "matched_skills": ["python", "kubernetes"],
                    "missing_skills": [],
                    "reasoning": "Meets all required skills.",
                }
            ),
        ]
    )
    scored = _score(client, sample_job_posting, resume_with_kubernetes)

    response = client.get(f"/jobs/{scored['dedup_key']}")

    assert response.status_code == 200
    body = response.json()
    assert body["dedup_key"] == scored["dedup_key"]
    assert body["status"] == "scored"
    assert body["company"] == sample_job_posting["company"]
    assert body["normalized_posting"]["description"] == sample_job_posting["description"]
    assert body["gap_analysis_result"] == {"gaps": []}
    assert body["resume_optimization_result"] == {"suggestions": []}


def test_get_job_detail_with_unknown_job_id_returns_404(client):
    response = client.get("/jobs/does-not-exist")

    assert response.status_code == 404


def test_update_job_status_persists_across_requests(client, sample_resume, sample_job_posting):
    resume_with_kubernetes = {**sample_resume, "skills": [*sample_resume["skills"], "Kubernetes"]}
    app.dependency_overrides[get_llm_client] = lambda: ScriptedLLMClient(
        [
            json.dumps(
                {"fit_tier": "strong", "matched_skills": [], "missing_skills": [], "reasoning": "n/a"}
            ),
        ]
    )
    scored = _score(client, sample_job_posting, resume_with_kubernetes)

    client.patch(f"/jobs/{scored['dedup_key']}/status", json={"status": "swiped_right"})
    refetched = client.get("/jobs/queue")

    assert refetched.json() == {"jobs": []}


def test_update_job_status_with_unknown_job_id_returns_404(client):
    response = client.patch("/jobs/does-not-exist/status", json={"status": "swiped_right"})

    assert response.status_code == 404


def test_update_job_status_rejects_invalid_status_value(client, sample_resume, sample_job_posting):
    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()
    failed = _score(client, sample_job_posting, sample_resume)

    response = client.patch(f"/jobs/{failed['dedup_key']}/status", json={"status": "maybe"})

    assert response.status_code == 422
