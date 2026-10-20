"""Tests for the API parsing."""

from datetime import date

import pytest

from custom_components.nvoa.api import (
    NvoaResponseError,
    address_without_id,
    parse_building_id,
    parse_services,
)

TODAY = date(2026, 10, 20)


async def test_parse_services(schedule_payload):
    services = parse_services(schedule_payload, TODAY)
    assert set(services) == {142911, 244238, 244239, 244240}

    mat = services[244240]
    assert mat.waste_type == "Mat/Rest"
    assert mat.next_pickup == date(2026, 10, 23)
    assert mat.frequency == "Fredag udda vecka"  # trailing space trimmed
    assert mat.bin_size == "240 L"
    assert mat.bin_type == "Tvåfackskärl"
    assert mat.fee_code == "NYKÄ1"
    assert mat.stop_date is None
    assert mat.start_date == date(2026, 1, 1)

    assert services[244239].next_pickup == date(2026, 11, 10)


async def test_inactive_and_stopped_services_are_skipped(schedule_payload):
    items = schedule_payload["RhServices"]
    items[0]["IsActive"] = False
    items[1]["StopDate"] = "/Date(1700000000000)/"  # Nov 2023
    services = parse_services(schedule_payload, TODAY)
    assert set(services) == {244239, 244240}


async def test_missing_pickup_date(schedule_payload):
    schedule_payload["RhServices"][0]["NextWastePickup"] = None
    assert parse_services(schedule_payload, TODAY)[142911].next_pickup is None


async def test_bad_payload():
    with pytest.raises(NvoaResponseError):
        parse_services({"nope": 1}, TODAY)


async def test_building_id():
    addr = "Storgatan 1, Saltsjö-Boo (123456)"
    assert parse_building_id(addr) == "123456"
    assert address_without_id(addr) == "Storgatan 1, Saltsjö-Boo"
    assert parse_building_id("no id") is None
