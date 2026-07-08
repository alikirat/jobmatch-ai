import json

import pytest

from agents.workflows.scoring_pipeline import run_scoring_pipeline
from agents.store import JobStore


class _ScriptedLLMClient:
    """Returns queued responses in order; blows up if called more times than scripted."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self._responses:
            raise AssertionError("LLM called more times than expected")
        return self._responses.pop(0)


class _ExplodingLLMClient:
    """Fails the test immediately if the pipeline ever calls the LLM."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("LLM should not have been called")


def _store(tmp_path) -> JobStore:
    return JobStore(tmp_path / "processed_jobs.json")


def test_new_job_that_passes_ats_gate_runs_the_full_pipeline(
    tmp_path, sample_resume, sample_job_posting
):
    resume_with_kubernetes = {
        **sample_resume,
        "skills": [*sample_resume["skills"], "Kubernetes"],
    }
    client = _ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "strong",
                    "matched_skills": ["python", "fastapi", "postgresql", "docker", "aws", "kubernetes"],
                    "missing_skills": ["kafka"],
                    "reasoning": "Meets all required skills; missing only the nice-to-have Kafka.",
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "kafka",
                            "classification": "fixable",
                            "reasoning": "Built internal REST APIs and AWS deployments adjacent to messaging systems.",
                        }
                    ]
                }
            ),
            json.dumps(
                {
                    "suggestions": [
                        {
                            "skill": "kafka",
                            "edit_type": "rephrase",
                            "before": "Built internal REST APIs consumed by 5 downstream teams",
                            "after": "Built internal event-driven REST APIs consumed by 5 downstream teams",
                            "rationale": "Surfaces existing API integration experience using Kafka-adjacent terminology.",
                        }
                    ]
                }
            ),
        ]
    )
    store = _store(tmp_path)

    result = run_scoring_pipeline(
        sample_job_posting, resume_with_kubernetes, store=store, llm_client=client
    )

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "strong"
    assert result["gap_analysis_result"]["gaps"][0]["classification"] == "fixable"
    assert result["resume_optimization_result"]["suggestions"][0]["skill"] == "kafka"
    assert len(client.calls) == 3

    assert store.get(result["dedup_key"]) == result


def test_ats_gate_failure_skips_llm_nodes_and_caches_as_failed(
    tmp_path, sample_resume, sample_job_posting
):
    store = _store(tmp_path)

    result = run_scoring_pipeline(
        sample_job_posting, sample_resume, store=store, llm_client=_ExplodingLLMClient()
    )

    assert result["status"] == "ats_gate_failed"
    assert result["ats_gate_result"]["passed"] is False
    assert result["ats_gate_result"]["missing_required_skills"] == ["kubernetes"]
    assert result["semantic_fit_result"] is None
    assert result["gap_analysis_result"] is None
    assert result["resume_optimization_result"] is None

    assert store.get(result["dedup_key"]) == result


def test_previously_scored_job_is_returned_from_cache_without_rerunning_llm(
    tmp_path, sample_resume, sample_job_posting
):
    resume_with_kubernetes = {
        **sample_resume,
        "skills": [*sample_resume["skills"], "Kubernetes"],
    }
    store = _store(tmp_path)
    first_client = _ScriptedLLMClient(
        [
            json.dumps(
                {"fit_tier": "strong", "matched_skills": [], "missing_skills": [], "reasoning": "n/a"}
            ),
        ]
    )

    first_result = run_scoring_pipeline(
        sample_job_posting, resume_with_kubernetes, store=store, llm_client=first_client
    )
    assert first_result["status"] == "scored"

    second_result = run_scoring_pipeline(
        sample_job_posting, resume_with_kubernetes, store=store, llm_client=_ExplodingLLMClient()
    )

    assert second_result == first_result


def test_reposted_job_with_minor_text_differences_hits_cache(
    tmp_path, sample_resume, sample_job_posting
):
    store = _store(tmp_path)

    first_result = run_scoring_pipeline(
        sample_job_posting, sample_resume, store=store, llm_client=_ExplodingLLMClient()
    )
    assert first_result["status"] == "ats_gate_failed"

    reposted_posting = {
        **sample_job_posting,
        "title": f"  {sample_job_posting['title'].upper()}  ",
        "company": sample_job_posting["company"].lower(),
        "description": " ".join(sample_job_posting["description"].split()).upper(),
    }

    second_result = run_scoring_pipeline(
        reposted_posting, sample_resume, store=store, llm_client=_ExplodingLLMClient()
    )

    assert second_result == first_result
    assert second_result["dedup_key"] == first_result["dedup_key"]
