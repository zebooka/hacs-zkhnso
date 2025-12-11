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

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.session: aiohttp.ClientSession | None = None
        self.jsessionid: str | None = None
        self.form_token: str | None = None

    async def __aenter__(self) -> ZKHAPIClient:
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def preflight(self) -> dict[str, str] | None:
        """Perform preflight request to get FORM_TOKEN and JSESSIONID.

        Returns:
            Dictionary with JSESSIONID and FORM_TOKEN, or None on error
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = urljoin(API_BASE_URL, API_URL_PREFLIGHT)

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Preflight request to url %s failed with status %d", url, response.status
                    )
                    return None

                # Extract JSESSIONID from Set-Cookie header
                jsessionid = self._extract_jsessionid(response.headers)
                if not jsessionid:
                    _LOGGER.warning("JSESSIONID not found in response headers: %s", response.headers)

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

                _LOGGER.debug(
                    "Preflight successful: JSESSIONID=%s, FORM_TOKEN=%s",
                    jsessionid[:20] + "..." if jsessionid and len(jsessionid) > 20 else jsessionid,
                    form_token[:20] + "..." if len(form_token) > 20 else form_token,
                )

                return {
                    SESSION_JSESSIONID: jsessionid or "",
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


    async def login(self) -> bool:
        """Perform login after preflight.

        Returns:
            True if login successful, False otherwise
        """
        if not self.form_token or not self.jsessionid:
            _LOGGER.error("Preflight must be called before login")
            return False

        if not self.session:
            self.session = aiohttp.ClientSession()

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

        _LOGGER.debug("Login request headers: %s", headers)
        _LOGGER.debug("Login form payload: %s", form_payload)

        try:
            async with self.session.post(
                url, data=form_payload, headers=headers
            ) as response:
                # Extract updated JSESSIONID from response
                updated_jsessionid = self._extract_jsessionid(response.headers)
                if updated_jsessionid:
                    self.jsessionid = updated_jsessionid
                    _LOGGER.debug("JSESSIONID updated after login: %s", updated_jsessionid)
                else:
                    _LOGGER.warning("JSESSIONID not found in response headers: %s", response.headers)

                # Check if login was successful
                # Typically, successful login returns 200 or redirects
                if response.status in (200, 302):
                    _LOGGER.debug("Login successful with status %d", response.status)
                    return True
                else:
                    _LOGGER.error(
                        "Login failed with status %d", response.status
                    )
                    # Log response body for debugging
                    try:
                        response_text = await response.text()
                        _LOGGER.debug("Login response: %s", response_text[:500])
                    except Exception:
                        pass
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

        if not self.session:
            self.session = aiohttp.ClientSession()

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
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Tariffs request to url %s failed with status %d", url, response.status
                    )
                    return None

                html_content = await response.text()

                # Extract table rows
                rows = extract_table_rows_with_children(
                    html_content, "#tariffsForm table tr"
                )

                if not rows:
                    _LOGGER.warning("No table rows found in url %s (headers: %s) tariffs", url, headers)
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
            if len(row) < 6:
                _LOGGER.warning("Row has insufficient columns: %s", row)
                continue

            try:
                # Extract data from row cells
                # [0] - type name
                # [1] - serial number
                # [2] - units of measurement
                # [3] - value date (DD.MM.YYYY)
                # [4] - value (number)
                # [8] - next verification date (DD.MM.YYYY)
                type_name = row[0].strip()
                serial_number = row[1].strip()
                units = row[2].strip()
                value_date_str = row[3].strip()
                value_str = row[4].strip()
                next_verification_date_str = row[8].strip()
                _LOGGER.debug("METER Type: %s, Units: %s, Serial №: %s, Date: %s, Value: %s, Next V: %s", type_name, units, serial_number, value_date_str, value_str, next_verification_date_str)

                # Parse value as number and floor it
                try:
                    value = int(float(value_str))
                except (ValueError, TypeError):
                    _LOGGER.warning("Failed to parse value '%s' as number", value_str)
                    value = 0

                # Parse dates
                value_date = self._parse_date(value_date_str)
                next_verification_date = self._parse_date(next_verification_date_str)

                if value_date:
                    dates.append(value_date)

                # Create meter object
                meter = {
                    "name": f"{type_name} №{serial_number}",
                    "units": units,
                    "serial_number": serial_number,
                    "type_name": type_name,
                    "value": value,
                    "value_date": value_date,
                    "next_verification_date": next_verification_date,
                }

                _LOGGER.debug("Meter: %s", meter)

                # Use sanitized serial number as key
                key = self._sanitize_serial_number(serial_number)
                meters[key] = meter

            except (IndexError, AttributeError) as e:
                _LOGGER.warning("Error processing row %s: %s", row, e)
                continue

        # Find max date
        max_date = max(dates) if dates else None

        return {"meters": meters, "date": max_date}

    def _process_tariffs_data(self, rows: list[list[str]]) -> dict[str, Any]:
        """Process table rows into tariffs data structure (similar to JQ transformation).

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
                # Extract data from row cells based on JQ logic
                # [0] - name
                # [1] - norm
                # [2] - units of measurement
                # [3] - tariff
                # [4] - date (DD.MM.YYYY)
                name = row[0].strip()
                norm = row[1].strip()
                units = row[2].strip()
                tariff_value = row[3].strip()
                date_str = row[4].strip()

                _LOGGER.debug("TARIFF Name: %s, Norm %s, Unit: %s, Tariff: %s, Date: %s",
                            name, norm, units, tariff_value, date_str)

                # Parse rate (remove spaces, convert comma to dot)
                norm = self._extract_norm(norm)

                # Map Russian units to standard symbols
                unit = self._map_unit(units)

                # Parse tariff (remove spaces, convert comma to dot)
                tariff = self._extract_tariff(tariff_value)

                # Parse date
                date = self._parse_date(date_str)

                # Create tariff object
                tariff_obj = {
                    "name": name,
                    "rate": norm,
                    "unit": unit,
                    "tariff": tariff,
                    "date": date,
                }

                _LOGGER.debug("Processed tariff: %s", tariff_obj)

                # Use name as key
                tariffs[name] = tariff_obj

            except (IndexError, AttributeError) as e:
                _LOGGER.warning("Error processing tariff row %s: %s", row, e)
                continue

        return {"tariffs": tariffs}

    def _extract_norm(self, norm_str: str) -> float | None:
        """Extract and parse rate from string.

        Args:
            norm_str: Norm string (may contain spaces and commas)

        Returns:
            Parsed rate as float or None on error
        """
        if not norm_str:
            return None

        try:
            # Remove spaces and convert comma to dot
            cleaned = norm_str.replace(" ", "").replace(",", ".")
            return float(cleaned)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Failed to parse norm '%s': %s", norm_str, e)
            return None

    def _extract_tariff(self, tariff_str: str) -> float | None:
        """Extract and parse tariff from string.

        Args:
            tariff_str: Tariff string (may contain spaces and commas)

        Returns:
            Parsed tariff as float or None on error
        """
        if not tariff_str:
            return None

        try:
            # Remove spaces and convert comma to dot
            cleaned = tariff_str.replace(" ", "").replace(",", ".")
            return float(cleaned)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Failed to parse tariff '%s': %s", tariff_str, e)
            return None

    def _map_unit(self, unit_str: str) -> str:
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

        if not self.session:
            self.session = aiohttp.ClientSession()

        url = urljoin(API_BASE_URL, API_URL_METERS)
        referer_url = urljoin(API_BASE_URL, API_URL_MAIN)

        cookies = self._get_authenticated_cookies()
        cookie_header = self._build_cookie_header(cookies)

        # Prepare headers
        headers = {
            "Cookie": cookie_header,
            "Referer": referer_url,
        }

        _LOGGER.debug(
            "Meters request prepared with headers=%s and cookie_header=%s",
            headers,
            cookie_header,
        )

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Meters request to url %s failed with status %d", url, response.status
                    )
                    return None

                html_content = await response.text()

                # Extract table rows
                rows = extract_table_rows_with_children(
                    html_content, "#countersForm table tr"
                )

                if not rows:
                    _LOGGER.warning("No table rows found in url %s (headers: %s) meters", url, headers)
                    return {"meters": {}, "date": None}

                # Process rows into meters data
                return self._process_meters_data(rows)

        except aiohttp.ClientError as e:
            _LOGGER.error("Error during meters request: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Unexpected error during meters fetch: %s", e)
            return None

