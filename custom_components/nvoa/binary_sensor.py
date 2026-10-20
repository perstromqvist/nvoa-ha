"""Binary sensor for the NVOA integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS
from .coordinator import NvoaConfigEntry, NvoaCoordinator
from .entity import NvoaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NvoaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    async_add_entities([NvoaPickupSoonBinarySensor(entry.runtime_data)])


class NvoaPickupSoonBinarySensor(NvoaEntity, BinarySensorEntity):
    """On from N days before a pickup until the end of the pickup day."""

    _attr_translation_key = "pickup_soon"
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, coordinator: NvoaCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pickup_soon"

    @property
    def _advance_days(self) -> int:
        return int(
            self.coordinator.config_entry.options.get(
                CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS
            )
        )

    @property
    def is_on(self) -> bool:
        """True if any service is collected within the advance window."""
        return bool(self.coordinator.pickups_within(self._advance_days))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Which services are due and when."""
        due = self.coordinator.pickups_within(self._advance_days)
        first = due[0].next_pickup if due else None
        return {
            "types": [s.waste_type for s in due],
            "next_pickup": first.isoformat() if first else None,
            "days_until": self.coordinator.days_until(first),
            "advance_days": self._advance_days,
        }
