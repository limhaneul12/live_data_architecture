"""Create user analytics view table metadata."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260425_0004"
down_revision = "20260425_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create metadata storage for user-created analytics view tables.

    Args:
        None.

    Returns:
        None.
    """
    op.create_table(
        "analytics_view_tables",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_sql", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop user-created analytics view table metadata.

    Args:
        None.

    Returns:
        None.
    """
    op.drop_table("analytics_view_tables")
