"""Orchestrator: builds and compiles the LangGraph StateGraph."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from quada.agents.interpret import InterpretAgent
from quada.agents.quality import QualityAgent
from quada.agents.semantic_query import SemanticQueryAgent
from quada.cli.display import (
    print_agent_escalate,
    print_agent_execute,
    print_agent_interpret,
    print_agent_quality,
    print_agent_semantic,
)
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
    verbose: bool = True,
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
        result = run_semantic_query_node(state, semantic_agent, project_dir)
        if verbose:
            print_agent_semantic({**state, **result})
        return result

    def quality_node(state: QuadaState) -> dict:
        result = run_quality_node(state, quality_agent)
        if verbose:
            print_agent_quality({**state, **result})
        return result

    def execute_node(state: QuadaState) -> dict:
        result = run_execute_node(state, executor)
        if verbose:
            print_agent_execute({**state, **result})
        return result

    def interpret_node(state: QuadaState) -> dict:
        result = run_interpret_node(state, interpret_agent)
        if verbose:
            print_agent_interpret({**state, **result})
        return result

    def escalate_node(state: QuadaState) -> dict:
        result = run_escalate_node(state)
        if verbose:
            print_agent_escalate({**state, **result})
        return result

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
