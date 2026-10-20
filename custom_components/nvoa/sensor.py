"""Sensors for the NVOA integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import WasteService
from .coordinator import NvoaConfigEntry, NvoaCoordinator
from .entity import NvoaEntity

PARALLEL_UPDATES = 0

_ICONS = (
    ("glas", "mdi:bottle-wine"),
    ("mat", "mdi:food-apple"),
    ("plast", "mdi:recycle"),
    ("papper", "mdi:recycle"),
    ("tidning", "mdi:newspaper"),
    ("trädgård", "mdi:leaf"),
    ("grov", "mdi:sofa"),
)


def _icon_for(waste_type: str) -> str:
    lowered = waste_type.lower()
    for keyword, icon in _ICONS:
        if keyword in lowered:
            return icon
    return "mdi:trash-can"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NvoaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors; services that appear later are added dynamically."""
    coordinator = entry.runtime_data
    async_add_entities([NvoaNextPickupSensor(coordinator)])

    known: set[int] = set()

    @callback
    def _add_new_services() -> None:
        new = [sid for sid in coordinator.data if sid not in known]
        if new:
            known.update(new)
            async_add_entities(NvoaServiceSensor(coordinator, sid) for sid in new)

    _add_new_services()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_services))


class NvoaServiceSensor(NvoaEntity, SensorEntity):
    """Next pickup date for a single waste service."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: NvoaCoordinator, service_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._service_id = service_id
        service = coordinator.data[service_id]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{service_id}"
        self._attr_name = service.waste_type
        self._attr_icon = _icon_for(service.waste_type)

    @property
    def _service(self) -> WasteService | None:
        return self.coordinator.data.get(self._service_id)

    @property
    def available(self) -> bool:
        """Unavailable if the update failed or NVOA dropped the service."""
        return super().available and self._service is not None

    @property
    def native_value(self) -> date | None:
        """Next pickup date (None once it has passed and no refresh has landed yet)."""
        service = self._service
        if service is None or self.coordinator.days_until(service.next_pickup) is None:
            return None
        return service.next_pickup

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Details about the bin and the pickup rhythm."""
        service = self._service
        if service is None:
            return None
        return {
            "days_until": self.coordinator.days_until(service.next_pickup),
            "frequency": service.frequency,
            "bin_direction": service.bin_direction,
            "bin_size": service.bin_size,
            "bin_type": service.bin_type,
            "number_of_bins": service.number_of_bins,
            "pickups_per_year": service.pickups_per_year,
            "fee_code": service.fee_code,
            "description": service.description,
        }


class NvoaNextPickupSensor(NvoaEntity, SensorEntity):
    """Earliest upcoming pickup across all services."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "next_pickup"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: NvoaCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_next_pickup"

    @property
    def native_value(self) -> date | None:
        """Date of the next pickup."""
        result = self.coordinator.next_pickup()
        return result[0] if result else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Which services are collected on that date."""
        result = self.coordinator.next_pickup()
        if result is None:
            return {"types": [], "days_until": None}
        pickup, services = result
        return {
            "types": [s.waste_type for s in services],
            "days_until": self.coordinator.days_until(pickup),
        }
