"""Graph workflow: ingest -> ats_gate_check -> semantic_fit_scoring -> gap_analysis -> resume_optimizer.

Every posting is deduplicated before any processing happens. A posting that has already been
processed — pass or fail, regardless of outcome — is resolved from the job store with no
reprocessing and no LLM calls. On a new posting, the ATS gate runs first: on failure the
pipeline stops there (no semantic scoring, no gap analysis, no resume optimization, no LLM
calls) and caches an "ats_gate_failed" result; on a pass it runs the rest of the graph and
caches a "scored" result.
"""

from __future__ import annotations

from pathlib import Path

from agents.llm.client import LLMClient
from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.nodes.optimize.resume_optimizer import resume_optimizer
from agents.nodes.score.ats_gate_check import ats_gate_check
from agents.nodes.score.gap_analysis import gap_analysis
from agents.nodes.score.semantic_fit_scoring import semantic_fit_scoring
from agents.schemas import PipelineResult
from agents.store import JsonStore
from agents.workflows.dedup import compute_dedup_key

DEFAULT_STORE_PATH = Path(__file__).parent.parent / "data" / "processed_jobs.json"


def run_scoring_pipeline(
    raw_posting: dict,
    resume: dict,
    store: JsonStore | None = None,
    llm_client: LLMClient | None = None,
) -> dict:
    store = store or JsonStore(DEFAULT_STORE_PATH)
    dedup_key = compute_dedup_key(raw_posting)

    cached = store.get(dedup_key)
    if cached is not None:
        return cached

    normalized_posting = normalize_posting(raw_posting)
    ats_result = ats_gate_check(resume, normalized_posting)

    if not ats_result["passed"]:
        result = PipelineResult(
            dedup_key=dedup_key,
            status="ats_gate_failed",
            normalized_posting=normalized_posting,
            ats_gate_result=ats_result,
        ).model_dump()
        store.put(dedup_key, result)
        return result

    semantic_fit_result = semantic_fit_scoring(
        resume, normalized_posting, ats_result, llm_client=llm_client
    )
    gap_analysis_result = gap_analysis(
        resume, normalized_posting, semantic_fit_result, llm_client=llm_client
    )
    resume_optimization_result = resume_optimizer(
        resume, gap_analysis_result, normalized_posting, llm_client=llm_client
    )

    result = PipelineResult(
        dedup_key=dedup_key,
        status="scored",
        normalized_posting=normalized_posting,
        ats_gate_result=ats_result,
        semantic_fit_result=semantic_fit_result,
        gap_analysis_result=gap_analysis_result,
        resume_optimization_result=resume_optimization_result,
    ).model_dump()
    store.put(dedup_key, result)
    return result
