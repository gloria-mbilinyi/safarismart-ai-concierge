"""Africa's Talking USSD callback contract and privacy tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.config import Settings
from app.db.session import Database
from app.main import create_app


CALLBACK = "/api/v1/ussd"


def dial(client: TestClient, text: str = ""):
    """Simulate one cumulative application/x-www-form-urlencoded AT callback."""

    return client.post(
        CALLBACK,
        data={
            "sessionId": "synthetic-ussd-session",
            "serviceCode": "*384*123#",
            "phoneNumber": "+255700000001",
            "text": text,
        },
    )


def test_root_menu_returns_plain_text_and_continues(client: TestClient) -> None:
    response = dial(client)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("CON Welcome to SafariSmart")
    assert "2. Kiswahili" in response.text


def test_english_and_swahili_navigation(client: TestClient) -> None:
    en = dial(client, "1")
    sw = dial(client, "2")
    assert en.text.startswith("CON SafariSmart")
    assert "Explore destinations" in en.text
    assert sw.text.startswith("CON SafariSmart")
    assert "Maeneo ya utalii" in sw.text


def test_destination_menu_uses_active_curated_catalog(
    client: TestClient, seeded_destinations: list[Destination]
) -> None:
    en = dial(client, "1*1")
    sw = dial(client, "2*1")
    assert en.status_code == 200
    assert en.text.startswith("CON Choose a destination")
    assert "Serengeti" in en.text
    assert "Zanzibar" in en.text
    assert sw.text.startswith("CON Chagua eneo la utalii")


def test_destination_selection_is_informational_only(
    client: TestClient, seeded_destinations: list[Destination]
) -> None:
    response = dial(client, "1*1*1")
    assert response.status_code == 200
    assert response.text.startswith("END Mount Kilimanjaro")
    assert "Region: Kilimanjaro" in response.text
    assert "no booking was made" in response.text
    assert "price" not in response.text.lower()


def test_swahili_destination_detail(
    client: TestClient, seeded_destinations: list[Destination]
) -> None:
    response = dial(client, "2*1*5")
    assert response.text.startswith("END Zanzibar")
    assert "Mkoa: Zanzibar" in response.text
    assert "hakuna booking" in response.text.lower()


def test_inactive_destination_is_not_displayed(
    client: TestClient,
    db_session: Session,
    seeded_destinations: list[Destination],
) -> None:
    zanzibar = next(item for item in seeded_destinations if item.name == "Zanzibar")
    zanzibar.is_active = False
    db_session.commit()
    response = dial(client, "1*1")
    assert "Zanzibar" not in response.text
    assert "Serengeti" in response.text


def test_booking_info_and_help_are_terminal_and_do_not_disclose_pii(
    client: TestClient,
) -> None:
    for text in ("1*2", "2*2", "1*3", "2*3"):
        response = dial(client, text)
        assert response.status_code == 200
        assert response.text.startswith("END ")
        assert "+255700000001" not in response.text
        assert "synthetic-ussd-session" not in response.text


def test_invalid_inputs_end_safely(client: TestClient) -> None:
    for text in ("9", "1*9", "1*2*3", "1**1", "1*1*2*4", "1*1*999", "1*a", "1*" + "7" * 130):
        response = dial(client, text)
        assert response.status_code == 200
        assert response.text.startswith("END ")


def test_empty_catalog_fails_closed(client: TestClient) -> None:
    response = dial(client, "1*1")
    assert response.text == "END No destinations available yet."


def test_missing_callback_metadata_is_rejected(client: TestClient) -> None:
    response = client.post(CALLBACK, data={"text": "1"})
    assert response.status_code == 422


def test_callback_rejects_malformed_provider_metadata(client: TestClient) -> None:
    """Malformed service codes and phone numbers fail before menu processing."""

    invalid_service = client.post(
        CALLBACK,
        data={
            "sessionId": "synthetic-ussd-session",
            "serviceCode": "javascript:alert(1)",
            "phoneNumber": "+255700000001",
            "text": "",
        },
    )
    invalid_phone = client.post(
        CALLBACK,
        data={
            "sessionId": "synthetic-ussd-session",
            "serviceCode": "*384*123#",
            "phoneNumber": "0700000001",
            "text": "",
        },
    )

    assert invalid_service.status_code == 422
    assert invalid_phone.status_code == 422


def test_callback_rate_limit_ends_session_without_echoing_identifier(
    database: Database,
) -> None:
    """Repeated callbacks fail closed with an AT-compatible terminal response."""

    settings = Settings(
        app_env="test",
        database_url=str(database.engine.url),
        ussd_rate_limit_per_minute=2,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as limited_client:
        first = dial(limited_client)
        second = dial(limited_client, "1")
        limited = dial(limited_client, "1*1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 200
    assert limited.text.startswith("END SafariSmart is busy")
    assert "synthetic-ussd-session" not in limited.text
