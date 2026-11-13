"""Binary sensor for the NVOA integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, time
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .api import WasteService
from .const import CONF_ADVANCE_DAYS, CONF_PICKUP_DONE_TIME, DEFAULT_ADVANCE_DAYS
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


def parse_done_time(value: Any) -> time | None:
    """Parse the 'pickup done' option ('HH:MM' or 'HH:MM:SS'); None if unset."""
    if not isinstance(value, str) or not value.strip():
        return None
    return dt_util.parse_time(value.strip())


class NvoaPickupSoonBinarySensor(NvoaEntity, BinarySensorEntity):
    """On from N days before a pickup until the pickup is done.

    "Done" is the end of the pickup day, or the configured pickup-done time.
    """

    _attr_translation_key = "pickup_soon"
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, coordinator: NvoaCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pickup_soon"
        self._scheduled: time | None = None
        self._unsub_done: Callable[[], None] | None = None

    # -- options ----------------------------------------------------------------------

    @property
    def _advance_days(self) -> int:
        return int(
            self.coordinator.config_entry.options.get(
                CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS
            )
        )

    @property
    def _done_time(self) -> time | None:
        return parse_done_time(
            self.coordinator.config_entry.options.get(CONF_PICKUP_DONE_TIME)
        )

    # -- scheduling -------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Schedule the state change at the pickup-done time."""
        await super().async_added_to_hass()
        self._reschedule()
        self.async_on_remove(self._cancel_schedule)

    @callback
    def _cancel_schedule(self) -> None:
        if self._unsub_done is not None:
            self._unsub_done()
            self._unsub_done = None

    @callback
    def _reschedule(self) -> None:
        """(Re)register the daily callback when the configured time changes."""
        done = self._done_time
        if done == self._scheduled and (done is None or self._unsub_done is not None):
            return
        self._cancel_schedule()
        self._scheduled = done
        if done is not None:
            self._unsub_done = async_track_time_change(
                self.hass,
                self._async_done_reached,
                hour=done.hour,
                minute=done.minute,
                second=done.second,
            )

    @callback
    def _async_done_reached(self, now: datetime) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Also runs when options change (the update listener pokes the coordinator)."""
        self._reschedule()
        super()._handle_coordinator_update()

    # -- state ------------------------------------------------------------------------

    def _due(self) -> list[WasteService]:
        """Services due within the window, minus today's once the pickup is done."""
        due = self.coordinator.pickups_within(self._advance_days)
        done = self._done_time
        if done is None:
            return due
        now = dt_util.now()
        if now.time() < done:
            return due
        today = now.date()
        return [s for s in due if s.next_pickup != today]

    @property
    def is_on(self) -> bool:
        """True if any service is collected within the advance window."""
        return bool(self._due())

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Which services are due and when."""
        due = self._due()
        first = due[0].next_pickup if due else None
        done = self._done_time
        return {
            "types": [s.waste_type for s in due],
            "next_pickup": first.isoformat() if first else None,
            "days_until": self.coordinator.days_until(first),
            "advance_days": self._advance_days,
            "pickup_done_time": done.strftime("%H:%M") if done else None,
        }
