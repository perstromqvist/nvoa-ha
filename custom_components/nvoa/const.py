"""Constants for the NVOA waste pickup integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "nvoa"

BASE_URL: Final = "https://futureweb.nvoa.se/EDP/FutureWebBasic/SimpleWastePickup"
SEARCH_URL: Final = f"{BASE_URL}/SearchAdress"
SCHEDULE_URL: Final = f"{BASE_URL}/GetWastePickupSchedule"
REFERER_URL: Final = f"{BASE_URL}/simplewastepickup"

CONF_ADDRESS: Final = "address"
CONF_BUILDING_ID: Final = "building_id"
CONF_SEARCH: Final = "search"
CONF_ADVANCE_DAYS: Final = "advance_days"

DEFAULT_ADVANCE_DAYS: Final = 1
MAX_ADVANCE_DAYS: Final = 14
MIN_SEARCH_LENGTH: Final = 3

UPDATE_INTERVAL: Final = timedelta(hours=6)
REQUEST_TIMEOUT: Final = 30

# NVOA sits behind a WAF that rejects requests without browser-like headers.
REQUEST_HEADERS: Final = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": REFERER_URL,
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

MANUFACTURER: Final = "Nacka Vatten och Avfall"
