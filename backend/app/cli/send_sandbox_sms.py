"""Explicit one-message Africa's Talking Sandbox simulator check."""

import argparse
from collections.abc import Callable

from app.config import Settings, get_settings
from app.integrations.africastalking_sms import (
    PHONE_PATTERN,
    AfricasTalkingSMSProvider,
    SMSConfigurationError,
    SMSDeliveryError,
    SMSResult,
)


SANDBOX_TEST_MESSAGE = (
    "SafariSmart sandbox test. No real booking or reservation was created."
)


def parse_args() -> argparse.Namespace:
    """Require a developer-designated number registered in the simulator."""

    parser = argparse.ArgumentParser(
        description=(
            "Send one fixed SafariSmart test message to an Africa's Talking "
            "Sandbox simulator number."
        )
    )
    parser.add_argument(
        "--simulator-number",
        required=True,
        help="International-format number registered in the Sandbox Simulator.",
    )
    return parser.parse_args()


def send_sandbox_test(
    settings: Settings,
    simulator_number: str,
    *,
    provider_factory: Callable[[Settings], AfricasTalkingSMSProvider] = (
        AfricasTalkingSMSProvider.from_settings
    ),
) -> SMSResult:
    """Send exactly one fixed message after enforcing sandbox-only controls."""

    if settings.africastalking_environment != "sandbox":
        raise SMSConfigurationError(
            "This command is sandbox-only and refuses production configuration"
        )
    if settings.africastalking_username is None or (
        settings.africastalking_username.strip().lower() != "sandbox"
    ):
        raise SMSConfigurationError("Sandbox username must be 'sandbox'")
    if not PHONE_PATTERN.fullmatch(simulator_number):
        raise ValueError("Simulator number must use international format")

    provider = provider_factory(settings)
    return provider.send(simulator_number, SANDBOX_TEST_MESSAGE)


def main() -> None:
    """Run the sandbox check without displaying credentials or recipient data."""

    args = parse_args()
    try:
        result = send_sandbox_test(get_settings(), args.simulator_number)
    except (SMSConfigurationError, SMSDeliveryError, ValueError) as error:
        raise SystemExit(f"Sandbox SMS test failed: {error}") from None

    message_id = result.message_id or "not-returned"
    print(
        "Sandbox provider accepted the test message; this is not proof of "
        f"delivery. Provider message ID: {message_id}"
    )


if __name__ == "__main__":
    main()
