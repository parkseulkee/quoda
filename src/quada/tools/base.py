"""TerminalResult: returned by terminal tools to end the tool call loop."""

from dataclasses import dataclass, field


@dataclass
class TerminalResult:
    """Tool이 반환하면 tool call loop가 종료되고 state_updates가 QuadaState에 반영된다."""
    stop_reason: str
    state_updates: dict = field(default_factory=dict)
    display_value: str = ""
