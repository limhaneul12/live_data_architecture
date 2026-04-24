"""Create event analytics generated views."""

from __future__ import annotations

from alembic import op

revision = "20260425_0002"
down_revision = "20260424_0001"
branch_labels = None
depends_on = None

VIEW_NAMES = (
    "product_event_counts",
    "commerce_funnel_counts",
    "error_event_ratio",
    "hourly_event_counts",
    "user_event_counts",
    "event_type_counts",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW event_type_counts AS
        SELECT
          event_type,
          COUNT(*)::bigint AS event_count
        FROM events
        GROUP BY event_type
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW user_event_counts AS
        SELECT
          user_id,
          COUNT(*)::bigint AS event_count
        FROM events
        GROUP BY user_id
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW hourly_event_counts AS
        SELECT
          date_trunc('hour', occurred_at) AS event_hour,
          event_type,
          COUNT(*)::bigint AS event_count
        FROM events
        GROUP BY event_hour, event_type
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW error_event_ratio AS
        SELECT
          COUNT(*) FILTER (WHERE event_type = 'checkout_error')::bigint AS error_events,
          COUNT(*)::bigint AS total_events,
          ROUND(
            COUNT(*) FILTER (WHERE event_type = 'checkout_error')::numeric
            / NULLIF(COUNT(*), 0),
            4
          ) AS error_ratio
        FROM events
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW commerce_funnel_counts AS
        SELECT
          funnel.sort_order,
          funnel.funnel_step,
          funnel.event_type,
          COUNT(events.event_id)::bigint AS event_count
        FROM (
          VALUES
            (1, 'Page view', 'page_view'),
            (2, 'Product click', 'product_click'),
            (3, 'Add to cart', 'add_to_cart'),
            (4, 'Purchase', 'purchase'),
            (5, 'Checkout error', 'checkout_error')
        ) AS funnel(sort_order, funnel_step, event_type)
        LEFT JOIN events ON events.event_type = funnel.event_type
        GROUP BY funnel.sort_order, funnel.funnel_step, funnel.event_type
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW product_event_counts AS
        SELECT
          product_id,
          event_type,
          COUNT(*)::bigint AS event_count
        FROM events
        WHERE product_id IS NOT NULL
        GROUP BY product_id, event_type
        """
    )


def downgrade() -> None:
    for view_name in VIEW_NAMES:
        op.execute(f"DROP VIEW IF EXISTS {view_name}")
