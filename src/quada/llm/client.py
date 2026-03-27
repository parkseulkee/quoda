"""LiteLLM wrapper with per-agent model configuration and tool calling support."""

import json
import re

from litellm import completion as litellm_completion

from quada.core.config import LLMConfig


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM responses."""
    stripped = re.sub(r"^```\w*\n?", "", text.strip())
    stripped = re.sub(r"\n?```$", "", stripped.strip())
    return stripped.strip()


class LLMClient:
    """Unified LLM client that routes to the correct model per agent role."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def get_model_string(self, role: str) -> str:
        """Get the LiteLLM model string for a given role."""
        if role == "orchestrator":
            cfg = self.config.orchestrator
        elif hasattr(self.config.agents, role):
            cfg = getattr(self.config.agents, role)
        else:
            raise ValueError(f"Unknown role: {role}")
        return f"{cfg.provider}/{cfg.model}"

    def completion(self, role: str, messages: list[dict]) -> str:
        """Call LLM completion for the given role."""
        model = self.get_model_string(role)
        response = litellm_completion(model=model, messages=messages)
        content = response.choices[0].message.content
        return _strip_code_fences(content)

    def completion_with_tools(
        self,
        role: str,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[dict, list[dict]]:
        """Call LLM with tool definitions.

        Returns:
            (message_dict, tool_calls)
            message_dict: {"role": "assistant", "content": ..., "tool_calls": [...]}
            tool_calls: [{"name": str, "args": dict, "id": str}, ...]
        """
        model = self.get_model_string(role)
        kwargs: dict = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = litellm_completion(**kwargs)
        message = response.choices[0].message

        msg_dict: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id,
                })

        return msg_dict, tool_calls
