"""Base agent with shared LLM calling logic."""

import json

from quada.llm.client import LLMClient


class BaseAgent:
    """Base class for all quada agents."""

    def __init__(self, role: str, llm_client: LLMClient, system_prompt: str):
        self.role = role
        self.llm_client = llm_client
        self.system_prompt = system_prompt

    def call_llm(self, user_message: str, context: dict | None = None) -> str:
        """Call the LLM with system prompt and user message."""
        full_message = user_message
        if context:
            full_message = f"{user_message}\n\nContext:\n{json.dumps(context, ensure_ascii=False, indent=2)}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": full_message},
        ]
        return self.llm_client.completion(role=self.role, messages=messages)
