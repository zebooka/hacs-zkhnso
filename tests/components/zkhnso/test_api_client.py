"""Tests for ZKHNSO data parsing."""
from multidict import CIMultiDict

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


def test_api_client_parsing_helpers() -> None:
    """Numeric, date, serial, cookie, and login-page helper behavior is stable."""
    client = ZKHAPIClient("user", "password")

    assert client._parse_float("1\u00a0234,56") == 1234.56
    assert client._parse_float("") is None
    assert client._parse_float("invalid") is None
    assert client._parse_date("31.12.2026") == "2026-12-31"
    assert client._parse_date("invalid") is None
    assert client._sanitize_serial_number("AB-12/34") == "___12_34"
    assert client._extract_jsessionid(
        CIMultiDict({"Set-Cookie": "JSESSIONID=session; Path=/"})
    ) == "session"
    assert client._extract_jsessionid(CIMultiDict()) is None
    assert client._is_login_page('<form id="loginForm"></form>')
    assert client._is_login_page('<input name="loginToken">')
    assert not client._is_login_page("<html><body>Account</body></html>")


def test_process_data_skips_invalid_rows() -> None:
    """Parsers retain valid rows and ignore incomplete input rows."""
    client = ZKHAPIClient("user", "password")

    meters = client._process_meters_data(
        [["header"], ["incomplete"], ["Water", "42", "куб.м.", "01.01.2026", "1", "", "", "", "02.01.2030"]]
    )
    tariffs = client._process_tariffs_data(
        [["header"], ["incomplete"], ["Water", "1", "куб.м.", "2", "01.01.2026"]]
    )

    assert list(meters["meters"]) == ["42"]
    assert list(tariffs["tariffs"]) == ["Water"]
