"""API client for the NVOA (Nacka Vatten och Avfall) waste pickup service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
import logging
import re
from typing import Any

import aiohttp

from .const import (
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SCHEDULE_URL,
    SEARCH_URL,
)

_LOGGER = logging.getLogger(__name__)

_MS_DATE = re.compile(r"/Date\((-?\d+)")
_BUILDING_ID = re.compile(r"\((\d+)\)\s*$")
# .NET's DateTime.MinValue, used by the API to mean "no date".
_NO_DATE_MS = -62135596800000


class NvoaError(Exception):
    """Base error for the NVOA API."""


class NvoaConnectionError(NvoaError):
    """The service could not be reached."""


class NvoaResponseError(NvoaError):
    """The service answered with something unexpected (HTML error page, bad JSON)."""


@dataclass(frozen=True, slots=True)
class WasteService:
    """One waste service (bin + pickup rhythm) at an address."""

    id: int
    waste_type: str
    description: str | None
    next_pickup: date | None
    frequency: str | None
    bin_direction: str | None
    bin_type: str | None
    bin_size: str | None
    number_of_bins: int | None
    pickups_per_year: int | None
    fee_code: str | None
    start_date: date | None
    stop_date: date | None


def parse_building_id(address: str) -> str | None:
    """Return the trailing building id, e.g. 'Storgatan 1, Saltsjö-Boo (123456)'."""
    match = _BUILDING_ID.search(address)
    return match.group(1) if match else None


def address_without_id(address: str) -> str:
    """Strip the trailing '(id)' from an address string."""
    return _BUILDING_ID.sub("", address).strip()


def _clean(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _parse_ms_date(value: Any) -> date | None:
    """Parse '/Date(1767222000000)/' into a date, None for the 'no date' sentinel."""
    if not isinstance(value, str):
        return None
    match = _MS_DATE.search(value)
    if not match:
        return None
    millis = int(match.group(1))
    if millis <= _NO_DATE_MS:
        return None
    # The API stores local (Swedish) midnight as UTC milliseconds, i.e. 22:00 or
    # 23:00 the evening before. Adding 12 h lands on the intended calendar day.
    return (datetime.fromtimestamp(millis / 1000, tz=UTC) + timedelta(hours=12)).date()


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bin_size(bin_type: Any) -> str | None:
    if not isinstance(bin_type, dict):
        return None
    size = bin_type.get("Size")
    unit = _clean(bin_type.get("Unit")) or ""
    try:
        return f"{float(size):g} {unit}".strip()
    except (TypeError, ValueError):
        return None


def parse_services(payload: dict[str, Any], today: date) -> dict[int, WasteService]:
    """Parse a GetWastePickupSchedule response into active services keyed by ID."""
    raw = payload.get("RhServices")
    if not isinstance(raw, list):
        raise NvoaResponseError("Response is missing 'RhServices'")

    services: dict[int, WasteService] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        service_id = _to_int(item.get("ID"))
        if service_id is None:
            continue
        stop_date = _parse_ms_date(item.get("StopDate"))
        if item.get("IsActive") is False or (stop_date and stop_date < today):
            continue

        bin_type = item.get("BinType")
        fee = item.get("Fee") if isinstance(item.get("Fee"), dict) else {}
        waste_type = _clean(item.get("WasteType")) or _clean(item.get("Description"))
        services[service_id] = WasteService(
            id=service_id,
            waste_type=waste_type or f"Service {service_id}",
            description=_clean(item.get("Description")),
            next_pickup=_parse_iso_date(item.get("NextWastePickup")),
            frequency=_clean(item.get("WastePickupFrequency")),
            bin_direction=_clean(item.get("BinDirection")),
            bin_type=(
                _clean(bin_type.get("ContainerType"))
                if isinstance(bin_type, dict)
                else None
            ),
            bin_size=_bin_size(bin_type),
            number_of_bins=_to_int(item.get("NumberOfBins")),
            pickups_per_year=_to_int(item.get("WastePickupsPerYear")),
            fee_code=_clean(fee.get("Code")),
            start_date=_parse_ms_date(item.get("StartDate")),
            stop_date=stop_date,
        )
    return services


class NvoaClient:
    """Thin async client for the NVOA web endpoints."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = {**REQUEST_HEADERS, **kwargs.pop("headers", {})}
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                **kwargs,
            ) as response:
                if response.status != 200:
                    raise NvoaResponseError(f"HTTP {response.status} from {url}")
                text = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NvoaConnectionError(f"Cannot reach NVOA: {err}") from err

        try:
            data = json.loads(text)
        except ValueError as err:
            _LOGGER.debug("Non-JSON response from %s: %.200s", url, text)
            raise NvoaResponseError(
                "NVOA returned a non-JSON response (server error or blocked request)"
            ) from err
        if not isinstance(data, dict):
            raise NvoaResponseError("Unexpected JSON structure from NVOA")
        return data

    async def async_search_addresses(self, text: str) -> list[str]:
        """Search addresses. Returns up to 10 strings like 'Gata 1, Ort (123456)'."""
        body = json.dumps({"searchText": text}, ensure_ascii=False).encode("utf-8")
        data = await self._request(
            "POST",
            SEARCH_URL,
            data=body,
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        if not data.get("Succeeded"):
            raise NvoaResponseError("Address search was not successful")
        buildings = data.get("Buildings") or []
        return [b for b in buildings if isinstance(b, str)]

    async def async_get_schedule(
        self, address: str, today: date | None = None
    ) -> dict[int, WasteService]:
        """Fetch the active waste services for a full address string."""
        data = await self._request("GET", SCHEDULE_URL, params={"address": address})
        return parse_services(data, today or date.today())
