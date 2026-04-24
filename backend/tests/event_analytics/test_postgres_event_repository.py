from datetime import UTC, datetime
from decimal import Decimal

from app.event_analytics.domain.events import WebEvent
from app.event_analytics.infrastructure.repositories.postgres_event_repository import (
    EventRecord,
    build_insert_events_statement,
    event_to_record_values,
)
from sqlalchemy.dialects import postgresql


def build_event(event_id: str = "evt_1") -> WebEvent:
    return WebEvent(
        schema_version="web_event.v1",
        event_id=event_id,
        event_type="purchase",
        occurred_at=datetime(2026, 4, 24, tzinfo=UTC),
        user_id="user_001",
        traffic_phase="normal",
        producer_id="producer_local",
        page_path=None,
        category_id="cat_smartphone",
        product_id="prod_iphone_15",
        amount=Decimal("799.99"),
        currency="USD",
        error_code=None,
        error_message=None,
    )


def test_event_record_declares_expected_orm_table_contract() -> None:
    columns = EventRecord.__table__.columns

    expected_columns = {
        "event_id",
        "schema_version",
        "event_type",
        "occurred_at",
        "user_id",
        "traffic_phase",
        "producer_id",
        "page_path",
        "category_id",
        "product_id",
        "amount",
        "currency",
        "error_code",
        "error_message",
        "ingested_at",
    }
    assert set(columns.keys()) == expected_columns
    assert columns["event_id"].primary_key is True
    assert columns["schema_version"].nullable is False


def test_event_to_record_values_maps_internal_dataclass_to_orm_row() -> None:
    event = build_event()

    row = event_to_record_values(event)

    expected = {
        "event_id": "evt_1",
        "schema_version": "web_event.v1",
        "event_type": "purchase",
        "occurred_at": datetime(2026, 4, 24, tzinfo=UTC),
        "user_id": "user_001",
        "traffic_phase": "normal",
        "producer_id": "producer_local",
        "page_path": None,
        "category_id": "cat_smartphone",
        "product_id": "prod_iphone_15",
        "amount": Decimal("799.99"),
        "currency": "USD",
        "error_code": None,
        "error_message": None,
    }
    assert row == expected


def test_build_insert_events_statement_uses_postgres_conflict_ignore() -> None:
    statement = build_insert_events_statement(
        [build_event("evt_1"), build_event("evt_2")]
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "INSERT INTO events" in compiled
    assert "ON CONFLICT (event_id) DO NOTHING" in compiled
    assert "RETURNING events.event_id" in compiled
