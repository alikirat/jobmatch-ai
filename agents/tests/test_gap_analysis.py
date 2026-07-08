import json

import pytest
from pydantic import ValidationError

from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.nodes.score.gap_analysis import gap_analysis


class _StubLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.response


def _fit_result(missing_skills: list[str]) -> dict:
    return {
        "fit_tier": "moderate",
        "matched_skills": ["python", "fastapi"],
        "missing_skills": missing_skills,
        "reasoning": "n/a",
    }


def test_classifies_each_missing_skill(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    fit_result = _fit_result(["kubernetes"])
    stub_response = json.dumps(
        {
            "gaps": [
                {
                    "skill": "kubernetes",
                    "classification": "fixable",
                    "reasoning": "Resume shows Docker-based CI/CD and AWS deployment "
                    "experience adjacent to Kubernetes.",
                }
            ]
        }
    )
    client = _StubLLMClient(stub_response)

    result = gap_analysis(sample_resume, normalized, fit_result, llm_client=client)

    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["skill"] == "kubernetes"
    assert result["gaps"][0]["classification"] == "fixable"
    assert len(client.calls) == 1


def test_skips_llm_call_when_no_missing_skills(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    fit_result = _fit_result([])
    client = _StubLLMClient("should not be called")

    result = gap_analysis(sample_resume, normalized, fit_result, llm_client=client)

    assert result["gaps"] == []
    assert len(client.calls) == 0


def test_prompt_carries_missing_skills_and_resume_context(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    fit_result = _fit_result(["kubernetes"])
    stub_response = json.dumps(
        {"gaps": [{"skill": "kubernetes", "classification": "real_gap", "reasoning": "x"}]}
    )
    client = _StubLLMClient(stub_response)

    gap_analysis(sample_resume, normalized, fit_result, llm_client=client)

    call = client.calls[0]
    assert "kubernetes" in call["user_prompt"].lower()
    assert "Jordan Alvarez" in call["user_prompt"]


def test_raises_on_invalid_classification_value(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    fit_result = _fit_result(["kubernetes"])
    client = _StubLLMClient(
        json.dumps(
            {"gaps": [{"skill": "kubernetes", "classification": "not_a_real_option", "reasoning": "x"}]}
        )
    )

    with pytest.raises(ValidationError):
        gap_analysis(sample_resume, normalized, fit_result, llm_client=client)
