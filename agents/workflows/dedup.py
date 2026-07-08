"""Computes a stable dedup key for a raw job posting, used to cache scoring_pipeline results."""

from __future__ import annotations

import hashlib

from agents.schemas import RawJobPosting


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def compute_dedup_key(raw_posting: dict) -> str:
    """Prefer the source's own job ID; fall back to a hash of normalized company+title+description
    so reposted/re-scraped listings with only formatting differences still collide.
    """
    posting = RawJobPosting.model_validate(raw_posting)

    if posting.job_id:
        return f"id:{_normalize_text(posting.job_id)}"

    fingerprint = "|".join(
        _normalize_text(value)
        for value in (posting.company, posting.title, posting.description or "")
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"hash:{digest}"
