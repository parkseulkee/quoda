"""Interpret Agent: summarizes results and generates insights via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.llm.client import LLMClient
from quada.llm.prompts import INTERPRET_AGENT_SYSTEM_PROMPT
from quada.tools.base import TerminalResult
from quada.tools.interpret_tools import finalize_interpretation, render_chart

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "render_chart",
            "description": "Render a CLI chart from query results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Query result rows",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line"],
                        "description": "Chart type",
                    },
                },
                "required": ["rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_interpretation",
            "description": "Call this when you have completed the interpretation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "insights": {"type": "array", "items": {"type": "string"}},
                    "follow_up_questions": {"type": "array", "items": {"type": "string"}},
                    "quality_note": {"type": "string"},
                },
                "required": ["summary", "insights", "follow_up_questions"],
            },
        },
    },
]


class InterpretAgent(BaseAgent):
    """Interprets query results with natural language summary and insights."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(
            role="interpret",
            llm_client=llm_client,
            system_prompt=INTERPRET_AGENT_SYSTEM_PROMPT,
        )

    def run(self, state: QuadaState) -> dict:
        """Run interpretation tool loop. Returns state updates dict."""
        quality_context = ""
        if state.get("quality_results"):
            failed = [r for r in state["quality_results"] if r.get("status") != "pass"]
            if failed:
                quality_context = f"\nQuality warnings: {failed}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"User query: {state['user_query']}\n"
                    f"SQL executed: {state.get('sql', '')}\n"
                    f"Results ({len(state['query_results'])} rows): "
                    f"{state['query_results'][:50]}"
                    f"{quality_context}"
                ),
            },
        ]

        # Capture chart output from render_chart calls
        last_chart: list[str | None] = [None]

        def render_chart_with_capture(**kwargs) -> str:
            result = render_chart(**kwargs)
            last_chart[0] = result
            return result

        def finalize_with_chart(**kwargs) -> TerminalResult:
            terminal = finalize_interpretation(**kwargs)
            # Inject captured chart into interpretation state
            if last_chart[0] and terminal.state_updates.get("interpretation"):
                terminal.state_updates["interpretation"]["chart"] = last_chart[0]
            return terminal

        tool_executors = {
            "render_chart": render_chart_with_capture,
            "finalize_interpretation": finalize_with_chart,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        result = {"stop_reason": stop_reason or "done"}
        if state_updates:
            result.update(state_updates)
        return result
