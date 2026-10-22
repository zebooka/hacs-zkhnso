"""Tests for the ZKHNSO config flow input validation."""
import pytest

from custom_components.zkhnso.config_flow import InvalidAuth, validate_input


@pytest.mark.asyncio
async def test_validate_input_rejects_blank_credentials(hass) -> None:
    """Whitespace-only credentials are rejected before making HTTP requests."""
    with pytest.raises(InvalidAuth):
        await validate_input(hass, {"username": " ", "password": "password"})

    with pytest.raises(InvalidAuth):
        await validate_input(hass, {"username": "user", "password": " "})
