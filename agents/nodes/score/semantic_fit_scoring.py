"""Score node: LLM-based semantic fit scoring, weighing required skills over nice-to-have ones."""

from __future__ import annotations

from pathlib import Path

from agents.llm.client import LLMClient, get_default_llm_client
from agents.nodes._llm_json import parse_json_response
from agents.schemas import ATSGateResult, NormalizedRequirements, Resume, SemanticFitResult

_PROMPT_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT = (_PROMPT_DIR / "semantic_fit_scoring_system.md").read_text()
_USER_PROMPT_TEMPLATE = (_PROMPT_DIR / "semantic_fit_scoring_user.md").read_text()


def semantic_fit_scoring(
    resume: dict,
    normalized_posting: dict,
    ats_result: dict,
    llm_client: LLMClient | None = None,
) -> dict:
    """Score how well a resume semantically fits a job posting.

    Calls an LLM (injected via `llm_client`, defaulting to the ADK-backed client) to weigh
    required skills more heavily than nice-to-have ones and reason about adjacent/transferable
    experience that a plain string match would miss.
    """
    resume_model = Resume.model_validate(resume)
    posting = NormalizedRequirements.model_validate(normalized_posting)
    ats = ATSGateResult.model_validate(ats_result)

    client = llm_client or get_default_llm_client()

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        resume_json=resume_model.model_dump_json(indent=2),
        requirements_json=posting.model_dump_json(indent=2),
        ats_result_json=ats.model_dump_json(indent=2),
    )

    raw_response = client.complete(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    payload = parse_json_response(raw_response)

    return SemanticFitResult.model_validate(payload).model_dump()
