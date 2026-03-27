"""Quality Agent: runs quality checks and analyzes impact via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.llm.prompts import QUALITY_AGENT_SYSTEM_PROMPT
from quada.semantic.models import QualityRule
from quada.tools.quality_tools import (
    get_quality_rules,
    run_quality_checks,
    report_quality_passed,
    report_quality_warning,
)

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_quality_rules",
            "description": "Get quality rules applicable to the given tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Table names to get rules for",
                    }
                },
                "required": ["tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_quality_checks",
            "description": "Run all quality checks for the given tables and return results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Table names to check",
                    }
                },
                "required": ["tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_quality_passed",
            "description": "Call this when all quality checks pass. Proceeds to SQL execution.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_quality_warning",
            "description": "Call this when quality issues are found. Include impact analysis in the message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Impact analysis: what quality issues were found and how they affect the query",
                    },
                    "question": {
                        "type": "string",
                        "description": "Question to ask the user (e.g. 'Quality warning found. Proceed? (y/n)')",
                    },
                },
                "required": ["message", "question"],
            },
        },
    },
]


class QualityAgent(BaseAgent):
    """Runs quality checks and analyzes their impact via tool call loop."""

    def __init__(self, llm_client: LLMClient, rules: list[QualityRule], executor: SQLExecutor):
        super().__init__(
            role="quality",
            llm_client=llm_client,
            system_prompt=QUALITY_AGENT_SYSTEM_PROMPT,
        )
        self.rules = rules
        self.executor = executor

    def run(self, state: QuadaState) -> dict:
        """Run quality check tool loop. Returns state updates dict."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"SQL to execute: {state['sql']}\n"
                    f"Tables used: {state['tables_used']}\n"
                    f"User query: {state['user_query']}\n\n"
                    "Run quality checks on the tables and analyze their impact on this query."
                ),
            },
        ]

        tool_executors = {
            "get_quality_rules": lambda tables: get_quality_rules(tables, self.rules),
            "run_quality_checks": lambda tables: run_quality_checks(tables, self.rules, self.executor),
            "report_quality_passed": lambda: report_quality_passed(),
            "report_quality_warning": report_quality_warning,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        if stop_reason is None:
            return {"stop_reason": "quality_passed"}

        result = {"stop_reason": stop_reason}
        if state_updates:
            result.update(state_updates)
        return result
