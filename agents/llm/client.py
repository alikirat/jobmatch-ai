"""LLM client abstraction so score nodes don't couple directly to a specific SDK.

Nodes accept an `LLMClient` via dependency injection and default to `get_default_llm_client()`
when none is given. Tests inject a stub implementing `complete()`, so they never construct
the default client and never need google-adk installed or a live API key.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable, Protocol

from google.genai.errors import APIError

# Gemini has been observed returning transient 503s ("This model is currently
# experiencing high demand") under normal load, not just at extreme rate limits -- worth
# retrying automatically rather than failing every scoring/gap-analysis/optimization call
# that happens to land during a demand spike. 429 (rate limited) is a ClientError by
# google-genai's 4xx/5xx split but is just as transient as a 5xx, so it's included too.
# Anything else (401/403 auth failures, 400 malformed requests, etc.) fails the same way on
# every retry, so those raise immediately instead of wasting the backoff budget.
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _is_transient_error(exc: BaseException) -> bool:
    return isinstance(exc, APIError) and exc.code in _TRANSIENT_STATUS_CODES


def _call_with_retries(
    fn: Callable[[], str],
    *,
    max_retries: int,
    initial_backoff_seconds: float,
    sleep: Callable[[float], None],
) -> str:
    """Call `fn`, retrying transient failures with exponential backoff.

    With the defaults (max_retries=3, initial_backoff_seconds=1.0) this sleeps 1s, 2s, then
    4s between up to 4 total attempts. A non-transient error, or a transient one on the
    final attempt, propagates to the caller.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_retries or not _is_transient_error(exc):
                raise
            sleep(initial_backoff_seconds * (2**attempt))
            attempt += 1


class LLMClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text response for a single-turn system+user prompt."""
        ...


class AdkLlmClient:
    """Default LLMClient, backed by a Google ADK LlmAgent run through a Runner.

    Retries transient API errors (see `_is_transient_error`) with exponential backoff,
    transparently to every caller -- semantic_fit_scoring, gap_analysis, and
    resume_optimizer all get this by going through `get_default_llm_client()` with no
    changes needed in the nodes themselves.
    """

    def __init__(
        self,
        model: str = "gemini-flash-latest",
        max_retries: int = 3,
        initial_backoff_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._model = model
        self._max_retries = max_retries
        self._initial_backoff_seconds = initial_backoff_seconds
        self._sleep = sleep

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return _call_with_retries(
            lambda: asyncio.run(self._complete_async(system_prompt, user_prompt)),
            max_retries=self._max_retries,
            initial_backoff_seconds=self._initial_backoff_seconds,
            sleep=self._sleep,
        )

    async def _complete_async(self, system_prompt: str, user_prompt: str) -> str:
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        agent = LlmAgent(name="jobmatch_llm_node", model=self._model, instruction=system_prompt)
        session_service = InMemorySessionService()
        app_name, user_id, session_id = "jobmatch-ai", "agent", str(uuid.uuid4())
        await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

        final_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=user_prompt)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
        return final_text


def get_default_llm_client() -> LLMClient:
    return AdkLlmClient()
