import pytest

from quada.core.config import DatabaseConfig
from quada.db.connector import create_engine_from_config, get_connection_url
from quada.db.executor import SQLExecutor, ReadOnlyViolationError


def test_get_connection_url():
    config = DatabaseConfig(
        type="postgresql",
        host="localhost",
        port=5432,
        name="testdb",
        user="testuser",
        password="testpass",
    )
    url = get_connection_url(config)
    assert url == "postgresql://testuser:testpass@localhost:5432/testdb"


def test_ddl_blocked():
    executor = SQLExecutor.__new__(SQLExecutor)
    with pytest.raises(ReadOnlyViolationError, match="DDL/DML"):
        executor._validate_read_only("DROP TABLE users")


def test_dml_blocked():
    executor = SQLExecutor.__new__(SQLExecutor)
    with pytest.raises(ReadOnlyViolationError, match="DDL/DML"):
        executor._validate_read_only("INSERT INTO users VALUES (1)")


def test_dml_update_blocked():
    executor = SQLExecutor.__new__(SQLExecutor)
    with pytest.raises(ReadOnlyViolationError, match="DDL/DML"):
        executor._validate_read_only("UPDATE users SET name = 'x'")


def test_dml_delete_blocked():
    executor = SQLExecutor.__new__(SQLExecutor)
    with pytest.raises(ReadOnlyViolationError, match="DDL/DML"):
        executor._validate_read_only("DELETE FROM users WHERE id = 1")


def test_select_allowed():
    executor = SQLExecutor.__new__(SQLExecutor)
    executor._validate_read_only("SELECT * FROM users")  # should not raise


def test_with_clause_allowed():
    executor = SQLExecutor.__new__(SQLExecutor)
    executor._validate_read_only("WITH cte AS (SELECT 1) SELECT * FROM cte")
