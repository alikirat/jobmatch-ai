"""Shared helper for parsing structured JSON out of raw LLM text responses."""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_response(text: str) -> dict:
    match = _FENCE_RE.search(text)
    payload = match.group(1) if match else text
    return json.loads(payload.strip())
