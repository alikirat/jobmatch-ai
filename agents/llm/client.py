"""LLM client abstraction so score nodes don't couple directly to a specific SDK.

Nodes accept an `LLMClient` via dependency injection and default to `get_default_llm_client()`
when none is given. Tests inject a stub implementing `complete()`, so they never construct
the default client and never need google-adk installed or a live API key.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text response for a single-turn system+user prompt."""
        ...


class AdkLlmClient:
    """Default LLMClient, backed by a Google ADK LlmAgent run through a Runner."""

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        self._model = model

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return asyncio.run(self._complete_async(system_prompt, user_prompt))

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
