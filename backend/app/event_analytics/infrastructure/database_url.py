"""Database URL helpers for event analytics SQLAlchemy adapters."""

from __future__ import annotations


def to_sqlalchemy_async_url(database_url: str) -> str:
    """Convert a PostgreSQL URL to SQLAlchemy's asyncpg URL form.

    Args:
        database_url: PostgreSQL DSN from runtime configuration.

    Returns:
        SQLAlchemy async URL that uses the asyncpg driver.
    """
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url
