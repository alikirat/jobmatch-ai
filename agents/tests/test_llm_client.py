"""Tests for the retry-with-backoff behavior in agents/llm/client.py.

Covers the generic `_call_with_retries` helper directly (no google.adk/network involved),
plus `AdkLlmClient.complete()` end to end with `_complete_async` monkeypatched, so retries
are exercised without a live API key or real Gemini calls.
"""

from __future__ import annotations

import pytest
from google.genai.errors import ClientError, ServerError

from agents.llm.client import AdkLlmClient, _call_with_retries


def _server_error(code: int) -> ServerError:
    return ServerError(code, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}}, None)


def _client_error(code: int, message: str) -> ClientError:
    return ClientError(code, {"error": {"message": message}}, None)


class _FlakyCallable:
    """Raises `error` on the first `fail_times` calls, then returns `result`."""

    def __init__(self, error: Exception, fail_times: int, result: str = "ok"):
        self._error = error
        self._fail_times = fail_times
        self._result = result
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._error
        return self._result


def test_call_with_retries_returns_immediately_on_success():
    sleeps: list[float] = []
    fn = _FlakyCallable(_server_error(503), fail_times=0)

    result = _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert result == "ok"
    assert fn.calls == 1
    assert sleeps == []


def test_call_with_retries_retries_transient_errors_with_exponential_backoff():
    sleeps: list[float] = []
    fn = _FlakyCallable(_server_error(503), fail_times=2)

    result = _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert result == "ok"
    assert fn.calls == 3
    assert sleeps == [1.0, 2.0]


def test_call_with_retries_gives_up_after_max_retries_are_exhausted():
    sleeps: list[float] = []
    error = _server_error(503)
    fn = _FlakyCallable(error, fail_times=99)

    with pytest.raises(ServerError):
        _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert fn.calls == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_call_with_retries_treats_429_as_transient():
    sleeps: list[float] = []
    fn = _FlakyCallable(_client_error(429, "rate limited"), fail_times=1)

    result = _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert result == "ok"
    assert fn.calls == 2
    assert sleeps == [1.0]


def test_call_with_retries_does_not_retry_permanent_errors():
    sleeps: list[float] = []
    fn = _FlakyCallable(_client_error(401, "invalid API key"), fail_times=99)

    with pytest.raises(ClientError):
        _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert fn.calls == 1
    assert sleeps == []


def test_call_with_retries_does_not_retry_non_api_errors():
    sleeps: list[float] = []
    fn = _FlakyCallable(ValueError("malformed request"), fail_times=99)

    with pytest.raises(ValueError):
        _call_with_retries(fn, max_retries=3, initial_backoff_seconds=1.0, sleep=sleeps.append)

    assert fn.calls == 1
    assert sleeps == []


def test_adk_llm_client_retries_transient_failures_then_succeeds(monkeypatch):
    calls: list[tuple[str, str]] = []
    sleeps: list[float] = []

    async def flaky_complete_async(self: AdkLlmClient, system_prompt: str, user_prompt: str) -> str:
        calls.append((system_prompt, user_prompt))
        if len(calls) < 3:
            raise _server_error(503)
        return "final answer"

    monkeypatch.setattr(AdkLlmClient, "_complete_async", flaky_complete_async)

    client = AdkLlmClient(sleep=sleeps.append)
    result = client.complete(system_prompt="sys", user_prompt="user")

    assert result == "final answer"
    assert calls == [("sys", "user")] * 3
    assert sleeps == [1.0, 2.0]


def test_adk_llm_client_raises_after_exhausting_retries(monkeypatch):
    calls = []
    sleeps: list[float] = []

    async def always_fails(self: AdkLlmClient, system_prompt: str, user_prompt: str) -> str:
        calls.append(1)
        raise _server_error(503)

    monkeypatch.setattr(AdkLlmClient, "_complete_async", always_fails)

    client = AdkLlmClient(sleep=sleeps.append)
    with pytest.raises(ServerError):
        client.complete(system_prompt="sys", user_prompt="user")

    assert len(calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_adk_llm_client_does_not_retry_permanent_errors(monkeypatch):
    calls = []
    sleeps: list[float] = []

    async def auth_failure(self: AdkLlmClient, system_prompt: str, user_prompt: str) -> str:
        calls.append(1)
        raise _client_error(401, "invalid API key")

    monkeypatch.setattr(AdkLlmClient, "_complete_async", auth_failure)

    client = AdkLlmClient(sleep=sleeps.append)
    with pytest.raises(ClientError):
        client.complete(system_prompt="sys", user_prompt="user")

    assert len(calls) == 1
    assert sleeps == []
