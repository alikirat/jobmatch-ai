import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_resume() -> dict:
    return json.loads((FIXTURES_DIR / "resume.sample.json").read_text())


@pytest.fixture
def sample_job_posting() -> dict:
    return json.loads((FIXTURES_DIR / "job_posting.sample.json").read_text())


@pytest.fixture
def real_resume() -> dict:
    path = FIXTURES_DIR / "resume.real.json"
    if not path.exists():
        pytest.skip(
            "agents/fixtures/resume.real.json is gitignored (contains real personal data) "
            "and isn't present in this checkout; skipping tests that depend on it."
        )
    return json.loads(path.read_text())
