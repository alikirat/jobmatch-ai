"""Score node: hard pass/fail gate on required skills and minimum years, ahead of any semantic scoring."""

from __future__ import annotations

from agents.nodes._text import normalize_skill
from agents.schemas import ATSGateResult, NormalizedRequirements, Resume


def ats_gate_check(resume: dict, normalized_posting: dict) -> dict:
    """Check a resume against normalize_posting's output for hard requirement matches.

    Deterministic: no LLM calls, safe to unit test with fixed inputs/outputs.
    Does not attempt semantic/fuzzy skill matching — that belongs to a later, LLM-based node.
    """
    resume_model = Resume.model_validate(resume)
    posting = NormalizedRequirements.model_validate(normalized_posting)

    candidate_skills = {normalize_skill(skill) for skill in resume_model.skills}
    required_skills = [normalize_skill(skill) for skill in posting.required_skills]
    missing_skills = [skill for skill in required_skills if skill not in candidate_skills]

    required_years = posting.min_years_experience
    years_met = required_years is None or resume_model.years_experience >= required_years

    result = ATSGateResult(
        passed=not missing_skills and years_met,
        missing_required_skills=missing_skills,
        required_years=required_years,
        candidate_years=resume_model.years_experience,
        years_requirement_met=years_met,
    )
    return result.model_dump()
