import json

from app.dependencies import get_llm_client
from app.main import app

from .conftest import ExplodingLLMClient, ScriptedLLMClient


def test_score_with_inline_resume_and_ats_gate_failure(client, sample_resume, sample_job_posting):
    app.dependency_overrides[get_llm_client] = lambda: ExplodingLLMClient()

    response = client.post(
        "/score", json={"posting": sample_job_posting, "resume": sample_resume}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ats_gate_failed"
    assert body["ats_gate_result"]["passed"] is False
    assert "kubernetes" in body["ats_gate_result"]["missing_required_skills"]
    assert body["semantic_fit_result"] is None


def test_score_with_resume_id_runs_full_pipeline_when_ats_gate_passes(
    client, sample_resume, sample_job_posting
):
    resume_with_kubernetes = {
        **sample_resume,
        "skills": [*sample_resume["skills"], "Kubernetes"],
    }
    upload = client.post("/resumes", json=resume_with_kubernetes)
    resume_id = upload.json()["resume_id"]

    scripted_client = ScriptedLLMClient(
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
    app.dependency_overrides[get_llm_client] = lambda: scripted_client

    response = client.post(
        "/score", json={"posting": sample_job_posting, "resume_id": resume_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scored"
    assert body["semantic_fit_result"]["fit_tier"] == "strong"
    assert body["gap_analysis_result"] == {"gaps": []}
    assert len(scripted_client.calls) == 1


def test_score_requires_exactly_one_resume_source(client, sample_job_posting, sample_resume):
    missing_both = client.post("/score", json={"posting": sample_job_posting})
    assert missing_both.status_code == 422

    both_provided = client.post(
        "/score",
        json={
            "posting": sample_job_posting,
            "resume": sample_resume,
            "resume_id": "some-id",
        },
    )
    assert both_provided.status_code == 422


def test_score_with_unknown_resume_id_returns_404(client, sample_job_posting):
    response = client.post(
        "/score", json={"posting": sample_job_posting, "resume_id": "does-not-exist"}
    )

    assert response.status_code == 404
