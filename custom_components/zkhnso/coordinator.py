"""Data update coordinator for the ZKHNSO integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import ZKHAPIClient
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)


class ZKHDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch meter and tariff data from the ZKHNSO personal account."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data, translating service failures into Home Assistant errors."""
        username = self.entry.data[CONF_USERNAME]
        password = self.entry.data[CONF_PASSWORD]
        async with ZKHAPIClient(username, password) as client:
            if not await client.preflight():
                raise UpdateFailed("Failed to initialize ZKHNSO session")

            if not await client.login():
                raise ConfigEntryAuthFailed("Invalid ZKHNSO credentials")

            meters_data = await client.get_meters()
            if meters_data is None:
                raise UpdateFailed("Failed to fetch ZKHNSO meter data")

            tariffs_data = await client.get_tariffs()
            if tariffs_data is None:
                _LOGGER.warning("Failed to fetch ZKHNSO tariff data")
                tariffs_data = {"tariffs": {}}

        return {**meters_data, **tariffs_data}
