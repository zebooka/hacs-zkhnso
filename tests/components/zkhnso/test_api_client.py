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


def test_process_tariffs_numbers_duplicate_names() -> None:
    """Duplicate tariff names receive stable numbered keys and names."""
    client = ZKHAPIClient("user", "password")

    result = client._process_tariffs_data(
        [
            ["header"],
            ["А", "1", "кв.м.", "2", "01.01.2026"],
            ["Б", "3", "куб.м.", "4", "01.01.2026"],
            ["Б", "5", "кВтч", "6", "01.01.2026"],
        ]
    )

    assert list(result["tariffs"]) == ["А", "Б 1", "Б 2"]
    assert result["tariffs"]["Б 1"]["name"] == "Б 1"
    assert result["tariffs"]["Б 2"]["name"] == "Б 2"
