"""Tests for the pure helper functions in agents/scripts/run_ingestion_batch.py.

Only the source-combination/filtering logic is unit tested here -- main() itself makes
real network + LLM calls and isn't covered by the automated suite (see the script's
--store json dry-run mode for manual end-to-end verification).
"""

from __future__ import annotations

from agents.scripts.run_ingestion_batch import _interleave_postings, _is_local_to_la


def _posting(job_id: str) -> dict:
    return {"job_id": job_id}


def test_interleave_postings_alternates_between_sources_rather_than_favoring_one():
    remotive = [_posting(f"remotive:{i}") for i in range(5)]
    adzuna = [_posting(f"adzuna:{i}") for i in range(2)]

    combined = _interleave_postings(remotive, adzuna)

    # Alternates while both sources still have postings left...
    assert [p["job_id"] for p in combined[:4]] == [
        "remotive:0",
        "adzuna:0",
        "remotive:1",
        "adzuna:1",
    ]
    # ...then falls back to whichever source has postings remaining.
    assert [p["job_id"] for p in combined[4:]] == ["remotive:2", "remotive:3", "remotive:4"]


def test_capped_batch_after_interleaving_includes_both_sources_when_both_have_results():
    # Regression case for the bug this was written to fix: a plain concatenation would let
    # a longer Remotive list consume the entire cap before Adzuna's results were considered.
    remotive = [_posting(f"remotive:{i}") for i in range(10)]
    adzuna = [_posting(f"adzuna:{i}") for i in range(10)]

    batch = _interleave_postings(remotive, adzuna)[:4]

    sources = {posting["job_id"].split(":")[0] for posting in batch}
    assert sources == {"remotive", "adzuna"}


def test_interleave_postings_handles_an_empty_source():
    remotive = [_posting("remotive:0"), _posting("remotive:1")]

    combined = _interleave_postings(remotive, [])

    assert [p["job_id"] for p in combined] == ["remotive:0", "remotive:1"]


def test_is_local_to_la_matches_known_la_metro_localities():
    assert _is_local_to_la("Los Angeles, CA") is True
    assert _is_local_to_la("Long Beach, CA") is True
    assert _is_local_to_la("Austin, TX") is False
    assert _is_local_to_la(None) is False
