"""Data update coordinator for the NVOA integration."""

from __future__ import annotations

from datetime import date, datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NvoaClient, NvoaError, WasteService
from .const import CONF_ADDRESS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type NvoaConfigEntry = ConfigEntry[NvoaCoordinator]


class NvoaCoordinator(DataUpdateCoordinator[dict[int, WasteService]]):
    """Fetch the pickup schedule for one address."""

    config_entry: NvoaConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: NvoaConfigEntry, client: NvoaClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, WasteService]:
        try:
            return await self.client.async_get_schedule(
                self.config_entry.data[CONF_ADDRESS], dt_util.now().date()
            )
        except NvoaError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def async_start_midnight_tick(self) -> None:
        """Re-evaluate 'days until' just after midnight without waiting for the poll."""
        self.config_entry.async_on_unload(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=5, second=0
            )
        )

    async def _async_midnight(self, now: datetime) -> None:
        today = dt_util.as_local(now).date()
        if any(s.next_pickup and s.next_pickup < today for s in self.data.values()):
            # A pickup date has passed; ask NVOA for the next one.
            await self.async_request_refresh()
        self.async_update_listeners()

    # -- helpers used by the entities -------------------------------------------------

    @staticmethod
    def today() -> date:
        """Today's date in the Home Assistant time zone."""
        return dt_util.now().date()

    @staticmethod
    def days_until(pickup: date | None) -> int | None:
        """Days from today until a pickup date (None if unknown or already passed)."""
        if pickup is None:
            return None
        days = (pickup - dt_util.now().date()).days
        return days if days >= 0 else None

    def upcoming(self) -> list[WasteService]:
        """Services with a pickup today or later, sorted by date then name."""
        return sorted(
            (s for s in self.data.values() if self.days_until(s.next_pickup) is not None),
            key=lambda s: (s.next_pickup, s.waste_type),
        )

    def next_pickup(self) -> tuple[date, list[WasteService]] | None:
        """The earliest upcoming date and the services collected that day."""
        upcoming = self.upcoming()
        if not upcoming:
            return None
        first = upcoming[0].next_pickup
        assert first is not None
        return first, [s for s in upcoming if s.next_pickup == first]

    def pickups_within(self, days: int) -> list[WasteService]:
        """Services collected within the next `days` days (0 = today only)."""
        return [
            s
            for s in self.upcoming()
            if (d := self.days_until(s.next_pickup)) is not None and d <= days
        ]
