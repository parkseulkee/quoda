"""Tests for MetadataIndex build, save, load."""
from pathlib import Path

import pytest

from quada.semantic.index import MetadataIndex
from quada.semantic.loader import SemanticLoader


FIXTURES = Path(__file__).parent / "fixtures"


def _load_context():
    loader = SemanticLoader(
        models_dir=FIXTURES / "models",
        metrics_dir=FIXTURES / "metrics",
        glossary_dir=FIXTURES / "glossary",
    )
    return loader.load_all()


def test_build_includes_entities():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    names = [e["name"] for e in index.data["entities"]]
    assert "customer" in names


def test_build_entity_has_required_fields():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    entity = index.data["entities"][0]
    assert "name" in entity
    assert "table" in entity
    assert "description" in entity
    assert "key_columns" in entity
    assert isinstance(entity["key_columns"], list)


def test_build_includes_metrics():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    names = [m["name"] for m in index.data["metrics"]]
    assert "revenue" in names


def test_build_metric_has_required_fields():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    metric = index.data["metrics"][0]
    assert "name" in metric
    assert "description" in metric
    assert "entities" in metric


def test_build_includes_glossary():
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    terms = [g["term"] for g in index.data["glossary"]]
    assert "이탈 고객" in terms


def test_build_glossary_no_aliases():
    """aliases는 인덱스에 포함하지 않는다."""
    ctx = _load_context()
    index = MetadataIndex.build(ctx)
    for term in index.data["glossary"]:
        assert "aliases" not in term


def test_save_and_load(tmp_path):
    ctx = _load_context()
    index = MetadataIndex.build(ctx)

    quada_dir = tmp_path / ".quada"
    index.save(quada_dir)

    assert (quada_dir / "metadata_index.json").exists()

    loaded = MetadataIndex.load(quada_dir)
    assert loaded.data["entities"] == index.data["entities"]
    assert loaded.data["metrics"] == index.data["metrics"]
    assert loaded.data["glossary"] == index.data["glossary"]


def test_load_raises_if_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        MetadataIndex.load(tmp_path / ".quada")
