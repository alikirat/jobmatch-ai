"""Optimize node: LLM-based resume edit suggestions for fixable gaps only."""

from __future__ import annotations

import json
from pathlib import Path

from agents.llm.client import LLMClient, get_default_llm_client
from agents.nodes._llm_json import parse_json_response
from agents.schemas import (
    GapAnalysisResult,
    NormalizedRequirements,
    Resume,
    ResumeOptimizationResult,
)

_PROMPT_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT = (_PROMPT_DIR / "resume_optimizer_system.md").read_text()
_USER_PROMPT_TEMPLATE = (_PROMPT_DIR / "resume_optimizer_user.md").read_text()


def resume_optimizer(
    resume: dict,
    gap_analysis_result: dict,
    normalized_posting: dict,
    llm_client: LLMClient | None = None,
) -> dict:
    """Suggest resume edits that surface existing experience for "fixable" gaps only.

    Never sends "real_gap" or "borderline" gaps to the LLM — only "fixable" ones. The system
    prompt explicitly forbids inventing skills, experience, or claims not already present in
    the resume; suggestions may only rephrase or reorder existing content.
    """
    resume_model = Resume.model_validate(resume)
    posting = NormalizedRequirements.model_validate(normalized_posting)
    gaps = GapAnalysisResult.model_validate(gap_analysis_result)

    fixable_gaps = [gap for gap in gaps.gaps if gap.classification == "fixable"]
    if not fixable_gaps:
        return ResumeOptimizationResult(suggestions=[]).model_dump()

    client = llm_client or get_default_llm_client()

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        resume_json=resume_model.model_dump_json(indent=2),
        requirements_json=posting.model_dump_json(indent=2),
        fixable_gaps_json=json.dumps(
            [{"skill": gap.skill, "reasoning": gap.reasoning} for gap in fixable_gaps],
            indent=2,
        ),
    )

    raw_response = client.complete(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    payload = parse_json_response(raw_response)

    return ResumeOptimizationResult.model_validate(payload).model_dump()
