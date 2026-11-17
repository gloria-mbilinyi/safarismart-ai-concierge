"""Continuous and one-shot execution helpers for the transactional SMS outbox."""

from collections.abc import Callable
from dataclasses import dataclass
import time

from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import NotificationStatus
from app.services.notification_outbox import (
    NotificationProcessResult,
    process_next_notification,
)
from app.services.sms_notifications import SMSNotificationService


OutboxProcessor = Callable[
    [sessionmaker[Session], SMSNotificationService],
    NotificationProcessResult | None,
]


@dataclass(frozen=True, slots=True)
class WorkerSummary:
    """PII-free counts returned by bounded worker runs."""

    processed: int
    accepted: int
    requeued: int
    failed: int
    unknown: int


def drain_due_notifications(
    session_factory: sessionmaker[Session],
    service: SMSNotificationService,
    *,
    max_messages: int = 100,
    processor: OutboxProcessor = process_next_notification,
) -> WorkerSummary:
    """Process due messages until empty or a caller-supplied safety bound."""

    if not 1 <= max_messages <= 10_000:
        raise ValueError("max_messages must be between 1 and 10000")
    counts = {status: 0 for status in NotificationStatus}
    processed = 0
    for _ in range(max_messages):
        result = processor(session_factory, service)
        if result is None:
            break
        processed += 1
        counts[result.status] += 1

    return WorkerSummary(
        processed=processed,
        accepted=counts[NotificationStatus.ACCEPTED],
        requeued=counts[NotificationStatus.QUEUED],
        failed=counts[NotificationStatus.FAILED],
        unknown=counts[NotificationStatus.UNKNOWN],
    )


def run_continuously(
    session_factory: sessionmaker[Session],
    service: SMSNotificationService,
    *,
    poll_seconds: float = 5.0,
    processor: OutboxProcessor = process_next_notification,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Poll forever, relying on leases and retries for safe concurrent workers."""

    if not 0.5 <= poll_seconds <= 300:
        raise ValueError("poll_seconds must be between 0.5 and 300")
    while True:
        result = processor(session_factory, service)
        if result is None:
            sleep(poll_seconds)
            continue
        print(
            "Processed notification "
            f"{result.notification_id}: {result.status.value} "
            f"(attempt {result.attempt_count})",
            flush=True,
        )
