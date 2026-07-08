"""Score node: LLM-based classification of missing skills into fixable / real_gap / borderline."""

from __future__ import annotations

import json
from pathlib import Path

from agents.llm.client import LLMClient, get_default_llm_client
from agents.nodes._llm_json import parse_json_response
from agents.schemas import GapAnalysisResult, NormalizedRequirements, Resume, SemanticFitResult

_PROMPT_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT = (_PROMPT_DIR / "gap_analysis_system.md").read_text()
_USER_PROMPT_TEMPLATE = (_PROMPT_DIR / "gap_analysis_user.md").read_text()


def gap_analysis(
    resume: dict,
    normalized_posting: dict,
    semantic_fit_result: dict,
    llm_client: LLMClient | None = None,
) -> dict:
    """Classify each missing skill from semantic_fit_scoring as fixable, a real gap, or borderline.

    Calls an LLM (injected via `llm_client`, defaulting to the ADK-backed client) since the
    fixable/real_gap distinction requires judging whether adjacent experience in the resume
    could cover the skill if surfaced differently.
    """
    resume_model = Resume.model_validate(resume)
    posting = NormalizedRequirements.model_validate(normalized_posting)
    fit_result = SemanticFitResult.model_validate(semantic_fit_result)

    if not fit_result.missing_skills:
        return GapAnalysisResult(gaps=[]).model_dump()

    client = llm_client or get_default_llm_client()

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        resume_json=resume_model.model_dump_json(indent=2),
        requirements_json=posting.model_dump_json(indent=2),
        missing_skills_json=json.dumps(fit_result.missing_skills, indent=2),
    )

    raw_response = client.complete(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    payload = parse_json_response(raw_response)

    return GapAnalysisResult.model_validate(payload).model_dump()
