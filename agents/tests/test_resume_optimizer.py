import json

import pytest
from pydantic import ValidationError

from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.nodes.optimize.resume_optimizer import resume_optimizer


class _StubLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.response


def _gap_analysis_result(gaps: list[dict]) -> dict:
    return {"gaps": gaps}


def test_produces_suggestions_only_for_fixable_gaps(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    gap_result = _gap_analysis_result(
        [
            {
                "skill": "kubernetes",
                "classification": "fixable",
                "reasoning": "Docker-based CI/CD and AWS deployment experience is adjacent.",
            },
            {
                "skill": "terraform",
                "classification": "real_gap",
                "reasoning": "No infrastructure-as-code experience anywhere in the resume.",
            },
        ]
    )
    stub_response = json.dumps(
        {
            "suggestions": [
                {
                    "skill": "kubernetes",
                    "edit_type": "rephrase",
                    "before": "Introduced a Docker-based CI/CD pipeline, reducing deployment "
                    "time from 45 minutes to 6 minutes",
                    "after": "Introduced a Docker and container-orchestration-based CI/CD "
                    "pipeline, reducing deployment time from 45 minutes to 6 minutes",
                    "rationale": "Surfaces existing container/orchestration-adjacent "
                    "experience using the posting's Kubernetes terminology.",
                }
            ]
        }
    )
    client = _StubLLMClient(stub_response)

    result = resume_optimizer(sample_resume, gap_result, normalized, llm_client=client)

    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["skill"] == "kubernetes"
    call = client.calls[0]
    # terraform is a real_gap — it must never reach the LLM's fixable-gaps list
    assert "terraform" not in call["user_prompt"].lower()
    assert "kubernetes" in call["user_prompt"].lower()


def test_skips_llm_call_when_no_fixable_gaps(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    gap_result = _gap_analysis_result(
        [
            {"skill": "kafka", "classification": "real_gap", "reasoning": "x"},
            {"skill": "graphql", "classification": "borderline", "reasoning": "y"},
        ]
    )
    client = _StubLLMClient("should not be called")

    result = resume_optimizer(sample_resume, gap_result, normalized, llm_client=client)

    assert result["suggestions"] == []
    assert len(client.calls) == 0


def test_system_prompt_explicitly_forbids_fabricating_content(sample_resume, sample_job_posting):
    """The LLM must be instructed never to invent skills/experience — this is the anti-fabrication guardrail."""
    normalized = normalize_posting(sample_job_posting)
    gap_result = _gap_analysis_result(
        [{"skill": "kubernetes", "classification": "fixable", "reasoning": "x"}]
    )
    client = _StubLLMClient(json.dumps({"suggestions": []}))

    resume_optimizer(sample_resume, gap_result, normalized, llm_client=client)

    system_prompt = client.calls[0]["system_prompt"].lower()
    assert "never invent" in system_prompt or "must never invent" in system_prompt
    assert "fabricate" in system_prompt
    assert "already present" in system_prompt


def test_raises_on_llm_output_that_fails_schema_validation(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    gap_result = _gap_analysis_result(
        [{"skill": "kubernetes", "classification": "fixable", "reasoning": "x"}]
    )
    client = _StubLLMClient(
        json.dumps(
            {
                "suggestions": [
                    {
                        "skill": "kubernetes",
                        "edit_type": "add_new_bullet",
                        "before": "x",
                        "after": "y",
                        "rationale": "z",
                    }
                ]
            }
        )
    )

    with pytest.raises(ValidationError):
        resume_optimizer(sample_resume, gap_result, normalized, llm_client=client)
