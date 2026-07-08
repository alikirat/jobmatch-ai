from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.nodes.score.ats_gate_check import ats_gate_check


def test_fails_when_a_required_skill_is_missing(sample_resume, sample_job_posting):
    normalized = normalize_posting(sample_job_posting)

    result = ats_gate_check(sample_resume, normalized)

    assert result["passed"] is False
    assert result["missing_required_skills"] == ["kubernetes"]
    assert result["years_requirement_met"] is True


def test_passes_when_all_required_skills_and_years_are_met(sample_resume, sample_job_posting):
    resume_with_kubernetes = {
        **sample_resume,
        "skills": [*sample_resume["skills"], "Kubernetes"],
    }
    normalized = normalize_posting(sample_job_posting)

    result = ats_gate_check(resume_with_kubernetes, normalized)

    assert result["passed"] is True
    assert result["missing_required_skills"] == []
    assert result["years_requirement_met"] is True


def test_fails_when_candidate_has_insufficient_years(sample_resume, sample_job_posting):
    junior_resume = {**sample_resume, "years_experience": 2}
    normalized = normalize_posting(sample_job_posting)

    result = ats_gate_check(junior_resume, normalized)

    assert result["passed"] is False
    assert result["years_requirement_met"] is False
    assert result["required_years"] == 5
    assert result["candidate_years"] == 2


def test_passes_when_posting_has_no_years_requirement(sample_resume):
    normalized_posting = {
        "title": "Backend Engineer",
        "required_skills": ["python"],
        "nice_to_have_skills": [],
        "min_years_experience": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "work_arrangement": "remote",
    }

    result = ats_gate_check(sample_resume, normalized_posting)

    assert result["passed"] is True
    assert result["years_requirement_met"] is True
    assert result["required_years"] is None


def test_skill_matching_is_case_and_whitespace_insensitive():
    resume = {
        "candidate_name": "Test Candidate",
        "years_experience": 5,
        "skills": ["python", "  Docker  "],
        "roles": [],
    }
    normalized_posting = {
        "title": "Backend Engineer",
        "required_skills": ["Python", "DOCKER"],
        "nice_to_have_skills": [],
        "min_years_experience": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "work_arrangement": "remote",
    }

    result = ats_gate_check(resume, normalized_posting)

    assert result["passed"] is True
    assert result["missing_required_skills"] == []
