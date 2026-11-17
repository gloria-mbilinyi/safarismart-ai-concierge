"""Operational SMS outbox worker tests."""

from typing import Any
from uuid import uuid4

import pytest

from app.models.enums import NotificationStatus
from app.services.notification_outbox import NotificationProcessResult
from app.workers.sms_outbox import drain_due_notifications


def test_outbox_drain_returns_pii_free_status_counts() -> None:
    """A bounded worker run reports operational outcomes without recipients."""

    results = iter(
        [
            NotificationProcessResult(uuid4(), NotificationStatus.ACCEPTED, 1),
            NotificationProcessResult(uuid4(), NotificationStatus.QUEUED, 1),
            NotificationProcessResult(uuid4(), NotificationStatus.FAILED, 3),
            None,
        ]
    )

    def fake_processor(_: Any, __: Any) -> NotificationProcessResult | None:
        return next(results)

    summary = drain_due_notifications(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        processor=fake_processor,
    )

    assert summary.processed == 3
    assert summary.accepted == 1
    assert summary.requeued == 1
    assert summary.failed == 1
    assert summary.unknown == 0
    assert not hasattr(summary, "recipient")


def test_outbox_drain_rejects_unbounded_message_counts() -> None:
    """One-shot jobs cannot accidentally request an unlimited drain."""

    with pytest.raises(ValueError):
        drain_due_notifications(
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            max_messages=0,
        )
