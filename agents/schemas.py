from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResumeRole(BaseModel):
    title: str
    company: str
    years: float
    highlights: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    candidate_name: str
    years_experience: float
    skills: list[str]
    roles: list[ResumeRole] = Field(default_factory=list)


class RawJobPosting(BaseModel):
    """Schema for job postings as they arrive from a scraper/API — field formats are inconsistent and untrimmed."""

    title: str
    company: str
    location: str | None = None
    employment_type: str | None = None
    work_arrangement: str
    years_required: str | int | None = None
    salary_range: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    description: str | None = None


class NormalizedRequirements(BaseModel):
    """Output of the normalize_posting node — canonical, matchable requirement data."""

    title: str
    required_skills: list[str]
    nice_to_have_skills: list[str]
    min_years_experience: int | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    work_arrangement: Literal["remote", "hybrid", "onsite", "unknown"]


class ATSGateResult(BaseModel):
    """Output of the ats_gate_check node."""

    passed: bool
    missing_required_skills: list[str]
    required_years: int | None
    candidate_years: float
    years_requirement_met: bool
