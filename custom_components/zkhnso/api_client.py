"""API client for ZKHNSO integration."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urljoin

import aiohttp

from .const import (
    API_BASE_URL,
    API_URL_LOGIN,
    API_URL_MAIN,
    API_URL_METERS,
    API_URL_TARIFFS,
    API_URL_PREFLIGHT,
    SESSION_FORM_TOKEN,
    SESSION_JSESSIONID,
)
from .html_parser import extract_table_rows_with_children, html_to_json_simple

_LOGGER = logging.getLogger(__name__)


class ZKHAPIClient:
    """Client for interacting with ZKHNSO API."""

    def __init__(
            self,
            username: str,
            password: str,
    ) -> None:
        """Initialize the API client with an isolated HTTP session."""
        self.username = username
        self.password = password
        self.session: aiohttp.ClientSession | None = None
        self.jsessionid: str | None = None
        self.form_token: str | None = None
        self.address: str | None = None

    async def __aenter__(self) -> ZKHAPIClient:
        """Create an HTTP session and cookie jar isolated to this client."""
        self.session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the HTTP session and discard its account-specific cookies."""
        if self.session is not None:
            await self.session.close()
            self.session = None

    @property
    def _session(self) -> aiohttp.ClientSession:
        """Return the active session, requiring use as an async context manager."""
        if self.session is None:
            raise RuntimeError("ZKHAPIClient must be used as an async context manager")
        return self.session

    async def preflight(self) -> dict[str, str] | None:
        """Perform preflight request to get FORM_TOKEN and JSESSIONID.

        Returns:
            Dictionary with JSESSIONID and FORM_TOKEN, or None on error
        """
        url = urljoin(API_BASE_URL, API_URL_PREFLIGHT)

        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Preflight request to url %s failed with status %d", url, response.status
                    )
                    return None

                # Extract JSESSIONID from Set-Cookie header
                jsessionid = self._extract_jsessionid(response.headers)
                if not jsessionid:
                    _LOGGER.warning("JSESSIONID not found in preflight response")
                    return None

                # Get HTML content
                html_content = await response.text()

                # Extract FORM_TOKEN from HTML
                form_token = html_to_json_simple(
                    html_content,
                    "#loginForm input[name=loginToken]",
                    attribute="value",
                )

                if not form_token:
                    _LOGGER.error("FORM_TOKEN not found in HTML response")
                    return None

                self.jsessionid = jsessionid
                self.form_token = form_token

                _LOGGER.debug("Preflight successful, session initialized")

                return {
                    SESSION_JSESSIONID: jsessionid,
                    SESSION_FORM_TOKEN: form_token,
                }

        except aiohttp.ClientError as e:
            _LOGGER.error("Error during preflight request: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Unexpected error during preflight: %s", e)
            return None

    def _extract_jsessionid(self, headers: Any) -> str | None:
        """Extract JSESSIONID from Set-Cookie header.

        Args:
            headers: Response headers object

        Returns:
            JSESSIONID value or None if not found
        """
        cookies = headers.getall("Set-Cookie", [])
        for cookie in cookies:
            if "JSESSIONID=" in cookie:
                # Extract JSESSIONID value
                # Format: JSESSIONID=value; Path=/; ...
                parts = cookie.split(";")
                for part in parts:
                    part = part.strip()
                    if part.startswith("JSESSIONID="):
                        return part.split("=", 1)[1]
        return None

    def _get_authenticated_cookies(self) -> dict[str, str]:
        """Get cookies for authenticated requests (includes userLogin and loginModule)."""
        cookies = {
            "userLogin": self.username,
            "loginModule": "lk",
        }
        if self.jsessionid:
            cookies["JSESSIONID"] = self.jsessionid
        return cookies

    def _build_login_cookie_header(self) -> str:
        """Build cookie header for login request using JSESSIONID from preflight."""
        if not self.jsessionid:
            return ""
        return f"JSESSIONID={self.jsessionid};"

    def _build_cookie_header(self, cookies: dict[str, str]) -> str:
        """Build a Cookie header string from cookies dictionary."""
        parts = [
            f"{key}={value}"
            for key, value in cookies.items()
            if value is not None
        ]
        return ("; ".join(parts) + ";") if parts else ""

    @staticmethod
    def _is_login_page(html_content: str) -> bool:
        """Return whether an HTML response contains the login form."""
        return (
                'id="loginForm"' in html_content
                or "id='loginForm'" in html_content
                or 'name="loginToken"' in html_content
                or "name='loginToken'" in html_content
        )

    @staticmethod
    def _log_page_diagnostics(
            page_name: str, response: aiohttp.ClientResponse, html_content: str
    ) -> None:
        """Log safe response markers without exposing response content or secrets."""
        _LOGGER.debug(
            "%s response: status=%d, url=%s, login_form=%s, counters_form=%s, "
            "tariffs_form=%s",
            page_name,
            response.status,
            response.url,
            ZKHAPIClient._is_login_page(html_content),
            'id="countersForm"' in html_content or "id='countersForm'" in html_content,
            'id="tariffsForm"' in html_content or "id='tariffsForm'" in html_content,
        )

    async def login(self) -> bool:
        """Perform login after preflight.

        Returns:
            True if login successful, False otherwise
        """
        if not self.form_token or not self.jsessionid:
            _LOGGER.error("Preflight must be called before login")
            return False

        url = urljoin(API_BASE_URL, API_URL_LOGIN)
        preflight_url = urljoin(API_BASE_URL, API_URL_PREFLIGHT)

        # Prepare form data
        form_payload = urlencode(
            {
                "struts.token.name": "loginToken",
                "loginToken": self.form_token,
                "userName": self.username,
                "userPass": self.password,
                "captchaCode": "x",
                "timezone": "-420",
                "loginModule": "lk",
            },
            doseq=False,
            encoding="utf-8",
            safe="",
        )
        # Prepare headers
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": API_BASE_URL,
            "Referer": preflight_url,
        }

        login_cookie = self._build_login_cookie_header()
        if login_cookie:
            headers["Cookie"] = login_cookie

        _LOGGER.debug("Login: %s", self.username)

        try:
            async with self._session.post(
                    url, data=form_payload, headers=headers
            ) as response:
                response_text = await response.text()
                self._log_page_diagnostics("Login", response, response_text)

                # Extract updated JSESSIONID from response
                updated_jsessionid = self._extract_jsessionid(response.headers)
                if updated_jsessionid:
                    self.jsessionid = updated_jsessionid
                    _LOGGER.debug("JSESSIONID updated after login")

                if response.status == 200 and not self._is_login_page(response_text):
                    address = html_to_json_simple(
                        response_text,
                        ".header .address",
                    )
                    if isinstance(address, str):
                        self.address = " ".join(address.split()) or None
                    _LOGGER.debug("Login response accepted")
                    return True

                _LOGGER.warning(
                    "Login was not accepted: status=%d, login_form=%s",
                    response.status,
                    self._is_login_page(response_text),
                )
                return False

        except aiohttp.ClientError as e:
            _LOGGER.error("Error during login request to url %s: %s", url, e)
            return False
        except Exception as e:
            _LOGGER.exception("Unexpected error during login to url %s: %s", url, e)
            return False

    async def get_tariffs(self) -> dict[str, Any] | None:
        """Fetch tariffs data.

        Returns:
            Parsed tariffs data with structure:
            {
                "tariffs": {
                    "tariff_name": {
                        "name": "...",
                        "rate": 123.45,
                        "unit": "m³",
                        "tariff": 67.89,
                        "date": "YYYY-MM-DD"
                    }
                }
            }
            or None on error
        """
        if not self.jsessionid:
            _LOGGER.error("Must be logged in to fetch tariffs")
            return None

        url = urljoin(API_BASE_URL, API_URL_TARIFFS)
        referer_url = urljoin(API_BASE_URL, API_URL_MAIN)

        cookies = self._get_authenticated_cookies()
        cookie_header = self._build_cookie_header(cookies)

        # Prepare headers
        headers = {
            "Cookie": cookie_header,
            "Referer": referer_url,
        }

        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Tariffs request to url %s failed with status %d", url, response.status
                    )
                    return None

                html_content = await response.text()
                self._log_page_diagnostics("Tariffs", response, html_content)

                if self._is_login_page(html_content):
                    _LOGGER.warning("Tariffs response returned the login page")
                    return None

                # Extract table rows
                rows = extract_table_rows_with_children(
                    html_content, "#tariffsForm table tr"
                )

                if not rows:
                    _LOGGER.warning("No tariff table rows found at %s", url)
                    return {"tariffs": {}}

                # Process rows into tariffs data
                return self._process_tariffs_data(rows)

        except aiohttp.ClientError as e:
            _LOGGER.error("Error during tariffs request: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Unexpected error during tariffs fetch: %s", e)
            return None

    def _parse_date(self, date_str: str, format_in: str = "%d.%m.%Y") -> str | None:
        """Parse date string and convert to ISO format (YYYY-MM-DD).

        Args:
            date_str: Date string to parse
            format_in: Input date format (default: DD.MM.YYYY)

        Returns:
            ISO format date string (YYYY-MM-DD) or None on error
        """
        try:
            dt = datetime.strptime(date_str.strip(), format_in)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError) as e:
            _LOGGER.warning("Failed to parse date '%s': %s", date_str, e)
            return None

    def _sanitize_serial_number(self, serial: str) -> str:
        """Sanitize serial number for use as key (replace non-digits with underscore).

        Args:
            serial: Serial number string

        Returns:
            Sanitized serial number
        """
        return re.sub(r"[^0-9]", "_", serial)

    def _process_meters_data(self, rows: list[list[str]]) -> dict[str, Any]:
        """Process table rows into meters data structure (similar to JQ transformation).

        Args:
            rows: List of table rows, where each row is a list of cell text values

        Returns:
            Dictionary with meters and max date
        """
        if not rows or len(rows) < 2:
            return {"meters": {}, "date": None}

        # Skip first row (header) - [1:]
        data_rows = rows[1:]
        meters = {}
        dates = []

        for row in data_rows:
            _LOGGER.debug("Row: %s", row)
            if len(row) < 9:
                _LOGGER.warning("Row has insufficient columns: %s", row)
                continue

            try:
                type_name = row[0].strip()
                serial_number = row[1].strip()
                value_date = self._parse_date(row[3].strip())
                key = self._sanitize_serial_number(serial_number)

                if value_date:
                    dates.append(value_date)

                meter = {
                    "name": f"{type_name} №{serial_number}",
                    "units": row[2].strip(),
                    "serial_number": serial_number,
                    "type_name": type_name,
                    "value": self._parse_float(row[4].strip()),
                    "value_date": value_date,
                    "next_verification_date": self._parse_date(row[8].strip()),
                }

                _LOGGER.debug("Meter %s: %s", key, meter)
                meters[key] = meter

            except (IndexError, AttributeError) as e:
                _LOGGER.warning("Error processing row %s: %s", row, e)
                continue

        return {
            "meters": meters,
            "date": max(dates) if dates else None,
        }

    def _process_tariffs_data(self, rows: list[list[str]]) -> dict[str, Any]:
        """Process table rows into tariffs data structure

        Args:
            rows: List of table rows, where each row is a list of cell text values

        Returns:
            Dictionary with tariffs data
        """
        if not rows or len(rows) < 2:
            return {"tariffs": {}}

        # Skip first row (header) - [1:]
        data_rows = rows[1:]
        tariffs = {}

        for row in data_rows:
            if len(row) < 5:
                _LOGGER.warning("Tariff row has insufficient columns: %s", row)
                continue

            try:
                tariff = {
                    "name": row[0].strip(),
                    "rate": self._parse_float(row[1].strip()),
                    "unit": self._map_russian_unit(row[2].strip()),
                    "tariff": self._parse_float(row[3].strip()),
                    "date": self._parse_date(row[4].strip()),
                }

                _LOGGER.debug("Processed tariff: %s", tariff)

                tariffs[tariff["name"]] = tariff

            except (IndexError, AttributeError) as e:
                _LOGGER.warning("Error processing tariff row %s: %s", row, e)
                continue

        return {"tariffs": tariffs}

    def _parse_float(self, value_str: str) -> float | None:
        """Extract and parse float value from string.

        Args:
            value_str: Value string (may contain nbsp, spaces and commas)

        Returns:
            Parsed value as float or None on error
        """
        if not value_str:
            return None

        try:
            return float(value_str.replace("\u00a0", "").replace(" ", "").replace(",", "."))
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Failed to parse float value '%s': %s", value_str, e)
            return None

    def _map_russian_unit(self, unit_str: str) -> str:
        """Map Russian unit names to standard symbols of HASS.

        Args:
            unit_str: Russian unit string

        Returns:
            Mapped unit string
        """
        unit_mapping = {
            "кв.м": "m²",
            "куб.м.": "m³",
            "кВтч": "kWh",
            "Гкал": "Gcal",
        }

        return unit_mapping.get(unit_str, unit_str)

    async def get_meters(self) -> dict[str, Any] | None:
        """Fetch meters/counters data.

        Returns:
            Parsed meters data with structure:
            {
                "meters": {
                    "serial_key": {
                        "name": "...",
                        "units": "...",
                        "serial_number": "...",
                        "type_name": "...",
                        "value": 123,
                        "value_date": "YYYY-MM-DD",
                        "next_verification_date": "YYYY-MM-DD"
                    }
                },
                "date": "YYYY-MM-DD"  # max value_date
            }
            or None on error
        """
        if not self.jsessionid:
            _LOGGER.error("Must be logged in to fetch meters")
            return None

        url = urljoin(API_BASE_URL, API_URL_METERS)
        referer_url = urljoin(API_BASE_URL, API_URL_MAIN)

        cookies = self._get_authenticated_cookies()
        cookie_header = self._build_cookie_header(cookies)

        # Prepare headers
        headers = {
            "Cookie": cookie_header,
            "Referer": referer_url,
        }

        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Meters request to url %s failed with status %d", url, response.status
                    )
                    return None

                html_content = await response.text()
                self._log_page_diagnostics("Meters", response, html_content)

                if self._is_login_page(html_content):
                    _LOGGER.warning("Meters response returned the login page")
                    return None

                # Extract table rows
                rows = extract_table_rows_with_children(
                    html_content, "#countersForm table tr"
                )

                if not rows:
                    _LOGGER.warning("No meter table rows found at %s", url)
                    return {"meters": {}, "date": None}

                # Process rows into meters data
                return self._process_meters_data(rows)

        except aiohttp.ClientError as e:
            _LOGGER.error("Error during meters request: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Unexpected error during meters fetch: %s", e)
            return None
