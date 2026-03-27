"""quality_node logic: wraps QualityAgent.run() for LangGraph."""

from quada.agents.quality import QualityAgent
from quada.core.state import QuadaState


def run_quality_node(state: QuadaState, agent: QualityAgent) -> dict:
    """Run quality agent."""
    return agent.run(state)
