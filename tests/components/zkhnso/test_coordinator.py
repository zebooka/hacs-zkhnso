"""Tests for the ZKHNSO data update coordinator."""
import asyncio
from types import SimpleNamespace

from custom_components.zkhnso.coordinator import ZKHDataUpdateCoordinator


class _Client:
    """Successful API client test double."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def preflight(self):
        return {"JSESSIONID": "session", "FORM_TOKEN": "token"}

    async def login(self):
        return True

    async def get_meters(self):
        return {"serial": {"value": 12}}

    async def get_tariffs(self):
        return {"Water": {"rate_per_unit": 50}}


def test_coordinator_returns_meter_and_tariff_containers(monkeypatch) -> None:
    """The coordinator wraps parser results in the structure used by sensors."""
    import custom_components.zkhnso.coordinator as coordinator_module

    monkeypatch.setattr(coordinator_module, "ZKHAPIClient", lambda *_: _Client())
    coordinator = object.__new__(ZKHDataUpdateCoordinator)
    coordinator.entry = SimpleNamespace(data={"username": "user", "password": "pass"})

    assert asyncio.run(coordinator._async_update_data()) == {
        "meters": {"serial": {"value": 12}},
        "tariffs": {"Water": {"rate_per_unit": 50}},
    }
