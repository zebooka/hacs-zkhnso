"""Sensor platform for ZKHNSO integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ZKHDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

WATER_UNITS = {"куб.м.", "куб.м", "м³", "m³"}
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZKH sensor platform."""
    coordinator: ZKHDataUpdateCoordinator = entry.runtime_data

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

        self.meter_key = meter_key
        self._attr_unique_id = f"{self.coordinator.entry.entry_id}_meter_{meter_key}"
        self._attr_name = meter_data.get("name", f"Meter {meter_key}")
        self._attr_icon = "mdi:counter"

        if meter_data.get("units") in WATER_UNITS:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
            # A provider can correct or reset the total reading.
            self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (meter value)."""
        if not self.coordinator.data or "meters" not in self.coordinator.data:
            return None

        meters = self.coordinator.data["meters"]
        meter = meters.get(self.meter_key)
        if meter and isinstance(meter.get("value"), int | float):
            return meter["value"]
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
        self._attr_name = tariff_data.get("name", f"Tariff {tariff_key}")
        unit = tariff_data.get("unit")
        self._attr_native_unit_of_measurement = f"RUB/{unit}" if unit else "RUB"
        self._attr_icon = "mdi:currency-rub"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor (tariff value)."""
        if not self.coordinator.data or "tariffs" not in self.coordinator.data:
            return None

        tariffs = self.coordinator.data["tariffs"]
        tariff = tariffs.get(self.tariff_key)
        if tariff and isinstance(tariff.get("tariff"), int | float):
            return tariff["tariff"]
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
