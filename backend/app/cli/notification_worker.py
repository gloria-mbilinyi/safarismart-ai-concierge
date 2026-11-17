"""Run the consent-aware booking notification outbox dispatcher."""

import argparse

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db.session import Database
from app.services.notification_delivery import build_notification_delivery_services
from app.workers.sms_outbox import drain_due_notifications, run_continuously


def parse_args() -> argparse.Namespace:
    """Choose a bounded drain for jobs or continuous polling for a worker."""

    parser = argparse.ArgumentParser(
        description="Process queued, consent-aware SafariSmart notifications."
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
    services = build_notification_delivery_services(settings)
    if not services.configured_channels:
        raise SystemExit("Notification dispatcher has no configured providers")

    database = Database(settings.database_url)
    try:
        with database.engine.connect():
            pass
    except SQLAlchemyError:
        database.dispose()
        raise SystemExit("SMS worker database is unavailable") from None

    try:
        if args.drain:
            summary = drain_due_notifications(
                database.session_factory,
                services,
                max_messages=args.max_messages,
            )
            print(
                "Notification outbox drain complete: "
                f"processed={summary.processed}, accepted={summary.accepted}, "
                f"requeued={summary.requeued}, failed={summary.failed}, "
                f"unknown={summary.unknown}"
            )
        else:
            print(
                "SafariSmart notification outbox dispatcher started.",
                flush=True,
            )
            run_continuously(
                database.session_factory,
                services,
                poll_seconds=args.poll_seconds,
            )
    except KeyboardInterrupt:
        print("SafariSmart notification dispatcher stopped.")
    except SQLAlchemyError:
        raise SystemExit("SMS worker database operation failed") from None
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
