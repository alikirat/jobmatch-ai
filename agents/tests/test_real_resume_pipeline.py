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

FENWICK_AI_AGENT_ENGINEER_POSTING = {
    "title": "AI Agent Engineer",
    "company": "Fenwick Robotics",
    "location": "Remote (US/EU)",
    "employment_type": "Full-time",
    "work_arrangement": "Remote",
    "years_required": "2+ years of experience",
    "salary_range": "$110,000 - $145,000 USD",
    "required_skills": ["Python", "Multi-agent systems", "REST APIs", "Docker", "Git", "FastAPI"],
    "nice_to_have_skills": ["Kubernetes", "LangChain", "AWS", "TypeScript"],
    "description": (
        "Fenwick Robotics is building an AI-native operations platform. We're looking for an AI "
        "Agent Engineer to design and ship multi-agent LLM workflows that automate internal ops "
        "tasks, expose them as production REST APIs, and run reliably in containerized "
        "environments. You'll own the agent orchestration layer end to end, from prompt design "
        "to deployment."
    ),
    "job_id": "fenwick-aiagent-002",
}

IRONCLAD_PLATFORM_ENGINEER_POSTING = {
    "title": "Senior Platform Engineer",
    "company": "Ironclad Systems",
    "location": "Austin, TX",
    "employment_type": "Full-time",
    "work_arrangement": "Hybrid (3 days onsite)",
    "years_required": "5+ years of experience",
    "salary_range": "$140,000 - $170,000 USD",
    "required_skills": ["Python", "PostgreSQL", "AWS", "Kubernetes", "Terraform"],
    "nice_to_have_skills": ["Go", "gRPC", "Datadog"],
    "description": (
        "Ironclad Systems is hiring a Senior Platform Engineer to own our cloud infrastructure "
        "on AWS, running containerized services on Kubernetes and managing infra-as-code with "
        "Terraform. You'll work closely with backend teams building on Python and PostgreSQL."
    ),
    "job_id": "ironclad-platform-009",
}

CASCADE_DB_RELIABILITY_POSTING = {
    "title": "Database Reliability Engineer",
    "company": "Cascade Data Systems",
    "location": "Remote (US)",
    "employment_type": "Full-time",
    "work_arrangement": "Remote",
    "years_required": "2+ years of experience",
    "salary_range": "$105,000 - $130,000 USD",
    "required_skills": ["MongoDB", "Docker", "Git", "REST APIs"],
    "nice_to_have_skills": [
        "Kubernetes",
        "AWS",
        "Terraform",
        "Sharding",
        "On-call incident response",
    ],
    "description": (
        "Cascade Data Systems runs mission-critical MongoDB clusters at scale for fintech "
        "customers. We're hiring a Database Reliability Engineer to own replica set topology, "
        "sharding strategy, backup/disaster-recovery drills, and query performance tuning "
        "across a 40+ node fleet. You'll be on a rotating on-call schedule responding to "
        "production database incidents and driving postmortems."
    ),
    "job_id": "cascade-dbre-014",
}

HALCYON_DESIGN_SYSTEMS_POSTING = {
    "title": "Frontend Engineer, Design Systems",
    "company": "Halcyon Retail",
    "location": "Remote (US)",
    "employment_type": "Full-time",
    "work_arrangement": "Remote",
    "years_required": "2+ years of experience",
    "salary_range": "$100,000 - $125,000 USD",
    "required_skills": ["React", "TypeScript", "JavaScript", "Git", "HTML/CSS"],
    "nice_to_have_skills": ["Storybook", "Figma", "Accessibility (WCAG)", "Jest", "Design tokens"],
    "description": (
        "Halcyon Retail is growing our design systems team. You'll build and maintain a shared "
        "component library used across a dozen product teams, working closely with design in "
        "Figma to translate design tokens into accessible, well-tested React/TypeScript "
        "components. Strong WCAG accessibility knowledge and component testing discipline "
        "(Jest, Storybook) are core to this role."
    ),
    "job_id": "halcyon-designsys-021",
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


def test_fenwick_ai_agent_engineer_posting_passes_gate_with_a_strong_fit(tmp_path, real_resume):
    """LLM responses captured verbatim from a live run against gemini-flash-latest."""
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
                        "fastapi",
                        "typescript",
                    ],
                    "missing_skills": ["kubernetes", "langchain", "aws"],
                    "reasoning": (
                        "The candidate meets all required skills and has exactly the 2.0 years "
                        "of experience requested, with a highly relevant background in building "
                        "multi-agent systems and AI tools (such as Google ADK, Claude API, and "
                        "n8n workflows). Although missing nice-to-have skills like Kubernetes, "
                        "AWS, and LangChain, his deep practical experience with agentic "
                        "architectures makes him a strong fit for this specific role."
                    ),
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "kubernetes",
                            "classification": "real_gap",
                            "reasoning": (
                                "While the candidate lists Docker as a skill, the resume has no "
                                "mentions of container orchestration, Kubernetes, or managing "
                                "clustered deployments."
                            ),
                        },
                        {
                            "skill": "langchain",
                            "classification": "fixable",
                            "reasoning": (
                                "The candidate has built multiple LLM-based applications and "
                                "multi-agent systems using Google ADK, n8n, and Claude APIs, "
                                "demonstrating strong conceptual and practical equivalence to "
                                "LangChain."
                            ),
                        },
                        {
                            "skill": "aws",
                            "classification": "real_gap",
                            "reasoning": (
                                "There is no evidence of cloud infrastructure experience, "
                                "deployment on AWS, or any other cloud service providers in the "
                                "candidate's history."
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
                                "Built JobMatch AI, a multi-agent job search assistant utilizing "
                                "Google ADK 2.0 (LangChain-equivalent agent orchestration), with "
                                "ATS keyword gating, LLM-based semantic scoring, and automated "
                                "resume optimization"
                            ),
                            "rationale": (
                                "Surfaces the nice-to-have LangChain skill by drawing a direct, "
                                "truthful parallel between the candidate's Google ADK 2.0 agent "
                                "orchestration experience and LangChain."
                            ),
                        }
                    ]
                }
            ),
        ]
    )

    result = run_scoring_pipeline(
        FENWICK_AI_AGENT_ENGINEER_POSTING, real_resume, store=_store(tmp_path), llm_client=client
    )
    _print_result(FENWICK_AI_AGENT_ENGINEER_POSTING["title"], result)

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "strong"
    assert result["semantic_fit_result"]["missing_skills"] == ["kubernetes", "langchain", "aws"]

    gaps_by_skill = {gap["skill"]: gap["classification"] for gap in result["gap_analysis_result"]["gaps"]}
    assert gaps_by_skill == {"kubernetes": "real_gap", "langchain": "fixable", "aws": "real_gap"}

    suggestions = result["resume_optimization_result"]["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["skill"] == "langchain"
    assert len(client.calls) == 3


def test_ironclad_platform_engineer_posting_fails_ats_gate_on_missing_infra_skills(
    tmp_path, real_resume
):
    result = run_scoring_pipeline(
        IRONCLAD_PLATFORM_ENGINEER_POSTING,
        real_resume,
        store=_store(tmp_path),
        llm_client=_ExplodingLLMClient(),
    )
    _print_result(IRONCLAD_PLATFORM_ENGINEER_POSTING["title"], result)

    assert result["status"] == "ats_gate_failed"
    assert result["ats_gate_result"]["passed"] is False
    assert result["ats_gate_result"]["missing_required_skills"] == [
        "postgresql",
        "aws",
        "kubernetes",
        "terraform",
    ]
    assert result["ats_gate_result"]["years_requirement_met"] is False
    assert result["semantic_fit_result"] is None
    assert result["gap_analysis_result"] is None
    assert result["resume_optimization_result"] is None


def test_cascade_db_reliability_posting_scores_a_weak_fit_despite_passing_the_gate(
    tmp_path, real_resume
):
    """LLM responses captured verbatim from a live run against gemini-flash-latest.

    Demonstrates that passing the literal ATS keyword gate doesn't guarantee a good semantic
    fit -- all required skills match, but the role is a different domain (database ops) than
    the resume's actual experience (full-stack/AI-agent development).
    """
    client = _ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "weak",
                    "matched_skills": ["mongodb", "docker", "git", "rest apis"],
                    "missing_skills": [
                        "kubernetes",
                        "aws",
                        "terraform",
                        "sharding",
                        "on-call incident response",
                    ],
                    "reasoning": (
                        "While the candidate meets all the baseline required skills, their "
                        "background is heavily focused on frontend, full-stack, and AI "
                        "multi-agent software engineering rather than database administration "
                        "or infrastructure. They are missing all of the specialized "
                        "nice-to-have skills for a Database Reliability Engineer, including "
                        "Kubernetes, AWS, Terraform, sharding, and on-call incident response "
                        "experience, meaning their overall profile does not align with this "
                        "operations-heavy role."
                    ),
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "kubernetes",
                            "classification": "real_gap",
                            "reasoning": (
                                "The resume lists 'Docker' as a skill but contains no mention "
                                "of container orchestration, clustering, or cloud deployment "
                                "experience."
                            ),
                        },
                        {
                            "skill": "aws",
                            "classification": "real_gap",
                            "reasoning": (
                                "There is no mention of AWS or any other major public cloud "
                                "provider in the candidate's experience or skills list."
                            ),
                        },
                        {
                            "skill": "terraform",
                            "classification": "real_gap",
                            "reasoning": (
                                "The resume shows no evidence of experience with Infrastructure "
                                "as Code (IaC) or automated provisioning tools."
                            ),
                        },
                        {
                            "skill": "sharding",
                            "classification": "borderline",
                            "reasoning": (
                                "The candidate has experience with 'MongoDB' through their "
                                "Atlas Taxi project, which is a database technology that "
                                "natively uses sharding, but they do not explicitly mention "
                                "configuring database scaling, clustering, or partitioning."
                            ),
                        },
                        {
                            "skill": "on-call incident response",
                            "classification": "real_gap",
                            "reasoning": (
                                "The candidate's background is in freelance development, "
                                "teaching, and business consulting, with no experience in "
                                "production systems administration or on-call rotation support."
                            ),
                        },
                    ]
                }
            ),
        ]
    )

    result = run_scoring_pipeline(
        CASCADE_DB_RELIABILITY_POSTING, real_resume, store=_store(tmp_path), llm_client=client
    )
    _print_result(CASCADE_DB_RELIABILITY_POSTING["title"], result)

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "weak"
    assert result["semantic_fit_result"]["missing_skills"] == [
        "kubernetes",
        "aws",
        "terraform",
        "sharding",
        "on-call incident response",
    ]

    gaps_by_skill = {gap["skill"]: gap["classification"] for gap in result["gap_analysis_result"]["gaps"]}
    assert gaps_by_skill == {
        "kubernetes": "real_gap",
        "aws": "real_gap",
        "terraform": "real_gap",
        "sharding": "borderline",
        "on-call incident response": "real_gap",
    }

    assert result["resume_optimization_result"]["suggestions"] == []
    assert len(client.calls) == 2


def test_halcyon_design_systems_posting_scores_a_moderate_fit(tmp_path, real_resume):
    """LLM responses captured verbatim from a live run against gemini-flash-latest."""
    client = _ScriptedLLMClient(
        [
            json.dumps(
                {
                    "fit_tier": "moderate",
                    "matched_skills": ["React", "TypeScript", "JavaScript", "Git", "HTML/CSS"],
                    "missing_skills": [
                        "storybook",
                        "figma",
                        "accessibility (wcag)",
                        "jest",
                        "design tokens",
                    ],
                    "reasoning": (
                        "The candidate meets all required core technical skills (React, "
                        "TypeScript, JavaScript, Git, and HTML/CSS) and satisfies the minimum "
                        "experience requirement. However, their experience is heavily focused "
                        "on general full-stack and AI-agent development, leaving a significant "
                        "gap in design-system-specific competencies such as Storybook, Figma, "
                        "and design tokens."
                    ),
                }
            ),
            json.dumps(
                {
                    "gaps": [
                        {
                            "skill": "storybook",
                            "classification": "real_gap",
                            "reasoning": (
                                "The resume lists React and HTML/CSS but contains no mention of "
                                "Storybook, component isolation, UI library development, or any "
                                "adjacent frontend documentation tools."
                            ),
                        },
                        {
                            "skill": "figma",
                            "classification": "real_gap",
                            "reasoning": (
                                "There is no mention of Figma, prototyping, UI/UX design "
                                "collaboration, or any visual design tools in the candidate's "
                                "profile."
                            ),
                        },
                        {
                            "skill": "accessibility (wcag)",
                            "classification": "real_gap",
                            "reasoning": (
                                "The resume has no reference to web accessibility, WCAG "
                                "standards, semantic HTML optimization, or assistive technology "
                                "compatibility."
                            ),
                        },
                        {
                            "skill": "jest",
                            "classification": "real_gap",
                            "reasoning": (
                                "No unit testing frameworks, integration testing, or JavaScript "
                                "testing tools (like Jest or Mocha) are mentioned in the "
                                "candidate's projects or skills."
                            ),
                        },
                        {
                            "skill": "design tokens",
                            "classification": "real_gap",
                            "reasoning": (
                                "The candidate has built standard web applications but shows no "
                                "evidence of working with design systems, design tokens, "
                                "advanced CSS variables, or styling architecture."
                            ),
                        },
                    ]
                }
            ),
        ]
    )

    result = run_scoring_pipeline(
        HALCYON_DESIGN_SYSTEMS_POSTING, real_resume, store=_store(tmp_path), llm_client=client
    )
    _print_result(HALCYON_DESIGN_SYSTEMS_POSTING["title"], result)

    assert result["status"] == "scored"
    assert result["ats_gate_result"]["passed"] is True
    assert result["semantic_fit_result"]["fit_tier"] == "moderate"
    assert result["semantic_fit_result"]["missing_skills"] == [
        "storybook",
        "figma",
        "accessibility (wcag)",
        "jest",
        "design tokens",
    ]

    gaps_by_skill = {gap["skill"]: gap["classification"] for gap in result["gap_analysis_result"]["gaps"]}
    assert gaps_by_skill == {
        "storybook": "real_gap",
        "figma": "real_gap",
        "accessibility (wcag)": "real_gap",
        "jest": "real_gap",
        "design tokens": "real_gap",
    }

    assert result["resume_optimization_result"]["suggestions"] == []
    assert len(client.calls) == 2
