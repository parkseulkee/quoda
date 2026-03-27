"""Create SQLAlchemy engine from config."""

from sqlalchemy import create_engine, Engine

from quada.core.config import DatabaseConfig


def get_connection_url(config: DatabaseConfig) -> str:
    """Build a SQLAlchemy connection URL from database config."""
    if config.type == "sqlite":
        return f"sqlite:///{config.name}"
    return f"{config.type}://{config.user}:{config.password}@{config.host}:{config.port}/{config.name}"


def create_engine_from_config(config: DatabaseConfig) -> Engine:
    """Create a SQLAlchemy engine from database config."""
    url = get_connection_url(config)
    return create_engine(url)
