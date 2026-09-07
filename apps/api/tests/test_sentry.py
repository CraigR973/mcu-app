from sentry_sdk.types import Event

from src.main import _scrub_pii


def test_sentry_scrubber_removes_account_identifiers() -> None:
    event: Event = {
        "user": {
            "id": "11111111-1111-4111-8111-111111111111",
            "display_name": "Craig",
            "username": "craig",
            "email": "craig@example.com",
        }
    }

    result = _scrub_pii(event, {})

    assert result is event
    assert result["user"] == {"id": "11111111-1111-4111-8111-111111111111"}
