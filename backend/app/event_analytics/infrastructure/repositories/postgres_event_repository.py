"""SQLAlchemy ORM repository for persisted event analytics rows."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from app.event_analytics.domain.events import WebEvent
from app.event_analytics.domain.repositories.event_repository import EventRepository
from sqlalchemy import DateTime, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.dml import ReturningInsert


class EventAnalyticsBase(DeclarativeBase):
    """Base class for event analytics ORM records."""


class EventRecord(EventAnalyticsBase):
    """ORM mapped row for one stored web event."""

    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_occurred_at", "occurred_at"),
        Index("idx_events_event_type", "event_type"),
        Index("idx_events_user_id", "user_id"),
        Index("idx_events_product_id", "product_id"),
    )

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    traffic_phase: Mapped[str] = mapped_column(Text, nullable=False)
    producer_id: Mapped[str] = mapped_column(Text, nullable=False)
    page_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PostgresEventRepository(EventRepository):
    """Persist validated web events with SQLAlchemy ORM batch inserts."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize this repository with a root-owned async session factory.

        Args:
            session_factory: Factory that creates SQLAlchemy async sessions.

        Returns:
            None.
        """
        self._session_factory = session_factory

    async def save_batch(self, events: Sequence[WebEvent]) -> int:
        """Insert events as one batch and ignore duplicate event ids.

        Args:
            events: Validated internal event dataclasses to insert.

        Returns:
            Number of newly inserted rows after conflict-ignore handling.
        """
        if not events:
            return 0

        statement = build_insert_events_statement(events)
        async with self._session_factory() as session, session.begin():
            result = await session.execute(statement)
            inserted_event_ids = result.scalars().all()
        return len(inserted_event_ids)


def build_insert_events_statement(
    events: Sequence[WebEvent],
) -> ReturningInsert[tuple[str]]:
    """Build one PostgreSQL insert statement for a validated event batch.

    Args:
        events: Validated internal event dataclasses to include in the insert.

    Returns:
        PostgreSQL insert statement with conflict-ignore and returning clauses.
    """
    rows = [event_to_record_values(event) for event in events]
    return (
        postgres_insert(EventRecord)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[EventRecord.event_id])
        .returning(EventRecord.event_id)
    )


def event_to_record_values(
    event: WebEvent,
) -> dict[str, str | datetime | Decimal | None]:
    """Map one internal event dataclass to ORM insert values.

    Args:
        event: Validated internal event dataclass.

    Returns:
        Dictionary keyed by ORM column names for batch insert values.
    """
    return {
        "event_id": event.event_id,
        "schema_version": str(event.schema_version),
        "event_type": str(event.event_type),
        "occurred_at": event.occurred_at,
        "user_id": event.user_id,
        "traffic_phase": str(event.traffic_phase),
        "producer_id": event.producer_id,
        "page_path": event.page_path,
        "category_id": event.category_id,
        "product_id": event.product_id,
        "amount": event.amount,
        "currency": event.currency,
        "error_code": event.error_code,
        "error_message": event.error_message,
    }
