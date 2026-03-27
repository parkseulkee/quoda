"""semantic_query_node logic: wraps SemanticQueryAgent.run() for LangGraph."""

from pathlib import Path

from quada.agents.semantic_query import SemanticQueryAgent
from quada.core.state import QuadaState
from quada.semantic.index import MetadataIndex


def run_semantic_query_node(
    state: QuadaState,
    agent: SemanticQueryAgent,
    project_dir: Path,
) -> dict:
    """Run semantic query agent. Loads metadata index from .quada/."""
    index = MetadataIndex.load(project_dir / ".quada")
    return agent.run(state, index)
