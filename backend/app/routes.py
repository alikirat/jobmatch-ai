"""API routes: upload a resume once, then reference it by ID in score requests."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from agents.llm.client import LLMClient
from agents.schemas import PipelineResult, RawJobPosting, Resume
from agents.store import JsonStore
from agents.workflows.scoring_pipeline import run_scoring_pipeline

from app.dependencies import get_job_store, get_llm_client, get_resume_store

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
