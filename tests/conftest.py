"""Shared fixtures."""

import json
from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components in tests."""
    yield


@pytest.fixture
def schedule_payload() -> dict:
    """A real GetWastePickupSchedule response (address anonymised)."""
    return json.loads((FIXTURES / "schedule.json").read_text(encoding="utf-8"))


@pytest.fixture
def search_payload() -> dict:
    """A SearchAdress response."""
    return json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))
