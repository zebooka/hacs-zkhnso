"""Tests for ZKHNSO sensor entities."""
from types import SimpleNamespace

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfEnergy, UnitOfVolume

from custom_components.zkhnso.sensor import ZKHMeterSensor, ZKHTariffSensor


def _coordinator(data: dict) -> SimpleNamespace:
    """Create the coordinator shape used by entity unit tests."""
    return SimpleNamespace(
        data=data,
        entry=SimpleNamespace(entry_id="entry", data={"account_id": 42, "username": "user"}),
    )


def test_meter_uses_current_coordinator_data_and_clears_removed_meter() -> None:
    """Meters do not retain stale readings after a successful refresh."""
    data = {"meters": {"1": {"name": "Вода", "unit": "куб.м.", "value": 12.5}}}
    coordinator = _coordinator(data)
    sensor = ZKHMeterSensor(coordinator, "1", data["meters"]["1"])

    assert sensor.native_value == 12.5
    assert sensor.device_class == SensorDeviceClass.WATER
    assert sensor.native_unit_of_measurement == UnitOfVolume.CUBIC_METERS

    coordinator.data = {"meters": {}}
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_meter_device_classes() -> None:
    """Gas, electricity, heat, and generic volumes use correct device classes."""
    cases = [
        ("Газ", "куб.м.", SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS),
        ("Электричество", "кВтч", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
        ("Тепло", "Гкал", SensorDeviceClass.ENERGY, UnitOfEnergy.GIGA_CALORIE),
    ]
    for index, (name, unit, device_class, native_unit) in enumerate(cases):
        meter = {"name": name, "unit": unit, "value": 1}
        sensor = ZKHMeterSensor(_coordinator({"meters": {str(index): meter}}), str(index), meter)
        assert sensor.device_class == device_class
        assert sensor.native_unit_of_measurement == native_unit


def test_tariff_uses_current_data_and_clears_removed_tariff() -> None:
    """Tariffs use `rate` and clear stale state when removed."""
    tariff = {"name": "Water", "unit": "куб.м.", "rate": 50.25, "norm": 3, "from_date": "2026-01-01"}
    coordinator = _coordinator({"tariffs": {"Water": tariff}})
    sensor = ZKHTariffSensor(coordinator, "Water", tariff)

    assert sensor.native_value == 50.25
    assert sensor.device_class == SensorDeviceClass.MONETARY
    assert sensor.extra_state_attributes["normalized_unit"] == "RUB/m³"

    coordinator.data = {"tariffs": {}}
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}
