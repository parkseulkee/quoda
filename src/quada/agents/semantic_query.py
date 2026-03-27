"""Semantic Query Agent: resolves terms and generates SQL via tool call loop."""

from quada.agents.base import BaseAgent
from quada.core.state import QuadaState
from quada.llm.client import LLMClient
from quada.llm.prompts import SEMANTIC_QUERY_SYSTEM_PROMPT
from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticContext
from quada.tools.semantic_tools import (
    get_entity_definition,
    get_metric_definition,
    get_glossary_term,
    generate_sql,
    report_term_not_found,
)

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_entity_definition",
            "description": "Get full entity schema (columns, relationships, table name) by entity name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Entity name from the metadata index"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_definition",
            "description": "Get full metric definition (expression, filter, dimensions) by metric name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Metric name from the metadata index"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_glossary_term",
            "description": "Get full glossary term definition (sql_condition, entity) by term name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Glossary term from the metadata index"}
                },
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_sql",
            "description": "Commit the final SQL you have generated. Call this when you have gathered all needed context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "The SQL query you generated"},
                    "tables_used": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of table names used in the SQL",
                    },
                    "resolved_terms": {
                        "type": "object",
                        "description": "Map of user terms to their resolved definitions",
                    },
                },
                "required": ["sql", "tables_used", "resolved_terms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_term_not_found",
            "description": "Call this when a term cannot be resolved from the metadata index. Triggers user escalation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "The term that could not be resolved"},
                    "question": {"type": "string", "description": "Question to ask the user for clarification"},
                },
                "required": ["term", "question"],
            },
        },
    },
]


class SemanticQueryAgent(BaseAgent):
    """Resolves semantic terms from metadata index and generates SQL via tool call loop."""

    def __init__(self, llm_client: LLMClient, semantic_context: SemanticContext):
        super().__init__(
            role="semantic_query",
            llm_client=llm_client,
            system_prompt=SEMANTIC_QUERY_SYSTEM_PROMPT,
        )
        self.context = semantic_context

    def run(self, state: QuadaState, index: MetadataIndex) -> dict:
        """Run tool call loop. Returns state updates dict."""
        clarification = state.get("user_clarification")

        user_content = (
            f"User query: {state['user_query']}\n\n"
            f"Metadata Index (use this to decide which definitions to look up):\n"
            f"{index.to_json_string()}"
        )
        if clarification:
            user_content += f"\n\nUser clarification: {clarification}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        tool_executors = {
            "get_entity_definition": lambda name: get_entity_definition(name, self.context),
            "get_metric_definition": lambda name: get_metric_definition(name, self.context),
            "get_glossary_term": lambda term: get_glossary_term(term, self.context),
            "generate_sql": generate_sql,
            "report_term_not_found": report_term_not_found,
        }

        stop_reason, state_updates = self.run_tool_loop(
            messages=messages,
            tool_definitions=_TOOL_DEFINITIONS,
            tool_executors=tool_executors,
        )

        if stop_reason is None:
            return {
                "stop_reason": "term_not_found",
                "escalation_question": "쿼리를 처리할 수 없습니다. 질문을 다시 작성해주세요.",
            }

        return {"stop_reason": stop_reason, **state_updates}
