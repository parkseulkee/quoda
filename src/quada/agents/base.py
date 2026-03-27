"""Base agent with tool call loop support."""

import json
from typing import Any

from quada.llm.client import LLMClient
from quada.tools.base import TerminalResult


class BaseAgent:
    """Base class for quada agents. Provides tool call loop via run_tool_loop()."""

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

    def run_tool_loop(
        self,
        messages: list[dict],
        tool_definitions: list[dict],
        tool_executors: dict[str, Any],
    ) -> tuple[str | None, dict]:
        """Run ReAct tool call loop until LLM stops or a TerminalResult is returned.

        Args:
            messages: Initial messages (system + user). Modified in-place during loop.
            tool_definitions: OpenAI-format tool schemas.
            tool_executors: {tool_name: callable(**args) -> str | dict | TerminalResult}

        Returns:
            (stop_reason, state_updates)
            stop_reason is None if LLM stopped calling tools without a terminal tool.
        """
        max_iterations = 20
        for _ in range(max_iterations):
            msg_dict, tool_calls = self.llm_client.completion_with_tools(
                role=self.role,
                messages=messages,
                tools=tool_definitions,
            )
            messages.append(msg_dict)

            if not tool_calls:
                return None, {}

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                executor = tool_executors.get(tool_name)
                if executor is None:
                    result_content = f"Error: unknown tool '{tool_name}'"
                    messages.append({"role": "tool", "tool_call_id": tool_id, "content": result_content})
                    continue

                result = executor(**tool_args)

                if isinstance(result, TerminalResult):
                    messages.append({"role": "tool", "tool_call_id": tool_id, "content": result.display_value})
                    return result.stop_reason, result.state_updates

                if isinstance(result, dict):
                    result_content = json.dumps(result, ensure_ascii=False)
                else:
                    result_content = str(result)

                messages.append({"role": "tool", "tool_call_id": tool_id, "content": result_content})

        raise RuntimeError(
            f"Tool call loop exceeded {max_iterations} iterations without a terminal tool call. "
            "The agent may be stuck in a loop."
        )
