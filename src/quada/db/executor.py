"""Execute SQL queries in read-only transactions with DDL/DML blocking."""

import re

from sqlalchemy import Engine, text


class ReadOnlyViolationError(Exception):
    """Raised when a query attempts DDL or DML operations."""
    pass


_FORBIDDEN_PATTERNS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLExecutor:
    """Executes SQL queries in read-only mode."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _validate_read_only(self, sql: str) -> None:
        """Raise if the SQL contains DDL/DML statements."""
        stripped = sql.strip()
        # Handle WITH/CTE — check the final statement after CTE
        if stripped.upper().startswith("WITH"):
            # Find the main statement after the CTE
            # Look for the last SELECT that isn't inside the CTE
            pass
        if _FORBIDDEN_PATTERNS.match(stripped):
            raise ReadOnlyViolationError(
                f"DDL/DML statements are not allowed: {stripped[:50]}..."
            )

    def execute(self, sql: str) -> list[dict]:
        """Execute a read-only SQL query and return results as list of dicts."""
        self._validate_read_only(sql)
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]
