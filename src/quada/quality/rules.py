"""Quality rule types with evaluation logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re


@dataclass
class RuleResult:
    rule_name: str
    status: str  # "pass", "warn", "fail"
    message: str
    value: str = ""


def _parse_duration(threshold: str) -> timedelta:
    """Parse '24 hours', '1 day', '30 minutes' into timedelta."""
    match = re.match(r"(\d+)\s*(hour|hours|day|days|minute|minutes)", threshold)
    if not match:
        raise ValueError(f"Cannot parse duration: {threshold}")
    amount = int(match.group(1))
    unit = match.group(2).rstrip("s")
    if unit == "hour":
        return timedelta(hours=amount)
    elif unit == "day":
        return timedelta(days=amount)
    elif unit == "minute":
        return timedelta(minutes=amount)
    raise ValueError(f"Unknown unit: {unit}")


class FreshnessRule:
    def __init__(self, name: str, table: str, column: str, threshold: str):
        self.name = name
        self.table = table
        self.column = column
        self.threshold = threshold
        self.max_age = _parse_duration(threshold)

    def sql_fragment(self) -> str:
        return f"MAX({self.column}) AS max_{self.column}"

    def evaluate(self, row: dict) -> RuleResult:
        key = f"max_{self.column}"
        max_val = row.get(key)
        if max_val is None:
            return RuleResult(self.name, "warn", f"No data found in {self.table}.{self.column}")
        if isinstance(max_val, datetime) and max_val.tzinfo is None:
            max_val = max_val.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - max_val
        if age > self.max_age:
            return RuleResult(self.name, "warn", f"Data is {age} old (threshold: {self.threshold})", str(age))
        return RuleResult(self.name, "pass", f"Data is fresh ({age} old)", str(age))


class NullRatioRule:
    def __init__(self, name: str, table: str, column: str, threshold: float):
        self.name = name
        self.table = table
        self.column = column
        self.threshold = threshold

    def sql_fragment(self) -> str:
        return f"COUNT(*) FILTER (WHERE {self.column} IS NULL)::float / NULLIF(COUNT(*), 0) AS null_ratio_{self.column}"

    def evaluate(self, row: dict) -> RuleResult:
        key = f"null_ratio_{self.column}"
        ratio = row.get(key, 0) or 0
        if ratio > self.threshold:
            return RuleResult(
                self.name, "warn",
                f"{self.column} null ratio {ratio:.1%} exceeds threshold {self.threshold:.1%}",
                f"{ratio:.4f}",
            )
        return RuleResult(self.name, "pass", f"{self.column} null ratio {ratio:.1%} OK", f"{ratio:.4f}")


class ValueRangeRule:
    def __init__(self, name: str, table: str, column: str, min_val: float, max_val: float):
        self.name = name
        self.table = table
        self.column = column
        self.min_val = min_val
        self.max_val = max_val

    def sql_fragment(self) -> str:
        return (
            f"COUNT(*) FILTER (WHERE {self.column} < {self.min_val} OR {self.column} > {self.max_val}) "
            f"AS out_of_range_{self.column}"
        )

    def evaluate(self, row: dict) -> RuleResult:
        key = f"out_of_range_{self.column}"
        count = row.get(key, 0) or 0
        if count > 0:
            return RuleResult(
                self.name, "warn",
                f"{count} rows in {self.column} outside [{self.min_val}, {self.max_val}]",
                str(count),
            )
        return RuleResult(self.name, "pass", f"{self.column} values within range", "0")


class UniqueRule:
    def __init__(self, name: str, table: str, column: str):
        self.name = name
        self.table = table
        self.column = column

    def sql_fragment(self) -> str:
        return f"COUNT({self.column}) - COUNT(DISTINCT {self.column}) AS duplicate_count_{self.column}"

    def evaluate(self, row: dict) -> RuleResult:
        key = f"duplicate_count_{self.column}"
        count = row.get(key, 0) or 0
        if count > 0:
            return RuleResult(self.name, "warn", f"{count} duplicate values in {self.column}", str(count))
        return RuleResult(self.name, "pass", f"{self.column} values are unique", "0")


class CustomSQLRule:
    def __init__(self, name: str, table: str, query: str, threshold: int | float):
        self.name = name
        self.table = table
        self.query = query
        self.threshold = threshold

    def evaluate(self, row: dict) -> RuleResult:
        violations = row.get("violations", 0) or 0
        if violations > self.threshold:
            return RuleResult(self.name, "warn", f"{violations} violations (threshold: {self.threshold})", str(violations))
        return RuleResult(self.name, "pass", f"No violations", str(violations))
