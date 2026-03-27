"""3-stage semantic matching: Exact → Fuzzy (LLM) → No Match, with alias learning."""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from quada.semantic.models import GlossaryTerm, Metric, DerivedMetric
from quada.llm.client import LLMClient
from quada.llm.prompts import FUZZY_MATCH_PROMPT_TEMPLATE


@dataclass
class MatchResult:
    matched: bool
    match_type: str  # "exact", "fuzzy", "none"
    source_type: str = ""  # "glossary", "metric", ""
    term: GlossaryTerm | None = None
    metric: Metric | DerivedMetric | None = None
    confidence: str = ""  # "high", "medium", "low", "none"


class SemanticMatcher:
    """Matches natural language terms against glossary and metrics."""

    def __init__(
        self,
        glossary: list[GlossaryTerm],
        metrics: list[Metric | DerivedMetric],
        llm_client: LLMClient,
    ):
        self.glossary = glossary
        self.metrics = metrics
        self.llm_client = llm_client
        self._build_index()

    def _build_index(self) -> None:
        """Build lookup indexes for fast exact matching."""
        self._glossary_index: dict[str, GlossaryTerm] = {}
        for term in self.glossary:
            self._glossary_index[term.term.lower()] = term
            for alias in term.aliases:
                self._glossary_index[alias.lower()] = term

        self._metric_index: dict[str, Metric | DerivedMetric] = {}
        for metric in self.metrics:
            self._metric_index[metric.name.lower()] = metric
            for alias in metric.aliases:
                self._metric_index[alias.lower()] = metric

    def match_term(self, user_term: str) -> MatchResult:
        """Match a user term against glossary (exact then fuzzy)."""
        # Step 1: Exact match
        key = user_term.lower()
        if key in self._glossary_index:
            return MatchResult(
                matched=True,
                match_type="exact",
                source_type="glossary",
                term=self._glossary_index[key],
            )

        # Step 2: Fuzzy match via LLM
        return self._fuzzy_match_term(user_term)

    def match_metric(self, user_term: str) -> MatchResult:
        """Match a user term against metrics (exact only for now)."""
        key = user_term.lower()
        if key in self._metric_index:
            return MatchResult(
                matched=True,
                match_type="exact",
                source_type="metric",
                metric=self._metric_index[key],
            )
        return MatchResult(matched=False, match_type="none")

    def _fuzzy_match_term(self, user_term: str) -> MatchResult:
        """Use LLM to find semantically similar glossary term."""
        glossary_entries = "\n".join(
            f"- {t.term}: {t.definition} (aliases: {', '.join(t.aliases)})"
            for t in self.glossary
        )
        prompt = FUZZY_MATCH_PROMPT_TEMPLATE.format(
            user_term=user_term,
            glossary_entries=glossary_entries,
        )
        response = self.llm_client.completion(
            role="semantic_query",
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return MatchResult(matched=False, match_type="none")

        matched_term_name = data.get("match")
        confidence = data.get("confidence", "none")

        if matched_term_name is None or confidence == "none":
            return MatchResult(matched=False, match_type="none")

        # Find the matched glossary term
        for term in self.glossary:
            if term.term == matched_term_name:
                return MatchResult(
                    matched=True,
                    match_type="fuzzy",
                    source_type="glossary",
                    term=term,
                    confidence=confidence,
                )

        return MatchResult(matched=False, match_type="none")

    def learn_alias(self, term_name: str, new_alias: str, glossary_file: Path | None = None) -> None:
        """Add a new alias to a glossary term (in-memory + optionally persist to file)."""
        for term in self.glossary:
            if term.term == term_name:
                if new_alias not in term.aliases:
                    term.aliases.append(new_alias)
                    self._glossary_index[new_alias.lower()] = term
                break

        if glossary_file and glossary_file.exists():
            with open(glossary_file) as f:
                data = yaml.safe_load(f)
            if "glossary" in data:
                for entry in data["glossary"]:
                    if entry.get("term") == term_name:
                        if new_alias not in entry.get("aliases", []):
                            entry.setdefault("aliases", []).append(new_alias)
                        break
                with open(glossary_file, "w") as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
