"""Semantic Query Agent: resolves terms, generates SQL, executes queries."""

import json
from dataclasses import dataclass

from quada.agents.base import BaseAgent
from quada.llm.client import LLMClient
from quada.llm.prompts import SEMANTIC_QUERY_SYSTEM_PROMPT
from quada.semantic.loader import SemanticContext
from quada.semantic.matcher import SemanticMatcher


@dataclass
class SQLGenerationResult:
    sql: str
    tables_used: list[str]
    resolved_terms: dict[str, str]
    explanation: str


class SemanticQueryAgent(BaseAgent):
    """Resolves semantic terms and generates SQL."""

    def __init__(
        self,
        llm_client: LLMClient,
        semantic_context: SemanticContext,
        matcher: SemanticMatcher,
    ):
        super().__init__(
            role="semantic_query",
            llm_client=llm_client,
            system_prompt=SEMANTIC_QUERY_SYSTEM_PROMPT,
        )
        self.context = semantic_context
        self.matcher = matcher

    def generate_sql(self, user_query: str) -> SQLGenerationResult:
        """Generate SQL from a natural language query using semantic context."""
        context_data = self._build_context(user_query)
        response = self.call_llm(user_query, context=context_data)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            data = {"sql": response, "tables_used": [], "resolved_terms": {}, "explanation": ""}

        return SQLGenerationResult(
            sql=data.get("sql", ""),
            tables_used=data.get("tables_used", []),
            resolved_terms=data.get("resolved_terms", {}),
            explanation=data.get("explanation", ""),
        )

    def _build_context(self, user_query: str) -> dict:
        """Build semantic context for the LLM."""
        entities_info = []
        for entity in self.context.entities:
            cols = [{"name": c.name, "type": c.type} for c in entity.columns]
            rels = [{"name": r.name, "entity": r.entity, "join": r.join} for r in entity.relationships]
            entities_info.append({
                "name": entity.name,
                "table": entity.table,
                "columns": cols,
                "relationships": rels,
            })

        metrics_info = []
        for metric in self.context.metrics:
            metrics_info.append({
                "name": metric.name,
                "description": metric.description,
                "expression": getattr(metric, "expression", ""),
                "filter": getattr(metric, "filter", ""),
                "aliases": metric.aliases,
            })

        glossary_info = []
        for term in self.context.glossary:
            glossary_info.append({
                "term": term.term,
                "definition": term.definition,
                "sql_condition": term.sql_condition,
                "entity": term.entity,
            })

        return {
            "entities": entities_info,
            "metrics": metrics_info,
            "glossary": glossary_info,
        }
