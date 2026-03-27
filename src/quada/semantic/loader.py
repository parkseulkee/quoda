"""Load semantic layer YAML files from project directories."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from quada.semantic.models import (
    Entity,
    Metric,
    DerivedMetric,
    GlossaryTerm,
    QualityConfig,
    QualityRule,
)


@dataclass
class SemanticContext:
    """All loaded semantic layer data."""
    entities: list[Entity] = field(default_factory=list)
    metrics: list[Metric | DerivedMetric] = field(default_factory=list)
    glossary: list[GlossaryTerm] = field(default_factory=list)
    quality: QualityConfig = field(default_factory=QualityConfig)


class SemanticLoader:
    """Loads YAML definitions from models/, metrics/, glossary/, quality/ dirs."""

    def __init__(
        self,
        models_dir: Path | None = None,
        metrics_dir: Path | None = None,
        glossary_dir: Path | None = None,
        quality_dir: Path | None = None,
    ):
        self.models_dir = models_dir
        self.metrics_dir = metrics_dir
        self.glossary_dir = glossary_dir
        self.quality_dir = quality_dir

    def _read_yaml_files(self, directory: Path | None) -> list[dict]:
        """Read all YAML files from a directory."""
        if directory is None or not directory.exists():
            return []
        results = []
        for file in sorted(directory.glob("*.yaml")):
            with open(file) as f:
                data = yaml.safe_load(f)
                if data:
                    results.append(data)
        return results

    def load_entities(self) -> list[Entity]:
        """Load entity definitions from models/ directory."""
        entities = []
        for data in self._read_yaml_files(self.models_dir):
            if "entity" in data:
                entities.append(Entity(**data["entity"]))
        return entities

    def load_metrics(self) -> list[Metric | DerivedMetric]:
        """Load metric definitions from metrics/ directory."""
        metrics: list[Metric | DerivedMetric] = []
        for data in self._read_yaml_files(self.metrics_dir):
            if "metric" in data:
                m = data["metric"]
                if m.get("type") == "derived":
                    metrics.append(DerivedMetric(**m))
                else:
                    metrics.append(Metric(**m))
        return metrics

    def load_glossary(self) -> list[GlossaryTerm]:
        """Load glossary terms from glossary/ directory."""
        terms = []
        for data in self._read_yaml_files(self.glossary_dir):
            if "glossary" in data:
                for term_data in data["glossary"]:
                    terms.append(GlossaryTerm(**term_data))
        return terms

    def load_quality_rules(self) -> QualityConfig:
        """Load quality rules from quality/ directory."""
        all_rules: list[QualityRule] = []
        for data in self._read_yaml_files(self.quality_dir):
            if "quality" in data and "rules" in data["quality"]:
                for rule_data in data["quality"]["rules"]:
                    all_rules.append(QualityRule(**rule_data))
        return QualityConfig(rules=all_rules)

    def load_all(self) -> SemanticContext:
        """Load all semantic layer components."""
        return SemanticContext(
            entities=self.load_entities(),
            metrics=self.load_metrics(),
            glossary=self.load_glossary(),
            quality=self.load_quality_rules(),
        )
