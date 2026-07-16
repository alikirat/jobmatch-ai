"""API routes: upload a resume once, then reference it by ID in score requests."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from agents.ingest.adzuna_client import AdzunaClient, AdzunaError, AdzunaRateLimitError
from agents.llm.client import LLMClient
from agents.schemas import PipelineResult, RawJobPosting, Resume
from agents.store import JsonStore
from agents.workflows.scoring_pipeline import run_scoring_pipeline

from app.dependencies import get_adzuna_client, get_job_store, get_llm_client, get_resume_store

router = APIRouter()


class ResumeUploadResponse(BaseModel):
    resume_id: str


class ScoreRequest(BaseModel):
    posting: RawJobPosting
    resume: Resume | None = None
    resume_id: str | None = None

    @model_validator(mode="after")
    def _exactly_one_resume_source(self) -> "ScoreRequest":
        if (self.resume is None) == (self.resume_id is None):
            raise ValueError("Provide exactly one of `resume` or `resume_id`.")
        return self


@router.post("/resumes", response_model=ResumeUploadResponse, status_code=201)
def upload_resume(
    resume: Resume,
    resume_store: JsonStore = Depends(get_resume_store),
) -> dict:
    resume_id = uuid.uuid4().hex
    resume_store.put(resume_id, resume.model_dump())
    return {"resume_id": resume_id}


@router.post("/score", response_model=PipelineResult)
def score_job(
    request: ScoreRequest,
    job_store: JsonStore = Depends(get_job_store),
    resume_store: JsonStore = Depends(get_resume_store),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> dict:
    if request.resume is not None:
        resume_dict = request.resume.model_dump()
    else:
        resume_dict = resume_store.get(request.resume_id)
        if resume_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"No resume found for resume_id={request.resume_id!r}",
            )

    return run_scoring_pipeline(
        request.posting.model_dump(),
        resume_dict,
        store=job_store,
        llm_client=llm_client,
    )


class AdzunaIngestRequest(BaseModel):
    keywords: str | None = None
    location: str | None = None
    results_per_page: int = 20
    page: int = 1
    resume: Resume | None = None
    resume_id: str | None = None

    @model_validator(mode="after")
    def _exactly_one_resume_source(self) -> "AdzunaIngestRequest":
        if (self.resume is None) == (self.resume_id is None):
            raise ValueError("Provide exactly one of `resume` or `resume_id`.")
        return self


class AdzunaIngestResponse(BaseModel):
    fetched: int
    results: list[PipelineResult]


@router.post("/ingest/adzuna", response_model=AdzunaIngestResponse)
def ingest_adzuna(
    request: AdzunaIngestRequest,
    adzuna_client: AdzunaClient = Depends(get_adzuna_client),
    job_store: JsonStore = Depends(get_job_store),
    resume_store: JsonStore = Depends(get_resume_store),
    llm_client: LLMClient | None = Depends(get_llm_client),
) -> dict:
    if request.resume is not None:
        resume_dict = request.resume.model_dump()
    else:
        resume_dict = resume_store.get(request.resume_id)
        if resume_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"No resume found for resume_id={request.resume_id!r}",
            )

    try:
        raw_postings = adzuna_client.search(
            keywords=request.keywords,
            location=request.location,
            results_per_page=request.results_per_page,
            page=request.page,
        )
    except AdzunaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AdzunaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results = [
        run_scoring_pipeline(raw_posting, resume_dict, store=job_store, llm_client=llm_client)
        for raw_posting in raw_postings
    ]

    return {"fetched": len(results), "results": results}


class JobsQueueResponse(BaseModel):
    jobs: list[PipelineResult]


class JobStatusUpdateRequest(BaseModel):
    status: Literal["swiped_right", "swiped_left"]


@router.get("/jobs/queue", response_model=JobsQueueResponse)
def get_jobs_queue(job_store: JsonStore = Depends(get_job_store)) -> dict:
    """Scored jobs still awaiting a swipe decision, oldest first."""
    jobs = [
        job
        for job in job_store.list_all()
        if job.get("status") == "scored" and job.get("review_status", "pending") == "pending"
    ]
    return {"jobs": jobs}


@router.get("/jobs/{job_id}", response_model=PipelineResult)
def get_job_detail(job_id: str, job_store: JsonStore = Depends(get_job_store)) -> dict:
    """Full pipeline result for a single job -- the expanded detail view, unlike the
    summary-oriented /jobs/queue, needs the full description, gap analysis, and resume
    optimization suggestions.
    """
    stored = job_store.get(job_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No job found for job_id={job_id!r}")
    return stored


@router.patch("/jobs/{job_id}/status", response_model=PipelineResult)
def update_job_status(
    job_id: str,
    request: JobStatusUpdateRequest,
    job_store: JsonStore = Depends(get_job_store),
) -> dict:
    stored = job_store.get(job_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No job found for job_id={job_id!r}")

    stored["review_status"] = request.status
    job_store.put(job_id, stored)
    return stored
