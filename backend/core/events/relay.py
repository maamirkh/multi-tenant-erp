"""Background relay stub — marks pending outbox records as published.

Actual delivery to a message bus is deferred to a future epic.
This stub is intentionally a no-op beyond logging and state transition.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.events.outbox import OutboxRecord

logger = logging.getLogger(__name__)


def relay_pending_events(session: Session) -> int:
    """Query unpublished outbox records, log them, and mark them published.

    Returns the number of records processed.
    """
    stmt = (
        select(OutboxRecord)
        .where(OutboxRecord.published.is_(False))
        .order_by(OutboxRecord.created_at)
    )
    records = list(session.scalars(stmt))

    for record in records:
        logger.info(
            "relay_pending_events: processing event",
            extra={
                "event_id": str(record.id),
                "event_type": record.event_type,
                "aggregate_id": record.aggregate_id,
                "aggregate_type": record.aggregate_type,
            },
        )
        record.published = True
        record.published_at = datetime.now(tz=UTC)

    return len(records)
