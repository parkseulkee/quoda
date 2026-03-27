"""Quality Agent: runs quality checks and analyzes impact via LLM."""

import json
from dataclasses import dataclass

from quada.agents.base import BaseAgent
from quada.llm.client import LLMClient
from quada.llm.prompts import QUALITY_AGENT_SYSTEM_PROMPT
from quada.quality.engine import QualityEngine, QualityCheckResult


@dataclass
class QualityIssue:
    rule: str
    status: str
    impact: str
    estimated_error: str


@dataclass
class QualityAnalysis:
    overall_status: str
    issues: list[QualityIssue]
    recommendation: str


class QualityAgent(BaseAgent):
    """Runs quality checks and analyzes their impact on the query."""

    def __init__(self, llm_client: LLMClient, engine: QualityEngine):
        super().__init__(
            role="quality",
            llm_client=llm_client,
            system_prompt=QUALITY_AGENT_SYSTEM_PROMPT,
        )
        self.engine = engine

    def analyze_impact(
        self,
        check_result: QualityCheckResult,
        sql: str,
        user_query: str,
    ) -> QualityAnalysis:
        """Analyze the impact of quality issues on the query results."""
        if check_result.overall_status == "pass":
            # Still ask LLM for confirmation but provide pass context
            pass

        context = {
            "quality_results": [
                {"rule": r.rule_name, "status": r.status, "message": r.message, "value": r.value}
                for r in check_result.results
            ],
            "sql": sql,
            "user_query": user_query,
        }

        response = self.call_llm(
            "Analyze the impact of these quality check results on the query.",
            context=context,
        )

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return QualityAnalysis(
                overall_status=check_result.overall_status,
                issues=[],
                recommendation=response,
            )

        issues = [
            QualityIssue(
                rule=i.get("rule", ""),
                status=i.get("status", ""),
                impact=i.get("impact", ""),
                estimated_error=i.get("estimated_error", ""),
            )
            for i in data.get("issues", [])
        ]

        return QualityAnalysis(
            overall_status=data.get("overall_status", check_result.overall_status),
            issues=issues,
            recommendation=data.get("recommendation", ""),
        )
