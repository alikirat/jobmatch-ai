"""Batch ingestion: pull postings from Remotive + Adzuna, score them, print a summary.

Standalone script for manual/scheduled batch runs -- deliberately not a FastAPI route,
since it's meant to be invoked a few times a day (matching Remotive's polling guidance),
not on-demand per request.

Usage (from the repo root, with the same `.env` the backend uses):

    python agents/scripts/run_ingestion_batch.py
    python agents/scripts/run_ingestion_batch.py --max-postings 20 --store json

Scoring calls a real LLM (Gemini, via AdkLlmClient) for every posting that isn't already
cached, so each run has a real API cost -- that's why the batch is capped at 15-20
postings by default (see --max-postings).
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Allow running as `python agents/scripts/run_ingestion_batch.py` from the repo root
# without needing PYTHONPATH set up first.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from agents.ingest.adzuna_client import AdzunaClient, AdzunaError  # noqa: E402
from agents.ingest.remotive_client import RemotiveClient, RemotiveError  # noqa: E402
from agents.nodes.ingest.normalize_posting import normalize_posting  # noqa: E402
from agents.store import JsonStore, MongoStore  # noqa: E402
from agents.workflows.dedup import compute_dedup_key  # noqa: E402
from agents.workflows.scoring_pipeline import run_scoring_pipeline  # noqa: E402

_DEFAULT_RESUME_PATH = _REPO_ROOT / "agents" / "fixtures" / "resume.real.json"
_DEFAULT_JSON_STORE_PATH = _REPO_ROOT / "agents" / "data" / "processed_jobs.json"

_MAX_POSTINGS_CEILING = 20

# Cities/areas that count as "genuinely local to LA" for the Adzuna on-site filter below.
# Deliberately conservative substring list rather than a geocoding lookup -- good enough to
# separate "this posting is in the LA metro" from "Adzuna's location search returned
# something in the general vicinity of California".
_LA_METRO_LOCALITIES = (
    "los angeles",
    "long beach",
    "santa monica",
    "pasadena",
    "burbank",
    "glendale",
    "anaheim",
    "irvine",
    "hollywood",
    "culver city",
    "torrance",
    "downey",
    "compton",
    "inglewood",
    "beverly hills",
    "orange county",
    "la county",
)


def _is_local_to_la(location: str | None) -> bool:
    if not location:
        return False
    lowered = location.lower()
    return any(locality in lowered for locality in _LA_METRO_LOCALITIES)


def _passes_adzuna_filter(raw_posting: dict) -> bool:
    """Keep a posting if it's remote, or genuinely local to the LA metro area."""
    normalized = normalize_posting(raw_posting)
    if normalized["work_arrangement"] == "remote":
        return True
    return _is_local_to_la(raw_posting.get("location"))


def _interleave_postings(*sources: list[dict]) -> list[dict]:
    """Round-robin combine postings from multiple sources.

    A plain concatenation would let whichever source returns the most results consume the
    entire --max-postings cap before the other source is ever considered. Round-robin
    instead guarantees every source gets a turn (while it still has postings left) as the
    cap is filled.
    """
    combined = []
    for round_ in itertools.zip_longest(*sources):
        for posting in round_:
            if posting is not None:
                combined.append(posting)
    return combined


def _dedupe_postings(postings: list[dict]) -> list[dict]:
    seen_keys: set[str] = set()
    deduped = []
    for posting in postings:
        key = compute_dedup_key(posting)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(posting)
    return deduped


def _build_store(kind: str) -> JsonStore | MongoStore:
    if kind == "json":
        return JsonStore(_DEFAULT_JSON_STORE_PATH)

    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_database = os.environ.get("MONGODB_DATABASE", "jobmatch")
    return MongoStore(uri=mongodb_uri, database=mongodb_database, collection="processed_jobs")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume-file",
        type=Path,
        default=_DEFAULT_RESUME_PATH,
        help=f"Path to a Resume JSON fixture (default: {_DEFAULT_RESUME_PATH})",
    )
    parser.add_argument(
        "--remotive-keywords",
        default="junior software engineer",
        help="Keywords for the Remotive search",
    )
    parser.add_argument(
        "--adzuna-keywords",
        default="junior software engineer",
        help="Keywords for the Adzuna search",
    )
    parser.add_argument(
        "--adzuna-location",
        default="Los Angeles, CA",
        help="Location for the Adzuna search",
    )
    parser.add_argument(
        "--adzuna-results-per-page",
        type=int,
        default=20,
        help="How many Adzuna results to request before client-side filtering",
    )
    parser.add_argument(
        "--max-postings",
        type=int,
        default=18,
        help=f"Cap on total postings scored this run (max {_MAX_POSTINGS_CEILING}, "
        "to bound real Gemini API cost)",
    )
    parser.add_argument(
        "--store",
        choices=["mongo", "json"],
        default="mongo",
        help="Which job store to write scored results to (default: mongo, matching the "
        "backend's own store)",
    )
    args = parser.parse_args()

    if not 1 <= args.max_postings <= _MAX_POSTINGS_CEILING:
        parser.error(f"--max-postings must be between 1 and {_MAX_POSTINGS_CEILING}")

    return args


def main() -> None:
    # Loaded unconditionally (not just for --store mongo) since GOOGLE_API_KEY is needed
    # for real scoring regardless of which job store is used.
    load_dotenv()

    args = _parse_args()

    if not args.resume_file.exists():
        print(f"Resume file not found: {args.resume_file}", file=sys.stderr)
        sys.exit(1)
    resume = json.loads(args.resume_file.read_text())

    store = _build_store(args.store)

    # --- Fetch ---
    remotive_client = RemotiveClient()
    try:
        remotive_postings = remotive_client.search(keywords=args.remotive_keywords)
    except RemotiveError as exc:
        print(f"Remotive fetch failed: {exc}", file=sys.stderr)
        remotive_postings = []
    remotive_fetched = remotive_client.last_fetched_count
    remotive_us_eligible = remotive_client.last_us_eligible_count
    remotive_keyword_relevant = remotive_client.last_keyword_relevant_count

    try:
        adzuna_client = AdzunaClient()
        adzuna_raw_postings = adzuna_client.search(
            keywords=args.adzuna_keywords,
            location=args.adzuna_location,
            results_per_page=args.adzuna_results_per_page,
        )
    except AdzunaError as exc:
        print(f"Adzuna fetch failed: {exc}", file=sys.stderr)
        adzuna_raw_postings = []
    adzuna_fetched = len(adzuna_raw_postings)
    adzuna_filtered_postings = [p for p in adzuna_raw_postings if _passes_adzuna_filter(p)]
    adzuna_passed_filter = len(adzuna_filtered_postings)

    # --- Interleave + dedup + cap ---
    combined = _dedupe_postings(_interleave_postings(remotive_postings, adzuna_filtered_postings))
    batch = combined[: args.max_postings]

    # --- Score ---
    new_count = 0
    cached_count = 0
    error_count = 0
    fit_tier_counts: Counter[str] = Counter()
    ats_gate_failed_count = 0

    for raw_posting in batch:
        dedup_key = compute_dedup_key(raw_posting)
        already_cached = store.get(dedup_key) is not None
        if already_cached:
            cached_count += 1
        else:
            new_count += 1

        try:
            result = run_scoring_pipeline(raw_posting, resume, store=store, llm_client=None)
        except Exception as exc:  # noqa: BLE001 -- one bad posting shouldn't kill the batch
            error_count += 1
            print(f"  ! Failed to score {dedup_key!r}: {exc}", file=sys.stderr)
            continue

        if result["status"] == "ats_gate_failed":
            ats_gate_failed_count += 1
        elif result["status"] == "scored":
            fit_tier_counts[result["semantic_fit_result"]["fit_tier"]] += 1

    if isinstance(store, MongoStore):
        store.close()

    # --- Summary ---
    print()
    print("=== Ingestion batch summary ===")
    print(
        f"Remotive: fetched {remotive_fetched}, US-eligible after location filter: "
        f"{remotive_us_eligible}, kept after keyword-relevance filter: {remotive_keyword_relevant}"
    )
    print(f"Adzuna:   fetched {adzuna_fetched}, passed remote-or-LA-local filter: {adzuna_passed_filter}")
    print(f"Combined (interleaved + cross-source deduped): {len(combined)} (batch capped at {len(batch)})")
    print(f"New postings scored: {new_count}, already cached: {cached_count}, errors: {error_count}")
    print()
    print("Fit tier breakdown (scored postings):")
    for tier in ("strong", "moderate", "weak"):
        print(f"  {tier}: {fit_tier_counts.get(tier, 0)}")
    print(f"ATS gate failed: {ats_gate_failed_count}")


if __name__ == "__main__":
    main()
