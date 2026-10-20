"""Base entity for the NVOA integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import address_without_id
from .const import CONF_ADDRESS, DOMAIN, MANUFACTURER, REFERER_URL
from .coordinator import NvoaCoordinator


class NvoaEntity(CoordinatorEntity[NvoaCoordinator]):
    """Base class: one device per address."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NvoaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        street = address_without_id(entry.data[CONF_ADDRESS]).split(",")[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"NVOA {street}",
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=REFERER_URL,
        )
