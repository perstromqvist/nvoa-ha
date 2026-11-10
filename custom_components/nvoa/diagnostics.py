"""Diagnostics for the NVOA integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_BUILDING_ID
from .coordinator import NvoaConfigEntry

TO_REDACT = {
    CONF_ADDRESS,
    CONF_BUILDING_ID,
    "Address",
    "Adress",
    "BuildingId",
    "CustomerName",
    "CustomerNumber",
    "Email",
    "Phone",
    "PersonalNumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NvoaConfigEntry
) -> dict[str, Any]:
    """Return the config entry, parsed services and NVOA's raw response."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "services": {
            str(sid): {k: str(v) if v is not None else None for k, v in asdict(s).items()}
            for sid, s in (coordinator.data or {}).items()
        },
        "raw_schedule": async_redact_data(
            coordinator.client.last_schedule_payload or {}, TO_REDACT
        ),
    }
