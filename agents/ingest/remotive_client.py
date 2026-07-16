"""Remotive API client: fetches remote job postings and maps them into the RawJobPosting shape.

No API key required. Unlike Adzuna, every Remotive listing is remote by nature -- the
`candidate_required_location` field instead states which candidate locations the employer
will accept, so that's what gets filtered on to keep only postings a US-based candidate is
actually eligible for.
"""

from __future__ import annotations

import html
import re
from typing import Any, Protocol

import requests

_SEARCH_URL = "https://remotive.com/api/remote-jobs"

# Remotive's API terms (https://remotive.com/api-documentation) ask that this endpoint not be
# polled more than a few times a day -- their data doesn't change faster than that, and they
# say excessive requests get blocked. This client makes exactly one HTTP request per
# `search()` call with no retry/backoff/polling loop; callers (e.g. a batch script run a
# couple of times a day, not a scheduler) are responsible for keeping call volume low.
_TAG_RE = re.compile(r"<[^>]+>")

# A posting is kept if at least one comma-separated segment of `candidate_required_location`
# names a region a US-based candidate qualifies under. Word-boundary matching avoids false
# positives like "us" inside "Australia". Region names not covered here (e.g. a bare
# "Canada") are treated as excluding the US and are filtered out -- conservative by design,
# since the goal is "clearly eligible", not "maybe eligible".
_US_ELIGIBLE_KEYWORDS = (
    "worldwide",
    "usa",
    "us",
    "united states",
    "americas",
    "north america",
    "northern america",
)


class RemotiveError(Exception):
    """Raised when the Remotive API can't be reached or returns an error response."""


class HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class HttpSession(Protocol):
    def get(self, url: str, *, params: dict, timeout: float) -> HttpResponse: ...


class RemotiveClient:
    """Fetches remote job postings from Remotive's public search endpoint.

    `session` defaults to a `requests.Session`; tests inject a stub implementing `get()`
    so they never make a real HTTP call.
    """

    def __init__(self, session: HttpSession | None = None) -> None:
        self._session = session or requests.Session()
        # Set after each search() call so callers (e.g. the batch ingestion script) can
        # report how many results each filter dropped, without extra requests.
        self.last_fetched_count = 0
        self.last_us_eligible_count = 0
        self.last_keyword_relevant_count = 0

    def search(self, *, keywords: str | None = None, category: str | None = None) -> list[dict]:
        """Fetch postings, keep only ones a US-based candidate is eligible for and that
        actually match `keywords`, and map each into the RawJobPosting shape.
        """
        params: dict[str, Any] = {}
        if keywords:
            params["search"] = keywords
        if category:
            params["category"] = category

        try:
            response = self._session.get(_SEARCH_URL, params=params, timeout=10)
        except requests.exceptions.RequestException as exc:
            raise RemotiveError(f"Failed to reach the Remotive API: {exc}") from exc

        if response.status_code != 200:
            raise RemotiveError(
                f"Remotive API request failed with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        payload = response.json()
        jobs = payload.get("jobs", [])
        self.last_fetched_count = len(jobs)

        us_eligible_jobs = [job for job in jobs if _is_us_eligible(job.get("candidate_required_location"))]
        self.last_us_eligible_count = len(us_eligible_jobs)

        # Remotive's own `search` query param has been observed returning the full,
        # unfiltered job list regardless of the query (e.g. "search=junior software
        # engineer" and "search=zzznonexistent" both returned the same result set during
        # manual testing) -- this guard filters on title relevance unconditionally, so
        # results stay on-topic whether or not their server-side search is behaving.
        relevant_jobs = [job for job in us_eligible_jobs if _matches_keywords(job.get("title"), keywords)]
        self.last_keyword_relevant_count = len(relevant_jobs)

        return [_map_result_to_raw_posting(job) for job in relevant_jobs]


def _is_us_eligible(candidate_required_location: str | None) -> bool:
    if not candidate_required_location or not candidate_required_location.strip():
        return True

    segments = [segment.strip().lower() for segment in candidate_required_location.split(",")]
    return any(
        re.search(rf"\b{re.escape(keyword)}\b", segment)
        for segment in segments
        for keyword in _US_ELIGIBLE_KEYWORDS
    )


def _matches_keywords(title: str | None, keywords: str | None) -> bool:
    """True if any significant word of `keywords` appears in `title`.

    Deliberately loose (any word, not all) and title-only (not description) -- the goal is
    to reject clearly off-topic postings (e.g. "Assistant Account Payable" for "junior
    software engineer"), not to replicate real search ranking. Words shorter than 3
    characters are skipped so common short words don't make the guard too permissive.
    """
    if not keywords:
        return True

    words = [word for word in keywords.lower().split() if len(word) >= 3]
    if not words:
        return True

    lowered_title = (title or "").lower()
    return any(word in lowered_title for word in words)


def _map_result_to_raw_posting(job: dict) -> dict:
    """Map a single Remotive job into the RawJobPosting schema shape.

    Remotive doesn't distinguish required from nice-to-have skills (its `tags` field is an
    unstructured mix of skills, topics, and categories), so both are left empty -- the same
    tradeoff `adzuna_client._map_result_to_raw_posting` makes, letting the LLM-based scoring
    nodes read the full description instead of a noisy keyword list.
    """
    job_id = job.get("id")

    return {
        "title": job.get("title") or "",
        "company": job.get("company_name") or "Unknown",
        "location": job.get("candidate_required_location"),
        "employment_type": _employment_type(job.get("job_type")),
        "work_arrangement": "Remote",
        "years_required": None,
        "salary_range": job.get("salary") or None,
        "required_skills": [],
        "nice_to_have_skills": [],
        "description": _strip_html(job.get("description")),
        "job_id": f"remotive:{job_id}" if job_id is not None else None,
    }


def _employment_type(job_type: str | None) -> str | None:
    if not job_type:
        return None
    return job_type.replace("_", "-").title()


def _strip_html(raw: str | None) -> str | None:
    if not raw:
        return raw
    text = html.unescape(_TAG_RE.sub(" ", raw))
    return " ".join(text.split()) or None
