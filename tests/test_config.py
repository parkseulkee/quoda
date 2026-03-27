import os
from pathlib import Path

import pytest

from quada.core.config import load_config, QuadaConfig, DatabaseConfig, LLMConfig


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_valid_config():
    config = load_config(FIXTURES / "quada_valid.yaml")
    assert isinstance(config, QuadaConfig)
    assert config.database.type == "postgresql"
    assert config.database.host == "localhost"
    assert config.database.port == 5432
    assert config.llm.orchestrator.provider == "anthropic"
    assert config.llm.orchestrator.model == "claude-opus-4-6"
    assert config.llm.agents.semantic_query.provider == "anthropic"


def test_load_config_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_DB_USER", "envuser")
    monkeypatch.setenv("TEST_DB_PASS", "envpass")
    yaml_content = """
database:
  type: postgresql
  host: localhost
  port: 5432
  name: testdb
  user: ${TEST_DB_USER}
  password: ${TEST_DB_PASS}
semantic_layer:
  source: local
llm:
  orchestrator:
    provider: anthropic
    model: claude-opus-4-6
  agents:
    semantic_query:
      provider: anthropic
      model: claude-haiku-4-5-20251001
    quality:
      provider: openai
      model: gpt-4o-mini
    interpret:
      provider: anthropic
      model: claude-sonnet-4-6
"""
    config_file = tmp_path / "quada.yaml"
    config_file.write_text(yaml_content)
    config = load_config(config_file)
    assert config.database.user == "envuser"
    assert config.database.password == "envpass"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/quada.yaml"))


def test_load_config_invalid_yaml(tmp_path):
    config_file = tmp_path / "quada.yaml"
    config_file.write_text("database:\n  type: postgresql\n")
    with pytest.raises(Exception):
        load_config(config_file)
