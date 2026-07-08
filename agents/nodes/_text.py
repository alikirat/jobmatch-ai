"""Shared text-normalization helpers used by both the ingest and score nodes."""


def normalize_skill(value: str) -> str:
    return " ".join(value.strip().lower().split())


def dedupe_normalized_skills(skills: list[str]) -> list[str]:
    normalized = (normalize_skill(skill) for skill in skills)
    return list(dict.fromkeys(skill for skill in normalized if skill))
