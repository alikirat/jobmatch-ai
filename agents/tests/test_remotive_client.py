"""RemotiveClient tests.

The correctness tests below fake out the HTTP session entirely, so they run without a
network connection -- same pattern as test_adzuna_client.py.

The test at the bottom is a real integration test against the live Remotive API. It's
skipped by default and must be opted into explicitly (`REMOTIVE_INTEGRATION_TEST=1`),
since Remotive asks that their endpoint not be polled more than a few times a day and a
normal test run shouldn't count against that budget.
"""

from __future__ import annotations

import json
import os

import pytest

from agents.ingest.remotive_client import RemotiveClient, RemotiveError
from agents.nodes.ingest.normalize_posting import normalize_posting
from agents.schemas import RawJobPosting

REMOTIVE_JOB_FIXTURE = {
    "id": 2091062,
    "url": "https://remotive.com/remote-jobs/software-development/senior-product-engineer-2091062",
    "title": "Junior Software Engineer",
    "company_name": "Clipster",
    "company_logo": "https://remotive.com/job/2091062/logo",
    "category": "Software Development",
    "tags": ["backend", "frontend", "react", "postgresql"],
    "job_type": "full_time",
    "publication_date": "2026-07-13T07:05:10",
    "candidate_required_location": "USA",
    "salary": "$80,000 - $100,000",
    "description": "<p>Join our <strong>remote-first</strong> team building React apps.</p>",
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls: list[dict] = []

    def get(self, url: str, *, params: dict, timeout: float):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self._response


def test_search_maps_remotive_results_into_the_raw_job_posting_shape():
    session = _FakeSession(_FakeResponse(200, {"jobs": [REMOTIVE_JOB_FIXTURE]}))
    client = RemotiveClient(session=session)

    postings = client.search(keywords="junior software engineer")

    assert len(postings) == 1
    posting = postings[0]
    assert posting["title"] == "Junior Software Engineer"
    assert posting["company"] == "Clipster"
    assert posting["location"] == "USA"
    assert posting["work_arrangement"] == "Remote"
    assert posting["employment_type"] == "Full-Time"
    assert posting["salary_range"] == "$80,000 - $100,000"
    assert posting["job_id"] == "remotive:2091062"
    assert posting["required_skills"] == []
    assert posting["years_required"] is None
    assert posting["description"] == "Join our remote-first team building React apps."

    # Must be consumable by RawJobPosting/normalize_posting exactly as-is.
    RawJobPosting.model_validate(posting)
    normalized = normalize_posting(posting)
    assert normalized["title"] == "Junior Software Engineer"
    assert normalized["work_arrangement"] == "remote"
    assert normalized["salary_min"] == 80000
    assert normalized["salary_max"] == 100000


def test_search_sends_expected_query_params():
    session = _FakeSession(_FakeResponse(200, {"jobs": []}))
    client = RemotiveClient(session=session)

    client.search(keywords="junior software engineer", category="software-dev")

    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://remotive.com/api/remote-jobs"
    assert call["params"]["search"] == "junior software engineer"
    assert call["params"]["category"] == "software-dev"


def test_search_omits_optional_params_when_not_provided():
    session = _FakeSession(_FakeResponse(200, {"jobs": []}))
    client = RemotiveClient(session=session)

    client.search()

    call = session.calls[0]
    assert "search" not in call["params"]
    assert "category" not in call["params"]


@pytest.mark.parametrize(
    "location,expected_kept",
    [
        ("Worldwide", True),
        ("USA", True),
        ("USA Only", True),
        ("USA, CST (UTC-6)", True),
        ("Americas", True),
        ("Americas, Europe, Israel", True),
        ("North America", True),
        ("Northern America, LATAM, Europe, APAC", True),
        ("United States", True),
        ("", True),
        (None, True),
        ("Brazil", False),
        ("Mexico", False),
        ("Canada", False),
        ("Europe, UK, Germany, France, European timezones", False),
        ("LATAM, Europe", False),
        ("Australia", False),
    ],
)
def test_search_filters_postings_by_us_candidate_eligibility(location, expected_kept):
    job = {**REMOTIVE_JOB_FIXTURE, "candidate_required_location": location}
    session = _FakeSession(_FakeResponse(200, {"jobs": [job]}))
    client = RemotiveClient(session=session)

    postings = client.search(keywords="junior software engineer")

    assert (len(postings) == 1) is expected_kept


def test_search_tracks_fetched_and_us_eligible_counts_for_reporting():
    jobs = [
        {**REMOTIVE_JOB_FIXTURE, "id": 1, "candidate_required_location": "USA"},
        {**REMOTIVE_JOB_FIXTURE, "id": 2, "candidate_required_location": "Brazil"},
        {**REMOTIVE_JOB_FIXTURE, "id": 3, "candidate_required_location": "Worldwide"},
    ]
    session = _FakeSession(_FakeResponse(200, {"jobs": jobs}))
    client = RemotiveClient(session=session)

    postings = client.search(keywords="junior software engineer")

    assert len(postings) == 2
    assert client.last_fetched_count == 3
    assert client.last_us_eligible_count == 2


def test_search_raises_remotive_error_on_non_200_status():
    session = _FakeSession(_FakeResponse(500, text="Internal Server Error"))
    client = RemotiveClient(session=session)

    with pytest.raises(RemotiveError, match="500"):
        client.search(keywords="python")


def test_search_strips_html_tags_from_the_description():
    job = {**REMOTIVE_JOB_FIXTURE, "description": "<div>Line one.<br/></div><p>Line two.</p>"}
    session = _FakeSession(_FakeResponse(200, {"jobs": [job]}))
    client = RemotiveClient(session=session)

    # No keywords, so the keyword-relevance guard is a no-op -- this test is only about
    # HTML stripping.
    postings = client.search()

    assert postings[0]["description"] == "Line one. Line two."


def test_missing_job_id_maps_to_none():
    job = {**REMOTIVE_JOB_FIXTURE}
    del job["id"]
    session = _FakeSession(_FakeResponse(200, {"jobs": [job]}))
    client = RemotiveClient(session=session)

    postings = client.search()

    assert postings[0]["job_id"] is None


def test_search_filters_out_off_topic_results_via_client_side_keyword_guard():
    """Regression test: Remotive's own `search` query param has been observed returning the
    full unfiltered job list regardless of the query, so relevance filtering can't be
    trusted to happen server-side -- this guard is what actually keeps results on-topic.
    """
    on_topic = {**REMOTIVE_JOB_FIXTURE, "id": 1, "title": "Junior Software Engineer"}
    off_topic_jobs = [
        {**REMOTIVE_JOB_FIXTURE, "id": 2, "title": "Assistant Account Payable"},
        {**REMOTIVE_JOB_FIXTURE, "id": 3, "title": "Remote Office Assistant"},
        {**REMOTIVE_JOB_FIXTURE, "id": 4, "title": "Product Sales Specialist - Pet Health"},
        {**REMOTIVE_JOB_FIXTURE, "id": 5, "title": "Inside Sales Contractor"},
    ]
    session = _FakeSession(_FakeResponse(200, {"jobs": [on_topic, *off_topic_jobs]}))
    client = RemotiveClient(session=session)

    postings = client.search(keywords="junior software engineer")

    assert [p["title"] for p in postings] == ["Junior Software Engineer"]
    assert client.last_fetched_count == 5
    assert client.last_us_eligible_count == 5
    assert client.last_keyword_relevant_count == 1


def test_search_keyword_guard_accepts_any_matching_word_not_the_full_phrase():
    # "Full Stack Developer" doesn't contain the exact phrase "junior software engineer",
    # but it does share the word "software" -- the guard is deliberately loose (any
    # significant word, not the full phrase) so it doesn't reject differently-phrased but
    # genuinely relevant titles.
    job = {**REMOTIVE_JOB_FIXTURE, "title": "Junior Full Stack Software Developer"}
    session = _FakeSession(_FakeResponse(200, {"jobs": [job]}))
    client = RemotiveClient(session=session)

    postings = client.search(keywords="junior software engineer")

    assert len(postings) == 1


def test_search_without_keywords_does_not_filter_by_title():
    job = {**REMOTIVE_JOB_FIXTURE, "title": "Assistant Account Payable"}
    session = _FakeSession(_FakeResponse(200, {"jobs": [job]}))
    client = RemotiveClient(session=session)

    postings = client.search()

    assert len(postings) == 1


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("REMOTIVE_INTEGRATION_TEST") != "1",
    reason=(
        "hits the live Remotive API -- skipped unless REMOTIVE_INTEGRATION_TEST=1 is set, "
        "since Remotive asks that this endpoint not be polled more than a few times a day"
    ),
)
def test_search_against_the_live_remotive_api():
    client = RemotiveClient()
    postings = client.search(keywords="software engineer")

    assert isinstance(postings, list)
    if postings:
        RawJobPosting.model_validate(postings[0])
