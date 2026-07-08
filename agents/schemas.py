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
    job_id: str | None = None


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


class SemanticFitResult(BaseModel):
    """Output of the semantic_fit_scoring node."""

    fit_tier: Literal["strong", "moderate", "weak"]
    matched_skills: list[str]
    missing_skills: list[str]
    reasoning: str


class SkillGap(BaseModel):
    skill: str
    classification: Literal["fixable", "real_gap", "borderline"]
    reasoning: str


class GapAnalysisResult(BaseModel):
    """Output of the gap_analysis node."""

    gaps: list[SkillGap]


class ResumeEditSuggestion(BaseModel):
    """A single suggested edit addressing one fixable gap. Must only rephrase or reorder
    content already present in the resume — never introduce new facts."""

    skill: str
    edit_type: Literal["rephrase", "reorder"]
    before: str
    after: str
    rationale: str


class ResumeOptimizationResult(BaseModel):
    """Output of the resume_optimizer node."""

    suggestions: list[ResumeEditSuggestion]


class PipelineResult(BaseModel):
    """Output of the scoring_pipeline workflow — what gets cached in the job store, keyed by dedup_key."""

    dedup_key: str
    status: Literal["ats_gate_failed", "scored"]
    normalized_posting: NormalizedRequirements
    ats_gate_result: ATSGateResult
    semantic_fit_result: SemanticFitResult | None = None
    gap_analysis_result: GapAnalysisResult | None = None
    resume_optimization_result: ResumeOptimizationResult | None = None
