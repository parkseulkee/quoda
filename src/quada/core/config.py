"""Load and validate quada.yaml configuration."""

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR_NAME} patterns with environment variable values."""
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable '{var_name}' is not set")
        return env_value
    return re.sub(r"\$\{(\w+)}", replacer, value)


def _expand_env_recursive(data: dict | list | str) -> dict | list | str:
    """Recursively expand environment variables in a data structure."""
    if isinstance(data, dict):
        return {k: _expand_env_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env_recursive(item) for item in data]
    if isinstance(data, str) and "${" in data:
        return _expand_env_vars(data)
    return data


class DatabaseConfig(BaseModel):
    type: str
    host: str
    port: int = 5432
    name: str
    user: str
    password: str


class LLMModelConfig(BaseModel):
    provider: str
    model: str


class AgentsLLMConfig(BaseModel):
    semantic_query: LLMModelConfig
    quality: LLMModelConfig
    interpret: LLMModelConfig


class LLMConfig(BaseModel):
    orchestrator: LLMModelConfig
    agents: AgentsLLMConfig


class SemanticLayerConfig(BaseModel):
    source: str = "local"


class QuadaConfig(BaseModel):
    database: DatabaseConfig
    semantic_layer: SemanticLayerConfig = SemanticLayerConfig()
    llm: LLMConfig


def load_config(path: Path) -> QuadaConfig:
    """Load and validate quada.yaml from the given path."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    expanded = _expand_env_recursive(raw)
    return QuadaConfig(**expanded)
