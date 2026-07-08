from agents.nodes.ingest.normalize_posting import normalize_posting


def test_extracts_structured_fields_from_sample_posting(sample_job_posting):
    result = normalize_posting(sample_job_posting)

    assert result["title"] == "Senior Backend Engineer"
    assert result["min_years_experience"] == 5
    assert result["salary_min"] == 150000
    assert result["salary_max"] == 185000
    assert result["salary_currency"] == "USD"
    assert result["work_arrangement"] == "remote"


def test_normalizes_whitespace_and_case_in_skills(sample_job_posting):
    result = normalize_posting(sample_job_posting)

    assert "python" in result["required_skills"]
    assert "postgresql" in result["required_skills"]
    assert all(skill == skill.strip() for skill in result["required_skills"])
    assert all(skill == skill.lower() for skill in result["required_skills"])


def test_dedupes_skills_that_differ_only_by_case_or_whitespace():
    raw_posting = {
        "title": "Data Engineer",
        "company": "Acme",
        "work_arrangement": "Onsite",
        "years_required": "3 years minimum",
        "required_skills": ["Python", "python", " PYTHON ", "SQL"],
        "nice_to_have_skills": [],
    }

    result = normalize_posting(raw_posting)

    assert result["required_skills"] == ["python", "sql"]
    assert result["min_years_experience"] == 3
    assert result["work_arrangement"] == "onsite"


def test_handles_missing_salary_and_years():
    raw_posting = {
        "title": "Junior Developer",
        "company": "Acme",
        "work_arrangement": "Hybrid - 2 days in office",
        "years_required": None,
        "salary_range": None,
        "required_skills": ["Git"],
        "nice_to_have_skills": [],
    }

    result = normalize_posting(raw_posting)

    assert result["min_years_experience"] is None
    assert result["salary_min"] is None
    assert result["salary_max"] is None
    assert result["salary_currency"] is None
    assert result["work_arrangement"] == "hybrid"


def test_classifies_onsite_work_arrangement():
    raw_posting = {
        "title": "Support Engineer",
        "company": "Acme",
        "work_arrangement": "On-site in Austin, TX",
        "required_skills": [],
        "nice_to_have_skills": [],
    }

    result = normalize_posting(raw_posting)

    assert result["work_arrangement"] == "onsite"


def test_accepts_integer_years_required():
    raw_posting = {
        "title": "Support Engineer",
        "company": "Acme",
        "work_arrangement": "Remote",
        "years_required": 4,
        "required_skills": [],
        "nice_to_have_skills": [],
    }

    result = normalize_posting(raw_posting)

    assert result["min_years_experience"] == 4
