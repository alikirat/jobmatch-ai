"""Runs Ali's real resume through the full scoring pipeline against realistic job postings.

Not part of the mock-based unit suite (see test_scoring_pipeline.py) -- this validates the
pipeline end to end against production-shaped data, using the same scripted LLM client pattern.
Run with `pytest -s agents/tests/test_real_resume_pipeline.py` to see the printed results.
"""

from __future__ import annotations

import json

from agents.store import JsonStore
from agents.workflows.scoring_pipeline import run_scoring_pipeline


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


FULL_STACK_ENGINEER_POSTING = {
    "title": "Full Stack Engineer",
    "company": "Meridian Labs",
    "location": "Remote (US)",
    "employment_type": "Full-time",
    "work_arrangement": "Remote",
    "years_required": "1-3 years of experience",
    "salary_range": "$95,000 - $125,000 USD",
    "required_skills": ["React", "Node.js", "TypeScript", "MongoDB", "REST APIs", "Git"],
    "nice_to_have_skills": ["Docker", "GraphQL", "AWS"],
    "description": (
        "Meridian Labs is hiring a Full Stack Engineer to build and ship features across our "
        "React/TypeScript frontend and Node.js/MongoDB backend. You'll work closely with "
        "product and design in a small, fast-moving team."
    ),
    "job_id": "meridian-fullstack-001",
}

SOFTWARE_ENGINEER_POSTING = {
    "title": "Software Engineer",
    "company": "Bluecrest Systems",
    "location": "Austin, TX",
    "employment_type": "Full-time",
    "work_arrangement": "Hybrid (3 days onsite)",
    "years_required": "3+ years of experience",
    "salary_range": "$110,000 - $140,000 USD",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes"],
    "nice_to_have_skills": ["Docker", "Terraform", "React"],
    "description": (
        "Bluecrest Systems is looking for a Software Engineer to build backend services on "
        "Python/FastAPI, deployed on AWS/Kubernetes, powering our internal data platform."
    ),
    "job_id": "bluecrest-swe-014",
}

AI_AUTOMATION_ENGINEER_POSTING = {
    "title": "AI/Automation Engineer",
    "company": "Northstar AI",
    "location": "Remote",
    "employment_type": "Contract",
    "work_arrangement": "Remote (Anywhere)",
    "years_required": "2+ years of experience",
    "salary_range": "$100,000 - $130,000 USD",
    "required_skills": ["Python", "Multi-agent systems", "REST APIs", "Docker", "Git"],
    "nice_to_have_skills": ["Google ADK", "LangChain", "Kubernetes"],
    "description": (
        "Northstar AI builds automation workflows and multi-agent LLM systems for internal ops "
        "teams. We're looking for an AI/Automation Engineer comfortable designing agent "
        "orchestration pipelines and shipping them as production APIs."
    ),
    "job_id": "northstar-aiauto-007",
}


def _store(tmp_path) -> JsonStore:
    return JsonStore(tmp_path / "processed_jobs.json")


def _print_result(posting_title: str, result: dict) -> None:
    print(f"\n=== {posting_title} ===")
    print(f"status: {result['status']}")

    ats = result["ats_gate_result"]
    print(f"ats_gate passed: {ats['passed']} (missing required: {ats['missing_required_skills']})")

    fit = result["semantic_fit_result"]
    if fit:
        print(f"fit_tier: {fit['fit_tier']}")
        print(f"matched_skills: {fit['matched_skills']}")
        print(f"missing_skills: {fit['missing_skills']}")

    gaps = result["gap_analysis_result"]
    if gaps:
        for gap in gaps["gaps"]:
            print(f"gap: {gap['skill']} -> {gap['classification']}")

    optimization = result["resume_optimization_result"]
    if optimization:
        for suggestion in optimization["suggestions"]:
            print(f"suggestion ({suggestion['skill']}): {suggestion['after']}")


def test_full_stack_engineer_posting_passes_gate_with_a_strong_fit(tmp_path, real_resume):
    client = _ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "strong",
                    "matched_skills": [
                        "react",
                        "node.js",
                        "typescript",
                        "mongodb",
                        "rest apis",
                        "git",
                        "docker",
                    ],
                    "missing_skills": ["graphql", "aws"],
                    "reasoning": (
                        "Meets all required skills with hands-on React/Node/MongoDB project "
                        "experience (Atlas Taxi); Docker experience covers part of the "
                        "nice-to-have list, but GraphQL and AWS are unaddressed."
                    ),
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "graphql",
                            "classification": "real_gap",
                            "reasoning": "No GraphQL API work appears anywhere in the resume.",
                        },
                        {
                            "skill": "aws",
                            "classification": "real_gap",
                            "reasoning": (
                                "Docker experience does not imply AWS deployment experience; no "
                                "cloud infrastructure work is mentioned."
                            ),
                        },
                    ]
                }
            ),
        ]
    )

    result = run_scoring_pipeline(
        FULL_STACK_ENGINEER_POSTING, real_resume, store=_store(tmp_path), llm_client=client
    )
    _print_result(FULL_STACK_ENGINEER_POSTING["title"], result)

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "strong"
    assert result["semantic_fit_result"]["missing_skills"] == ["graphql", "aws"]
    assert {gap["skill"]: gap["classification"] for gap in result["gap_analysis_result"]["gaps"]} == {
        "graphql": "real_gap",
        "aws": "real_gap",
    }
    assert result["resume_optimization_result"]["suggestions"] == []
    assert len(client.calls) == 2


def test_software_engineer_posting_fails_ats_gate_on_missing_cloud_skills(tmp_path, real_resume):
    result = run_scoring_pipeline(
        SOFTWARE_ENGINEER_POSTING,
        real_resume,
        store=_store(tmp_path),
        llm_client=_ExplodingLLMClient(),
    )
    _print_result(SOFTWARE_ENGINEER_POSTING["title"], result)

    assert result["status"] == "ats_gate_failed"
    assert result["ats_gate_result"]["passed"] is False
    assert result["ats_gate_result"]["missing_required_skills"] == ["postgresql", "aws", "kubernetes"]
    assert result["ats_gate_result"]["years_requirement_met"] is False
    assert result["semantic_fit_result"] is None
    assert result["gap_analysis_result"] is None
    assert result["resume_optimization_result"] is None


def test_ai_automation_engineer_posting_surfaces_a_fixable_gap_and_optimization(tmp_path, real_resume):
    client = _ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "strong",
                    "matched_skills": [
                        "python",
                        "multi-agent systems",
                        "rest apis",
                        "docker",
                        "git",
                        "google adk",
                    ],
                    "missing_skills": ["langchain", "kubernetes"],
                    "reasoning": (
                        "Strong match on core requirements plus direct Google ADK multi-agent "
                        "experience (JobMatch AI, School Dropout Prevention system); LangChain "
                        "and Kubernetes are not directly evidenced."
                    ),
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "langchain",
                            "classification": "fixable",
                            "reasoning": (
                                "Candidate has built multiple multi-agent orchestration systems "
                                "with Google ADK and the Claude API -- directly transferable to "
                                "LangChain's agent framework even though LangChain itself isn't "
                                "named."
                            ),
                        },
                        {
                            "skill": "kubernetes",
                            "classification": "real_gap",
                            "reasoning": (
                                "Only Docker containerization is mentioned; no evidence of "
                                "container orchestration at the Kubernetes level."
                            ),
                        },
                    ]
                }
            ),
            json.dumps(
                {
                    "suggestions": [
                        {
                            "skill": "langchain",
                            "edit_type": "rephrase",
                            "before": (
                                "Built JobMatch AI, a multi-agent job search assistant using "
                                "Google ADK 2.0, with ATS keyword gating, LLM-based semantic "
                                "scoring, and automated resume optimization"
                            ),
                            "after": (
                                "Built JobMatch AI, a multi-agent LLM orchestration system "
                                "(Google ADK 2.0) with agent-to-agent handoffs, ATS keyword "
                                "gating, LLM-based semantic scoring, and automated resume "
                                "optimization -- directly transferable to LangChain-style agent "
                                "frameworks"
                            ),
                            "rationale": (
                                "Surfaces existing multi-agent orchestration experience in "
                                "framework-agnostic terms so it reads as directly relevant to "
                                "LangChain."
                            ),
                        }
                    ]
                }
            ),
        ]
    )

    result = run_scoring_pipeline(
        AI_AUTOMATION_ENGINEER_POSTING, real_resume, store=_store(tmp_path), llm_client=client
    )
    _print_result(AI_AUTOMATION_ENGINEER_POSTING["title"], result)

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "strong"
    assert result["semantic_fit_result"]["missing_skills"] == ["langchain", "kubernetes"]

    gaps_by_skill = {gap["skill"]: gap["classification"] for gap in result["gap_analysis_result"]["gaps"]}
    assert gaps_by_skill == {"langchain": "fixable", "kubernetes": "real_gap"}

    suggestions = result["resume_optimization_result"]["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["skill"] == "langchain"
    assert len(client.calls) == 3
