from pathlib import Path

import pytest

from quada.semantic.loader import SemanticLoader


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_entities():
    loader = SemanticLoader(models_dir=FIXTURES / "sample_models")
    entities = loader.load_entities()
    assert len(entities) == 2
    names = {e.name for e in entities}
    assert "customer" in names
    assert "order" in names


def test_load_metrics():
    loader = SemanticLoader(metrics_dir=FIXTURES / "sample_metrics")
    metrics = loader.load_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "revenue"
    assert "매출" in metrics[0].aliases


def test_load_glossary():
    loader = SemanticLoader(glossary_dir=FIXTURES / "sample_glossary")
    terms = loader.load_glossary()
    assert len(terms) == 2
    assert terms[0].term == "이탈 고객"


def test_load_quality_rules():
    loader = SemanticLoader(quality_dir=FIXTURES / "sample_quality")
    config = loader.load_quality_rules()
    assert len(config.rules) == 3
    assert config.rules[0].type == "freshness"


def test_load_all():
    loader = SemanticLoader(
        models_dir=FIXTURES / "sample_models",
        metrics_dir=FIXTURES / "sample_metrics",
        glossary_dir=FIXTURES / "sample_glossary",
        quality_dir=FIXTURES / "sample_quality",
    )
    context = loader.load_all()
    assert len(context.entities) == 2
    assert len(context.metrics) == 1
    assert len(context.glossary) == 2
    assert len(context.quality.rules) == 3


def test_load_empty_dir(tmp_path):
    loader = SemanticLoader(models_dir=tmp_path)
    entities = loader.load_entities()
    assert entities == []


def test_load_nonexistent_dir():
    loader = SemanticLoader(models_dir=Path("/nonexistent"))
    entities = loader.load_entities()
    assert entities == []
