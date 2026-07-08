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
