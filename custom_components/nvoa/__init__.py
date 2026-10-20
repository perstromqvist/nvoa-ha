"""NVOA (Nacka Vatten och Avfall) waste pickup integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NvoaClient
from .coordinator import NvoaConfigEntry, NvoaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NvoaConfigEntry) -> bool:
    """Set up NVOA from a config entry."""
    client = NvoaClient(async_get_clientsession(hass))
    coordinator = NvoaCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    coordinator.async_start_midnight_tick()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: NvoaConfigEntry) -> None:
    """Re-evaluate entities when options change (advance days is read at runtime)."""
    entry.runtime_data.async_update_listeners()


async def async_unload_entry(hass: HomeAssistant, entry: NvoaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
