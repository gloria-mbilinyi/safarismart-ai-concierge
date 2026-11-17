"""Run the consent-aware Africa's Talking SMS outbox worker."""

import argparse

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db.session import Database
from app.integrations.africastalking_sms import (
    AfricasTalkingSMSProvider,
    SMSConfigurationError,
)
from app.services.sms_notifications import SMSNotificationService
from app.workers.sms_outbox import drain_due_notifications, run_continuously


def parse_args() -> argparse.Namespace:
    """Choose a bounded drain for jobs or continuous polling for a worker."""

    parser = argparse.ArgumentParser(
        description="Process queued, consent-aware SafariSmart SMS notifications."
    )
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Process currently due messages and exit instead of polling.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=100,
        help="Maximum messages in --drain mode (default: 100).",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Idle delay for continuous mode (default: 5).",
    )
    return parser.parse_args()


def main() -> None:
    """Validate provider configuration before claiming any outbox rows."""

    args = parse_args()
    settings = get_settings()
    if not settings.sms_enabled:
        raise SystemExit("SMS worker is not configured: SMS sending is disabled")

    database = Database(settings.database_url)
    try:
        with database.engine.connect():
            pass
    except SQLAlchemyError:
        database.dispose()
        raise SystemExit("SMS worker database is unavailable") from None

    try:
        provider = AfricasTalkingSMSProvider.from_settings(settings)
    except SMSConfigurationError as error:
        database.dispose()
        raise SystemExit(f"SMS worker is not configured: {error}") from None

    service = SMSNotificationService(provider)
    try:
        if args.drain:
            summary = drain_due_notifications(
                database.session_factory,
                service,
                max_messages=args.max_messages,
            )
            print(
                "SMS outbox drain complete: "
                f"processed={summary.processed}, accepted={summary.accepted}, "
                f"requeued={summary.requeued}, failed={summary.failed}, "
                f"unknown={summary.unknown}"
            )
        else:
            print("SafariSmart SMS outbox worker started.", flush=True)
            run_continuously(
                database.session_factory,
                service,
                poll_seconds=args.poll_seconds,
            )
    except KeyboardInterrupt:
        print("SafariSmart SMS outbox worker stopped.")
    except SQLAlchemyError:
        raise SystemExit("SMS worker database operation failed") from None
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
