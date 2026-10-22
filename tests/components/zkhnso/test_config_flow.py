"""Tests for the ZKHNSO config flow input validation."""
import asyncio

import pytest

from custom_components.zkhnso.config_flow import InvalidAuth, validate_input


def test_validate_input_rejects_blank_credentials() -> None:
    """Whitespace-only credentials are rejected before making HTTP requests."""
    with pytest.raises(InvalidAuth):
        asyncio.run(
            validate_input(None, {"username": " ", "password": "password"})
        )

    with pytest.raises(InvalidAuth):
        asyncio.run(
            validate_input(None, {"username": "user", "password": " "})
        )
