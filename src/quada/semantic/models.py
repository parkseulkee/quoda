"""Pydantic models for the semantic layer: entities, metrics, glossary."""

from typing import Literal

from pydantic import BaseModel


class Column(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    description: str = ""


class Relationship(BaseModel):
    name: str
    type: Literal["one_to_many", "many_to_one", "one_to_one", "many_to_many"]
    entity: str
    join: str


class Entity(BaseModel):
    name: str
    description: str = ""
    table: str
    columns: list[Column] = []
    relationships: list[Relationship] = []


class Dimension(BaseModel):
    name: str
    expression: str


class Metric(BaseModel):
    name: str
    description: str = ""
    type: Literal["sum", "count", "avg", "count_distinct"]
    expression: str
    filter: str = ""
    entities: list[str] = []
    dimensions: list[Dimension] = []
    aliases: list[str] = []


class DerivedMetric(BaseModel):
    name: str
    description: str = ""
    expression: str
    aliases: list[str] = []


class GlossaryTerm(BaseModel):
    term: str
    definition: str
    sql_condition: str
    entity: str
    aliases: list[str] = []


class QualityRule(BaseModel):
    name: str
    type: str
    table: str
    column: str | None = None
    threshold: str | float | int | None = None
    min: float | None = None
    max: float | None = None
    query: str | None = None


class QualityConfig(BaseModel):
    rules: list[QualityRule] = []
