"""Orchestrator: coordinates agents, manages execution flow."""

import json
from dataclasses import dataclass

from quada.agents.interpret import InterpretAgent, InterpretResult
from quada.agents.quality import QualityAgent, QualityAnalysis
from quada.agents.semantic_query import SemanticQueryAgent, SQLGenerationResult
from quada.db.executor import SQLExecutor
from quada.llm.client import LLMClient
from quada.llm.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from quada.quality.engine import QualityCheckResult
from quada.semantic.models import QualityRule


@dataclass
class OrchestratorResult:
    sql: str
    query_results: list[dict]
    quality_check: QualityCheckResult | None
    quality_analysis: QualityAnalysis | None
    interpret_result: InterpretResult
    sql_generation: SQLGenerationResult


class Orchestrator:
    """Coordinates the 3-agent pipeline: Semantic Query → Quality → Interpret."""

    def __init__(
        self,
        llm_client: LLMClient,
        semantic_agent: SemanticQueryAgent,
        quality_agent: QualityAgent,
        interpret_agent: InterpretAgent,
        executor: SQLExecutor,
        quality_rules: list[QualityRule],
    ):
        self.llm_client = llm_client
        self.semantic_agent = semantic_agent
        self.quality_agent = quality_agent
        self.interpret_agent = interpret_agent
        self.executor = executor
        self.quality_rules = quality_rules

    async def run(
        self,
        user_query: str,
        skip_quality: bool = False,
    ) -> OrchestratorResult:
        """Run the full pipeline: semantic → quality → execute → interpret."""

        # Step 1: Parse intent via LLM
        intent_response = self.llm_client.completion(
            role="orchestrator",
            messages=[
                {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
        )

        # Step 2: Semantic Query Agent generates SQL
        sql_result = self.semantic_agent.generate_sql(user_query)

        # Step 3: Quality check (unless skipped)
        quality_check = None
        quality_analysis = None
        if not skip_quality and self.quality_rules:
            # Extract table names from SQL result
            tables = sql_result.tables_used
            # Strip schema prefix for rule matching
            table_names = [t.split(".")[-1] for t in tables]

            quality_check = await self.quality_agent.engine.check(
                rules=self.quality_rules,
                tables=table_names,
                where_clause=None,
            )

            if quality_check.overall_status != "pass":
                quality_analysis = self.quality_agent.analyze_impact(
                    check_result=quality_check,
                    sql=sql_result.sql,
                    user_query=user_query,
                )

        # Step 4: Execute SQL
        query_results = self.executor.execute(sql_result.sql)

        # Step 5: Interpret results
        interpret_result = self.interpret_agent.interpret(
            query_results=query_results,
            sql=sql_result.sql,
            user_query=user_query,
            quality_analysis=quality_analysis,
        )

        return OrchestratorResult(
            sql=sql_result.sql,
            query_results=query_results,
            quality_check=quality_check,
            quality_analysis=quality_analysis,
            interpret_result=interpret_result,
            sql_generation=sql_result,
        )
