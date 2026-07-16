"""Ingest node: turns a raw job posting payload into structured, matchable requirements."""

from __future__ import annotations

import re

from agents.nodes._text import dedupe_normalized_skills
from agents.schemas import NormalizedRequirements, RawJobPosting

_CURRENCY_CODE_RE = re.compile(r"\b(USD|EUR|GBP|CAD|AUD)\b")
_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?")
_LEADING_DIGITS_RE = re.compile(r"\d+")

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}


def _parse_min_years(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = _LEADING_DIGITS_RE.search(value)
    return int(match.group()) if match else None


def _parse_salary_range(raw: str | None) -> tuple[int | None, int | None, str | None]:
    if not raw:
        return None, None, None

    amounts = [int(float(a.replace(",", ""))) for a in _AMOUNT_RE.findall(raw)]
    salary_min = amounts[0] if len(amounts) >= 1 else None
    salary_max = amounts[1] if len(amounts) >= 2 else None

    currency_match = _CURRENCY_CODE_RE.search(raw.upper())
    if currency_match:
        currency = currency_match.group(1)
    else:
        currency = next(
            (code for symbol, code in _CURRENCY_SYMBOLS.items() if symbol in raw),
            None,
        )

    return salary_min, salary_max, currency


def _classify_work_arrangement(raw: str) -> str:
    lowered = raw.lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "remote" in lowered:
        return "remote"
    if "on-site" in lowered or "onsite" in lowered or "in office" in lowered or "in-office" in lowered:
        return "onsite"
    return "unknown"


def normalize_posting(raw_posting: dict) -> dict:
    """Extract structured, matchable requirements from a raw job posting payload.

    Deterministic: no LLM calls, safe to unit test with fixed inputs/outputs.
    """
    posting = RawJobPosting.model_validate(raw_posting)

    salary_min, salary_max, salary_currency = _parse_salary_range(posting.salary_range)

    normalized = NormalizedRequirements(
        title=posting.title.strip(),
        required_skills=dedupe_normalized_skills(posting.required_skills),
        nice_to_have_skills=dedupe_normalized_skills(posting.nice_to_have_skills),
        min_years_experience=_parse_min_years(posting.years_required),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        work_arrangement=_classify_work_arrangement(posting.work_arrangement),
        description=posting.description,
    )
    return normalized.model_dump()
