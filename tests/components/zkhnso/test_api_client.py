"""Tests for ZKHNSO data parsing."""
from custom_components.zkhnso.api_client import ZKHAPIClient


def test_process_meters_preserves_fractional_reading() -> None:
    """Meter values retain fractional readings from the portal."""
    client = ZKHAPIClient("user", "password")

    result = client._process_meters_data(
        [
            ["header"],
            ["Water", "123", "куб.м.", "01.01.2026", "12,34", "", "", "", "01.01.2030"],
        ]
    )

    assert result["meters"]["123"]["value"] == 12.34


def test_authenticated_cookies_exclude_session_cookie() -> None:
    """The cookie jar, rather than manual headers, manages JSESSIONID."""
    client = ZKHAPIClient("user", "password")
    client.jsessionid = "session-id"

    assert client._get_authenticated_cookies() == {
        "userLogin": "user",
        "loginModule": "lk",
    }
