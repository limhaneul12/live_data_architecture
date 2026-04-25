"""Create optional analytics read-only role grants."""

import os
from dataclasses import dataclass

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import ArgumentError

revision = "20260425_0003"
down_revision = "20260425_0002"
branch_labels = None
depends_on = None

ANALYTICS_DATABASE_URL_ENV = "ANALYTICS_DATABASE_DB_ADDRESS"
INVALID_ANALYTICS_DATABASE_URL_MESSAGE = (
    f"{ANALYTICS_DATABASE_URL_ENV} must be a valid database URL"
)
MISSING_ANALYTICS_DATABASE_USERNAME_MESSAGE = (
    f"{ANALYTICS_DATABASE_URL_ENV} must include a username"
)
ANALYTICS_VIEW_NAMES = (
    "event_type_counts",
    "user_event_counts",
    "hourly_event_counts",
    "error_event_ratio",
    "commerce_funnel_counts",
    "product_event_counts",
)


@dataclass(frozen=True, slots=True)
class AnalyticsReaderRole:
    """Analytics read-only role details parsed from the analytics DSN."""

    name: str
    password: str | None


def analytics_reader_role_from_env() -> AnalyticsReaderRole | None:
    """Return the analytics reader role requested by the deployment environment."""
    raw_url = os.environ.get(ANALYTICS_DATABASE_URL_ENV)
    if raw_url is None or raw_url.strip() == "":
        return None

    try:
        url = make_url(raw_url)
    except ArgumentError as exc:
        raise ValueError(INVALID_ANALYTICS_DATABASE_URL_MESSAGE) from exc

    if url.username is None or url.username.strip() == "":
        raise ValueError(MISSING_ANALYTICS_DATABASE_USERNAME_MESSAGE)

    return AnalyticsReaderRole(name=url.username, password=url.password)


def upgrade() -> None:
    """Apply optional analytics reader role and generated-view grants."""
    role = analytics_reader_role_from_env()
    if role is None:
        return

    connection = op.get_bind()
    quoted_role = quote_identifier(connection, role.name)
    create_or_update_analytics_reader_role(
        connection=connection,
        role=role,
        quoted_role=quoted_role,
    )
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
    op.execute("REVOKE ALL ON TABLE events FROM PUBLIC")
    op.execute(f"REVOKE ALL ON TABLE events FROM {quoted_role}")
    op.execute(
        f"GRANT SELECT ON TABLE {analytics_view_list(connection)} TO {quoted_role}"
    )


def downgrade() -> None:
    """Revoke optional analytics reader generated-view grants."""
    role = analytics_reader_role_from_env()
    if role is None:
        return

    connection = op.get_bind()
    quoted_role = quote_identifier(connection, role.name)
    op.execute(
        f"REVOKE SELECT ON TABLE {analytics_view_list(connection)} FROM {quoted_role}"  # noqa: S608
    )
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {quoted_role}")
    op.execute(f"ALTER ROLE {quoted_role} RESET default_transaction_read_only")
    op.execute(f"ALTER ROLE {quoted_role} RESET statement_timeout")
    op.execute(f"ALTER ROLE {quoted_role} RESET idle_in_transaction_session_timeout")


def create_or_update_analytics_reader_role(
    *,
    connection: Connection,
    role: AnalyticsReaderRole,
    quoted_role: str,
) -> None:
    """Create or harden the configured analytics reader role."""
    role_literal = quote_literal(connection, role.name)
    password_clause = password_ddl_clause(connection, role.password)
    alter_password_statement = password_alter_statement(
        connection=connection,
        quoted_role=quoted_role,
        password=role.password,
    )
    role_sql = f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN
            CREATE ROLE {quoted_role}
              LOGIN
              NOSUPERUSER
              NOCREATEDB
              NOCREATEROLE
              NOREPLICATION{password_clause};
          ELSE
            ALTER ROLE {quoted_role}
              WITH LOGIN
              NOSUPERUSER
              NOCREATEDB
              NOCREATEROLE
              NOREPLICATION;
            {alter_password_statement}
          END IF;
        END
        $$;
        """  # noqa: S608
    op.execute(role_sql)
    op.execute(f"ALTER ROLE {quoted_role} SET default_transaction_read_only = on")
    op.execute(f"ALTER ROLE {quoted_role} SET statement_timeout = '3s'")
    op.execute(
        f"ALTER ROLE {quoted_role} SET idle_in_transaction_session_timeout = '5s'"
    )


def password_ddl_clause(connection: Connection, password: str | None) -> str:
    """Return the optional CREATE ROLE password clause."""
    if password is None:
        return ""
    return f" PASSWORD {quote_literal(connection, password)}"


def password_alter_statement(
    *,
    connection: Connection,
    quoted_role: str,
    password: str | None,
) -> str:
    """Return the optional ALTER ROLE password statement."""
    if password is None:
        return ""
    return (
        f"ALTER ROLE {quoted_role} WITH PASSWORD {quote_literal(connection, password)};"
    )


def analytics_view_list(connection: Connection) -> str:
    """Return the comma-separated generated view identifier list."""
    return ", ".join(
        quote_identifier(connection, view_name) for view_name in ANALYTICS_VIEW_NAMES
    )


def quote_identifier(connection: Connection, identifier: str) -> str:
    """Quote a PostgreSQL identifier using the active migration connection."""
    return str(
        connection.execute(
            sa.text("SELECT quote_ident(:identifier)"),
            {"identifier": identifier},
        ).scalar_one()
    )


def quote_literal(connection: Connection, value: str) -> str:
    """Quote a PostgreSQL string literal using the active migration connection."""
    return str(
        connection.execute(
            sa.text("SELECT quote_literal(:value)"),
            {"value": value},
        ).scalar_one()
    )
