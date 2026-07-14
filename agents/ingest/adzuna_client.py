"""Adzuna API client: fetches job postings and maps them into the RawJobPosting shape.

Credentials come from ADZUNA_APP_ID / ADZUNA_APP_KEY, loaded via python-dotenv the same
way MONGODB_URI / MONGODB_DATABASE are loaded in `backend/app/dependencies.py`.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import requests
from dotenv import load_dotenv

_SEARCH_URL_TEMPLATE = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"


class AdzunaError(Exception):
    """Raised when the Adzuna API can't be reached or returns an error response."""


class AdzunaRateLimitError(AdzunaError):
    """Raised when Adzuna responds with HTTP 429 (rate limit exceeded)."""


class HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> Any: ...


class HttpSession(Protocol):
    def get(self, url: str, *, params: dict, timeout: float) -> HttpResponse: ...


def _load_credentials() -> tuple[str, str]:
    load_dotenv()
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaError(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in the environment "
            "(see .env.example)."
        )
    return app_id, app_key


class AdzunaClient:
    """Fetches job postings from Adzuna's US search endpoint.

    `session` defaults to a `requests.Session`; tests inject a stub implementing `get()`
    so they never make a real HTTP call or need real credentials.
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
        session: HttpSession | None = None,
    ) -> None:
        if app_id is None or app_key is None:
            env_app_id, env_app_key = _load_credentials()
            app_id = app_id or env_app_id
            app_key = app_key or env_app_key
        self._app_id = app_id
        self._app_key = app_key
        self._session = session or requests.Session()

    def search(
        self,
        *,
        keywords: str | None = None,
        location: str | None = None,
        results_per_page: int = 20,
        page: int = 1,
    ) -> list[dict]:
        """Fetch a page of job postings, each mapped into the RawJobPosting shape."""
        params: dict[str, Any] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": results_per_page,
            "content-type": "application/json",
        }
        if keywords:
            params["what"] = keywords
        if location:
            params["where"] = location

        url = _SEARCH_URL_TEMPLATE.format(page=page)

        try:
            response = self._session.get(url, params=params, timeout=10)
        except requests.exceptions.RequestException as exc:
            raise AdzunaError(f"Failed to reach the Adzuna API: {exc}") from exc

        if response.status_code == 429:
            raise AdzunaRateLimitError(
                "Adzuna API rate limit exceeded (HTTP 429). Wait before retrying."
            )
        if response.status_code != 200:
            raise AdzunaError(
                f"Adzuna API request failed with HTTP {response.status_code}: {response.text[:200]}"
            )

        payload = response.json()
        results = payload.get("results", [])
        return [_map_result_to_raw_posting(result) for result in results]


def _map_result_to_raw_posting(result: dict) -> dict:
    """Map a single Adzuna search result into the RawJobPosting schema shape.

    Adzuna doesn't provide structured required/nice-to-have skills or a years-of-experience
    requirement, so those are left empty/None -- normalize_posting handles absent values fine.
    """
    company = (result.get("company") or {}).get("display_name") or "Unknown"
    location = (result.get("location") or {}).get("display_name")
    title = result.get("title") or ""
    description = result.get("description")
    job_id = result.get("id")

    return {
        "title": title,
        "company": company,
        "location": location,
        "employment_type": _employment_type(result),
        "work_arrangement": _work_arrangement(title, description),
        "years_required": None,
        "salary_range": _salary_range(result),
        "required_skills": [],
        "nice_to_have_skills": [],
        "description": description,
        "job_id": f"adzuna:{job_id}" if job_id is not None else None,
    }


def _employment_type(result: dict) -> str | None:
    contract_time = result.get("contract_time")
    contract_type = result.get("contract_type")
    parts = [value.replace("_", "-").title() for value in (contract_time, contract_type) if value]
    return " ".join(parts) or None


def _work_arrangement(title: str, description: str | None) -> str:
    haystack = f"{title} {description or ''}".lower()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    if "on-site" in haystack or "onsite" in haystack or "in office" in haystack or "in-office" in haystack:
        return "Onsite"
    return "Not specified"


def _salary_range(result: dict) -> str | None:
    salary_min = result.get("salary_min")
    salary_max = result.get("salary_max")
    if salary_min is None and salary_max is None:
        return None
    if salary_min is not None and salary_max is not None:
        return f"${salary_min:,.0f} - ${salary_max:,.0f} USD"
    value = salary_min if salary_min is not None else salary_max
    return f"${value:,.0f} USD"
