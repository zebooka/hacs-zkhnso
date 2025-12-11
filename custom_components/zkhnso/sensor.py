"""Sensor platform for ZKHNSO integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api_client import ZKHAPIClient
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZKH sensor platform."""
    coordinator = ZKHDataUpdateCoordinator(hass, entry)
    
    # Store coordinator in hass.data for potential future use
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    
    # Try to fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Initial data fetch successful")
    except Exception as e:
        _LOGGER.error("Failed to fetch initial data: %s", e, exc_info=True)
        # Set empty data structure so sensors can still be created
        coordinator.data = {"meters": {}, "tariffs": {}}

    # Create sensors dynamically based on meters and tariffs data
    entities = []

    # Create meter sensors
    if coordinator.data and isinstance(coordinator.data, dict) and "meters" in coordinator.data:
        meters = coordinator.data["meters"]
        if meters and isinstance(meters, dict) and len(meters) > 0:
            meter_entities = [
                ZKHMeterSensor(coordinator, meter_key, meter_data)
                for meter_key, meter_data in meters.items()
            ]
            entities.extend(meter_entities)
            _LOGGER.info("Created %d meter sensors", len(meter_entities))
        else:
            _LOGGER.warning(
                "Meters data is empty or invalid. Meters: %s (type: %s, len: %s)",
                meters,
                type(meters),
                len(meters) if isinstance(meters, dict) else "N/A",
            )

    # Create tariff sensors
    if coordinator.data and isinstance(coordinator.data, dict) and "tariffs" in coordinator.data:
        tariffs = coordinator.data["tariffs"]
        if tariffs and isinstance(tariffs, dict) and len(tariffs) > 0:
            tariff_entities = [
                ZKHTariffSensor(coordinator, tariff_key, tariff_data)
                for tariff_key, tariff_data in tariffs.items()
            ]
            entities.extend(tariff_entities)
            _LOGGER.info("Created %d tariff sensors", len(tariff_entities))
        else:
            _LOGGER.warning(
                "Tariffs data is empty or invalid. Tariffs: %s (type: %s, len: %s)",
                tariffs,
                type(tariffs),
                len(tariffs) if isinstance(tariffs, dict) else "N/A",
            )

    if entities:
        async_add_entities(entities, update_before_add=False)
        _LOGGER.info("Total sensors created: %d", len(entities))
    else:
        _LOGGER.error(
            "No sensors created. Coordinator data: %s (type: %s). "
            "This might indicate an API issue. Check logs for errors.",
            coordinator.data,
            type(coordinator.data) if coordinator.data else None,
        )


class ZKHDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ZKH data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

    async def _async_update_data(self):
        """Fetch data from ZKH."""
        try:
            async with ZKHAPIClient(self.username, self.password) as client:
                # Perform preflight to get FORM_TOKEN and JSESSIONID
                _LOGGER.debug("Starting preflight request")
                preflight_result = await client.preflight()
                if not preflight_result:
                    _LOGGER.error("Preflight request failed")
                    raise Exception("Failed to perform preflight request")

                _LOGGER.debug("Preflight successful, session initialized")

                # Perform login
                _LOGGER.debug("Starting login")
                login_success = await client.login()
                if not login_success:
                    _LOGGER.error("Login failed")
                    raise Exception("Failed to login")

                _LOGGER.debug("Login successful")

                # Fetch meters data
                _LOGGER.debug("Fetching meters data")
                meters_data = await client.get_meters()
                if not meters_data:
                    _LOGGER.error("Failed to fetch meters data")
                    raise Exception("Failed to fetch meters data")

                meters_count = len(meters_data.get("meters", {}))
                _LOGGER.info("Fetched %d meters", meters_count)

                if meters_count == 0:
                    _LOGGER.warning("No meters found in response")

                # Fetch tariffs data
                _LOGGER.debug("Fetching tariffs data")
                tariffs_data = await client.get_tariffs()
                if not tariffs_data:
                    _LOGGER.warning("Failed to fetch tariffs data, continuing without it")
                    tariffs_data = {"tariffs": {}}

                tariffs_count = len(tariffs_data.get("tariffs", {}))
                _LOGGER.info("Fetched %d tariffs", tariffs_count)

                # Combine data
                combined_data = {
                    **meters_data,
                    **tariffs_data,
                }

                return combined_data
        except Exception as e:
            _LOGGER.error("Error updating ZKH data: %s", e, exc_info=True)
            raise


class ZKHMeterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ZKH meter sensor."""

    def __init__(
        self,
        coordinator: ZKHDataUpdateCoordinator,
        meter_key: str,
        meter_data: dict,
    ) -> None:
        """Initialize the meter sensor."""
        super().__init__(coordinator)

        units_to_device_class = {
            "куб.м.": "water",
        }

        units_to_measurement = {
            "куб.м.": "m³",
        }

        self.meter_key = meter_key
        self._attr_unique_id = f"{self.coordinator.entry.entry_id}_meter_{meter_key}"
        self._attr_name = meter_data.get("name", f"Meter {meter_key}")
        self._attr_device_class = units_to_device_class.get(meter_data.get("units"), "energy")
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = units_to_measurement.get(meter_data.get("units"), "None")

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (meter value)."""
        if not self.coordinator.data or "meters" not in self.coordinator.data:
            return None

        meters = self.coordinator.data["meters"]
        meter = meters.get(self.meter_key)
        if meter:
            return float(meter.get("value", 0))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "meters" not in self.coordinator.data:
            return {}

        meters = self.coordinator.data["meters"]
        meter = meters.get(self.meter_key)
        if not meter:
            return {}

        return {
            "serial_number": meter.get("serial_number"),
            "units": meter.get("units"),
            "type_name": meter.get("type_name"),
            "value_date": meter.get("value_date"),
            "next_verification_date": meter.get("next_verification_date"),
        }


class ZKHTariffSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ZKH tariff sensor."""

    def __init__(
        self,
        coordinator: ZKHDataUpdateCoordinator,
        tariff_key: str,
        tariff_data: dict,
    ) -> None:
        """Initialize the tariff sensor."""
        super().__init__(coordinator)
        self.tariff_key = tariff_key
        self._attr_unique_id = f"{self.coordinator.entry.entry_id}_tariff_{tariff_key}"
        self._attr_name = f"{tariff_data.get('name', f"Tariff {tariff_key}")}"
        self._attr_device_class = None  # Tariffs don't have a specific device class
        self._attr_native_unit_of_measurement = f"{tariff_data.get('unit', '')}/руб" if tariff_data.get('unit') else "руб"
        self._attr_state_class = None  # Tariffs are not measured values
        self._attr_icon = "mdi:currency-rub"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (tariff value)."""
        if not self.coordinator.data or "tariffs" not in self.coordinator.data:
            return None

        tariffs = self.coordinator.data["tariffs"]
        tariff = tariffs.get(self.tariff_key)
        if tariff:
            return float(tariff.get("tariff", 0))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "tariffs" not in self.coordinator.data:
            return {}

        tariffs = self.coordinator.data["tariffs"]
        tariff = tariffs.get(self.tariff_key)
        if not tariff:
            return {}

        return {
            "name": tariff.get("name"),
            "rate": tariff.get("rate"),
            "unit": tariff.get("unit"),
            "tariff_date": tariff.get("date"),
        }

