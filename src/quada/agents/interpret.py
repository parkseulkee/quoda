"""Interpret Agent: summarizes results, provides insights, generates charts."""

import json
from dataclasses import dataclass

from quada.agents.base import BaseAgent
from quada.llm.client import LLMClient
from quada.llm.prompts import INTERPRET_AGENT_SYSTEM_PROMPT


@dataclass
class InterpretResult:
    summary: str
    insights: list[str]
    quality_note: str | None
    follow_up_questions: list[str]


class InterpretAgent(BaseAgent):
    """Interprets query results with natural language summary and insights."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(
            role="interpret",
            llm_client=llm_client,
            system_prompt=INTERPRET_AGENT_SYSTEM_PROMPT,
        )

    def interpret(
        self,
        query_results: list[dict],
        sql: str,
        user_query: str,
        quality_analysis: dict | None = None,
    ) -> InterpretResult:
        """Interpret query results with quality context."""
        context = {
            "user_query": user_query,
            "sql": sql,
            "results": query_results[:50],  # Limit to avoid token overflow
            "row_count": len(query_results),
        }
        if quality_analysis:
            context["quality"] = quality_analysis

        response = self.call_llm("Interpret these query results.", context=context)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return InterpretResult(
                summary=response,
                insights=[],
                quality_note=None,
                follow_up_questions=[],
            )

        return InterpretResult(
            summary=data.get("summary", ""),
            insights=data.get("insights", []),
            quality_note=data.get("quality_note"),
            follow_up_questions=data.get("follow_up_questions", []),
        )
