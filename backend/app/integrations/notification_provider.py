"""Shared provider acceptance and safe failure contracts."""

from dataclasses import dataclass


class NotificationDeliveryError(Exception):
    """A provider failure represented without recipient data or response bodies."""

    def __init__(self, message: str, *, retryable: bool, code: str) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True, slots=True)
class ProviderAcceptance:
    """Provider submission result; acceptance is not confirmed delivery."""

    status: str
    message_id: str | None
