"""MetadataIndex: builds and persists a lightweight index of semantic layer YAML files."""

import json
from dataclasses import dataclass
from pathlib import Path

from quada.semantic.loader import SemanticContext


@dataclass
class MetadataIndex:
    """Lightweight index for LLM to decide which entities/metrics/glossary to look up."""

    data: dict  # {"entities": [...], "metrics": [...], "glossary": [...]}

    @classmethod
    def build(cls, context: SemanticContext) -> "MetadataIndex":
        """Build index from a loaded SemanticContext."""
        entities = [
            {
                "name": e.name,
                "table": e.table,
                "description": e.description,
                "key_columns": [c.name for c in e.columns],
            }
            for e in context.entities
        ]

        metrics = [
            {
                "name": m.name,
                "description": m.description,
                "entities": getattr(m, "entities", []),
            }
            for m in context.metrics
        ]

        glossary = [
            {
                "term": t.term,
                "description": t.definition,
                "entity": t.entity,
            }
            for t in context.glossary
        ]

        return cls(data={"entities": entities, "metrics": metrics, "glossary": glossary})

    def save(self, quada_dir: Path) -> None:
        """Save index to <quada_dir>/metadata_index.json."""
        quada_dir.mkdir(parents=True, exist_ok=True)
        index_path = quada_dir / "metadata_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, quada_dir: Path) -> "MetadataIndex":
        """Load index from <quada_dir>/metadata_index.json."""
        index_path = quada_dir / "metadata_index.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"metadata_index.json not found at {index_path}. Run 'quada index build' first."
            )
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data=data)

    def to_json_string(self) -> str:
        """Serialize index to JSON string for LLM context."""
        return json.dumps(self.data, ensure_ascii=False, indent=2)
