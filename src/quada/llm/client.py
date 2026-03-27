"""LiteLLM wrapper with per-agent model configuration."""

import re

from litellm import completion as litellm_completion

from quada.core.config import LLMConfig


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM responses."""
    stripped = re.sub(r"^```\w*\n?", "", text.strip())
    stripped = re.sub(r"\n?```$", "", stripped.strip())
    return stripped.strip()


class LLMClient:
    """Unified LLM client that routes to the correct model per agent role."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def get_model_string(self, role: str) -> str:
        """Get the LiteLLM model string for a given role."""
        if role == "orchestrator":
            cfg = self.config.orchestrator
        elif hasattr(self.config.agents, role):
            cfg = getattr(self.config.agents, role)
        else:
            raise ValueError(f"Unknown role: {role}")
        return f"{cfg.provider}/{cfg.model}"

    def completion(self, role: str, messages: list[dict]) -> str:
        """Call LLM completion for the given role."""
        model = self.get_model_string(role)
        response = litellm_completion(model=model, messages=messages)
        content = response.choices[0].message.content
        return _strip_code_fences(content)
