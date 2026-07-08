import json

import pytest
from pydantic import ValidationError

from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.nodes.score.ats_gate_check import ats_gate_check
from agents.nodes.score.semantic_fit_scoring import semantic_fit_scoring


class _StubLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.response


def test_parses_llm_response_into_schema(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    ats_result = ats_gate_check(sample_resume, normalized)
    stub_response = json.dumps(
        {
            "fit_tier": "moderate",
            "matched_skills": ["python", "fastapi", "postgresql", "docker", "aws"],
            "missing_skills": ["kubernetes"],
            "reasoning": "Meets all required skills except Kubernetes; strong adjacent "
            "container experience via Docker.",
        }
    )
    client = _StubLLMClient(stub_response)

    result = semantic_fit_scoring(sample_resume, normalized, ats_result, llm_client=client)

    assert result["fit_tier"] == "moderate"
    assert result["missing_skills"] == ["kubernetes"]
    assert "python" in result["matched_skills"]
    assert len(client.calls) == 1


def test_parses_response_wrapped_in_markdown_fence(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    ats_result = ats_gate_check(sample_resume, normalized)
    fenced_response = "```json\n" + json.dumps(
        {
            "fit_tier": "strong",
            "matched_skills": ["python"],
            "missing_skills": [],
            "reasoning": "All required skills met.",
        }
    ) + "\n```"
    client = _StubLLMClient(fenced_response)

    result = semantic_fit_scoring(sample_resume, normalized, ats_result, llm_client=client)

    assert result["fit_tier"] == "strong"
    assert result["missing_skills"] == []


def test_prompt_carries_weighting_guidance_and_full_context(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    ats_result = ats_gate_check(sample_resume, normalized)
    stub_response = json.dumps(
        {"fit_tier": "moderate", "matched_skills": [], "missing_skills": [], "reasoning": "n/a"}
    )
    client = _StubLLMClient(stub_response)

    semantic_fit_scoring(sample_resume, normalized, ats_result, llm_client=client)

    call = client.calls[0]
    assert "nice-to-have" in call["system_prompt"].lower()
    assert "must" in call["system_prompt"].lower()
    assert "Jordan Alvarez" in call["user_prompt"]
    assert "kubernetes" in call["user_prompt"].lower()


def test_raises_on_llm_output_that_fails_schema_validation(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)
    ats_result = ats_gate_check(sample_resume, normalized)
    client = _StubLLMClient(
        json.dumps(
            {"fit_tier": "amazing", "matched_skills": [], "missing_skills": [], "reasoning": "x"}
        )
    )

    with pytest.raises(ValidationError):
        semantic_fit_scoring(sample_resume, normalized, ats_result, llm_client=client)
