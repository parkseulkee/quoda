"""Orchestrator tests — superseded by test_build_graph.py.

The Orchestrator class was replaced by build_graph() in Task 11.
These tests are kept as skipped stubs until Task 12 removes the stub entirely.
"""
import pytest


@pytest.mark.skip(reason="Orchestrator class removed; see test_build_graph.py")
def test_orchestrator_run():
    pass


@pytest.mark.skip(reason="Orchestrator class removed; see test_build_graph.py")
def test_orchestrator_skip_quality():
    pass
