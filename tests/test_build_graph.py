"""Tests for build_graph — validates graph structure and routing."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from quada.core.orchestrator import build_graph
from quada.core.state import QuadaState


def _make_deps(tmp_path):
    mock_llm = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.quality.rules = []
    mock_executor = MagicMock()
    return mock_llm, mock_ctx, mock_executor, tmp_path


def test_build_graph_returns_compiled_graph(tmp_path):
    llm, ctx, executor, project_dir = _make_deps(tmp_path)
    graph = build_graph(
        llm_client=llm,
        semantic_context=ctx,
        executor=executor,
        project_dir=project_dir,
    )
    assert hasattr(graph, "invoke")


def test_graph_full_flow_happy_path(tmp_path):
    """sql_generated → quality_passed → executed → done."""
    llm, ctx, executor, project_dir = _make_deps(tmp_path)

    quada_dir = tmp_path / ".quada"
    quada_dir.mkdir()
    (quada_dir / "metadata_index.json").write_text('{"entities":[],"metrics":[],"glossary":[]}')

    graph = build_graph(
        llm_client=llm,
        semantic_context=ctx,
        executor=executor,
        project_dir=project_dir,
    )

    with patch("quada.agents.semantic_query.SemanticQueryAgent.run") as mock_sem, \
         patch("quada.agents.quality.QualityAgent.run") as mock_qual, \
         patch("quada.agents.interpret.InterpretAgent.run") as mock_interp:

        mock_sem.return_value = {
            "sql": "SELECT 1",
            "tables_used": ["orders"],
            "resolved_terms": {},
            "stop_reason": "sql_generated",
        }
        mock_qual.return_value = {"stop_reason": "quality_passed"}
        executor.execute.return_value = [{"count": 1}]
        mock_interp.return_value = {"stop_reason": "done"}

        initial_state: QuadaState = {
            "user_query": "고객 수",
            "sql": None, "tables_used": [], "resolved_terms": {},
            "quality_results": [], "query_results": [], "error": None,
            "escalation_question": None, "user_clarification": None,
            "stop_reason": None,
        }

        result = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": "test-happy"}},
        )

    assert result["stop_reason"] == "done"
    mock_sem.assert_called_once()
    mock_qual.assert_called_once()
    mock_interp.assert_called_once()
