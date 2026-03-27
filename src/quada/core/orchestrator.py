"""Orchestrator: builds and compiles the LangGraph StateGraph."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from quada.agents.interpret import InterpretAgent
from quada.agents.quality import QualityAgent
from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.nodes.escalate import run_escalate_node
from quada.nodes.execute import run_execute_node
from quada.nodes.interpret import run_interpret_node
from quada.nodes.quality import run_quality_node
from quada.nodes.semantic_query import run_semantic_query_node
from quada.semantic.loader import SemanticContext


def build_graph(
    llm_client: LLMClient,
    semantic_context: SemanticContext,
    executor: SQLExecutor,
    project_dir: Path,
):
    """Build and compile the LangGraph StateGraph.

    Returns a compiled graph with MemorySaver checkpointer for interrupt() support.
    Each node is a closure capturing its dependencies — no global state.
    """
    semantic_agent = SemanticQueryAgent(llm_client=llm_client, semantic_context=semantic_context)
    quality_agent = QualityAgent(
        llm_client=llm_client,
        rules=semantic_context.quality.rules,
        executor=executor,
    )
    interpret_agent = InterpretAgent(llm_client=llm_client)

    def semantic_query_node(state: QuadaState) -> dict:
        return run_semantic_query_node(state, semantic_agent, project_dir)

    def quality_node(state: QuadaState) -> dict:
        return run_quality_node(state, quality_agent)

    def execute_node(state: QuadaState) -> dict:
        return run_execute_node(state, executor)

    def interpret_node(state: QuadaState) -> dict:
        return run_interpret_node(state, interpret_agent)

    def escalate_node(state: QuadaState) -> dict:
        return run_escalate_node(state)

    def route(state: QuadaState) -> str:
        return state["stop_reason"]

    graph = StateGraph(QuadaState)

    graph.add_node("semantic_query", semantic_query_node)
    graph.add_node("quality", quality_node)
    graph.add_node("execute", execute_node)
    graph.add_node("interpret", interpret_node)
    graph.add_node("escalate", escalate_node)

    graph.set_entry_point("semantic_query")

    graph.add_conditional_edges("semantic_query", route, {
        "sql_generated": "quality",
        "term_not_found": "escalate",
    })
    graph.add_conditional_edges("quality", route, {
        "quality_passed": "execute",
        "quality_warning": "escalate",
    })
    graph.add_conditional_edges("execute", route, {
        "executed": "interpret",
        "sql_error": "escalate",
    })
    graph.add_conditional_edges("interpret", route, {
        "done": END,
    })
    graph.add_conditional_edges("escalate", route, {
        "term_clarified": "semantic_query",
        "sql_retry": "semantic_query",
        "execute_approved": "execute",
        "escalation_done": END,
    })

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Compatibility stub — Task 12 will replace cli/app.py's Orchestrator usage.
# Importing this name must not raise ImportError so test collection succeeds.
# ---------------------------------------------------------------------------
class Orchestrator:
    """Deprecated stub. Use build_graph() instead. Removed in Task 12."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Orchestrator has been replaced by build_graph(). "
            "See quada.core.orchestrator.build_graph."
        )
