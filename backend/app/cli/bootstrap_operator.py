"""Create a synthetic operator identity for local development."""

import argparse
import os

from app.config import get_settings
from app.db.session import Database
from app.services.operator_bootstrap import bootstrap_demo_operator


def parse_args() -> argparse.Namespace:
    """Parse explicit, non-secret demo account identifiers."""

    parser = argparse.ArgumentParser(
        description="Create a synthetic SafariSmart demo operator account."
    )
    parser.add_argument("--operator-name", required=True)
    parser.add_argument("--operator-slug", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument(
        "--password-env",
        default="SAFARISMART_BOOTSTRAP_PASSWORD",
        help="Environment variable containing the password (never pass it as an argument).",
    )
    return parser.parse_args()


def main() -> None:
    """Bootstrap one demo account only in the development environment."""

    args = parse_args()
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("Demo operator bootstrap is available only in development")

    password = os.environ.get(args.password_env)
    if password is None:
        raise SystemExit(
            f"Set {args.password_env} to the explicit local demo password first"
        )

    database = Database(settings.database_url)
    try:
        with database.session_factory() as session:
            operator, user = bootstrap_demo_operator(
                session,
                operator_name=args.operator_name,
                operator_slug=args.operator_slug,
                user_email=args.email,
                user_full_name=args.full_name,
                password=password,
            )
    finally:
        database.dispose()

    print(
        f"Created synthetic operator '{operator.slug}' with user '{user.email}'."
    )


if __name__ == "__main__":
    main()
