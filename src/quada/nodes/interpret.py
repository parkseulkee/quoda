"""interpret_node logic: wraps InterpretAgent.run() for LangGraph."""

from quada.agents.interpret import InterpretAgent
from quada.core.state import QuadaState


def run_interpret_node(state: QuadaState, agent: InterpretAgent) -> dict:
    """Run interpret agent."""
    return agent.run(state)
