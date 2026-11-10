"""Sensors for the NVOA integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import WasteService
from .const import DOMAIN
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


def _same_type(a: str | None, b: str | None) -> bool:
    return bool(a and b) and a.strip().casefold() == b.strip().casefold()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NvoaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors.

    Service sensors outlive gaps in NVOA's data: infrequent services (glass is
    emptied quarterly) can drop out of the response between periods. Sensors
    created earlier are restored from the entity registry and show "unknown"
    until NVOA schedules the service again, possibly under a new service ID,
    in which case the existing sensor takes it over by waste type.
    """
    coordinator = entry.runtime_data
    async_add_entities([NvoaNextPickupSensor(coordinator)])

    sensors: list[NvoaServiceSensor] = []

    # Restore sensors that exist in the registry, whether or not NVOA lists them now.
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.domain != Platform.SENSOR or reg.platform != DOMAIN:
            continue
        suffix = reg.unique_id.removeprefix(prefix)
        if suffix == reg.unique_id or not suffix.isdigit():
            continue
        sid = int(suffix)
        service = coordinator.data.get(sid)
        waste_type = (
            service.waste_type if service else reg.original_name or f"Service {sid}"
        )
        sensors.append(NvoaServiceSensor(coordinator, sid, waste_type))

    @callback
    def _sync_services() -> None:
        """Rebind orphaned sensors to new IDs, then add sensors for new services."""
        data = coordinator.data or {}
        claimed = {s.bound_id for s in sensors if s.bound_id in data}
        for sensor in sensors:
            if sensor.bound_id in data:
                continue
            match = next(
                (
                    sid
                    for sid, svc in data.items()
                    if sid not in claimed and _same_type(svc.waste_type, sensor.waste_type)
                ),
                None,
            )
            if match is not None:
                claimed.add(match)
                sensor.rebind(match)

        new = [
            NvoaServiceSensor(coordinator, sid, svc.waste_type)
            for sid, svc in data.items()
            if sid not in claimed
        ]
        if new:
            sensors.extend(new)
            async_add_entities(new)

    restored = list(sensors)
    _sync_services()
    async_add_entities(restored)
    entry.async_on_unload(coordinator.async_add_listener(_sync_services))


class NvoaServiceSensor(NvoaEntity, SensorEntity):
    """Next pickup date for a single waste service."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self, coordinator: NvoaCoordinator, service_id: int, waste_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.waste_type = waste_type
        self.bound_id = service_id
        self._last_service: WasteService | None = coordinator.data.get(service_id)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{service_id}"
        self._attr_name = waste_type
        self._attr_icon = _icon_for(waste_type)

    @callback
    def rebind(self, service_id: int) -> None:
        """Follow the service after NVOA moved it to a new ID."""
        self.bound_id = service_id
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def _service(self) -> WasteService | None:
        service = (self.coordinator.data or {}).get(self.bound_id)
        if service is not None:
            self._last_service = service
        return service

    @property
    def native_value(self) -> date | None:
        """Next pickup date, None (unknown) when NVOA has none scheduled."""
        service = self._service
        if service is None or self.coordinator.days_until(service.next_pickup) is None:
            return None
        return service.next_pickup

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Details about the bin and the pickup rhythm."""
        service = self._service
        info = service or self._last_service
        attrs: dict[str, Any] = {
            "scheduled": service is not None
            and self.coordinator.days_until(service.next_pickup) is not None,
            "days_until": (
                self.coordinator.days_until(service.next_pickup) if service else None
            ),
            "service_id": self.bound_id,
        }
        if info is not None:
            attrs.update(
                {
                    "frequency": info.frequency,
                    "bin_direction": info.bin_direction,
                    "bin_size": info.bin_size,
                    "bin_type": info.bin_type,
                    "number_of_bins": info.number_of_bins,
                    "pickups_per_year": info.pickups_per_year,
                    "fee_code": info.fee_code,
                    "description": info.description,
                }
            )
        return attrs


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
