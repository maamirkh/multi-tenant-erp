"""Transactional outbox pattern — model and append-only repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.database.models.base_model import BaseModel


class OutboxRecord(BaseModel):
    """Append-only record of a domain event to be relayed to the message bus.

    Records are written inside the same database transaction as the state change
    that produced the event, guaranteeing at-least-once delivery without
    distributed transactions.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "event_outbox"

    event_type: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class EventOutboxRepository:
    """Append-only repository for OutboxRecord.

    Intentionally exposes only ``create()``. Marking records as published
    is the exclusive responsibility of the relay process.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: OutboxRecord) -> OutboxRecord:
        """Persist a new outbox record within the current session transaction."""
        self._session.add(record)
        return record
