"""Semantic tools: pure functions used by SemanticQueryAgent's tool call loop."""

from quada.semantic.loader import SemanticContext
from quada.tools.base import TerminalResult


def get_entity_definition(name: str, context: SemanticContext) -> dict:
    """Get full entity definition (columns, relationships, table name).

    Called by LLM when it decides it needs schema info for a specific entity.
    """
    for entity in context.entities:
        if entity.name.lower() == name.lower():
            return {
                "name": entity.name,
                "table": entity.table,
                "description": entity.description,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "primary_key": c.primary_key,
                        "description": c.description,
                    }
                    for c in entity.columns
                ],
                "relationships": [
                    {
                        "name": r.name,
                        "type": r.type,
                        "entity": r.entity,
                        "join": r.join,
                    }
                    for r in entity.relationships
                ],
            }
    return {"error": f"Entity '{name}' not found in semantic layer."}


def get_metric_definition(name: str, context: SemanticContext) -> dict:
    """Get full metric definition (expression, filter, dimensions).

    Called by LLM when it identifies a metric in the user query.
    """
    for metric in context.metrics:
        if metric.name.lower() == name.lower():
            result = {
                "name": metric.name,
                "description": metric.description,
                "expression": getattr(metric, "expression", ""),
                "entities": getattr(metric, "entities", []),
            }
            if hasattr(metric, "filter") and metric.filter:
                result["filter"] = metric.filter
            if hasattr(metric, "dimensions"):
                result["dimensions"] = [
                    {"name": d.name, "expression": d.expression}
                    for d in metric.dimensions
                ]
            return result
    return {"error": f"Metric '{name}' not found in semantic layer."}


def get_glossary_term(term: str, context: SemanticContext) -> dict:
    """Get full glossary term definition (sql_condition, entity, definition).

    Called by LLM when it encounters a business term in the user query.
    """
    for t in context.glossary:
        if t.term.lower() == term.lower():
            return {
                "term": t.term,
                "definition": t.definition,
                "sql_condition": t.sql_condition,
                "entity": t.entity,
            }
    return {"error": f"Glossary term '{term}' not found."}


def generate_sql(
    sql: str,
    tables_used: list[str],
    resolved_terms: dict,
) -> TerminalResult:
    """Terminal tool: LLM commits the SQL it generated.

    The LLM calls this tool when it has gathered enough context and generated SQL.
    sql, tables_used, resolved_terms are provided by the LLM in the tool call arguments.
    """
    return TerminalResult(
        stop_reason="sql_generated",
        state_updates={
            "sql": sql,
            "tables_used": tables_used,
            "resolved_terms": resolved_terms,
        },
        display_value=f"SQL committed: {sql[:100]}{'...' if len(sql) > 100 else ''}",
    )


def report_term_not_found(term: str, question: str) -> TerminalResult:
    """Terminal tool: LLM signals that a term cannot be resolved.

    Triggers escalation to ask user for the definition.
    """
    return TerminalResult(
        stop_reason="term_not_found",
        state_updates={"escalation_question": question},
        display_value=f"Escalating: term '{term}' not found.",
    )
