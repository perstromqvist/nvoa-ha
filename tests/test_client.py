"""HTTP-level tests for the client (headers, body encoding, error mapping)."""

import json
from datetime import date

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.nvoa.api import (
    NvoaClient,
    NvoaConnectionError,
    NvoaResponseError,
)
from custom_components.nvoa.const import SCHEDULE_URL, SEARCH_URL


async def test_search_request_and_parse(hass, aioclient_mock, search_payload):
    aioclient_mock.post(SEARCH_URL, text=json.dumps(search_payload))
    client = NvoaClient(async_get_clientsession(hass))
    result = await client.async_search_addresses("Storgatan 1")

    assert result == search_payload["Buildings"]
    method, url, data, headers = aioclient_mock.mock_calls[0]
    assert json.loads(data.decode("utf-8")) == {"searchText": "Storgatan 1"}
    assert headers["Content-Type"] == "application/json; charset=UTF-8"
    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert "Mozilla" in headers["User-Agent"]
    assert headers["Referer"].endswith("/simplewastepickup")


async def test_schedule_request_and_parse(hass, aioclient_mock, schedule_payload):
    aioclient_mock.get(SCHEDULE_URL, text=json.dumps(schedule_payload))
    client = NvoaClient(async_get_clientsession(hass))
    services = await client.async_get_schedule(
        "Exempelvägen 1, Saltsjö-Boo (000000)", date(2026, 10, 20)
    )
    assert len(services) == 4
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["address"] == "Exempelvägen 1, Saltsjö-Boo (000000)"


async def test_html_error_page_is_response_error(hass, aioclient_mock):
    aioclient_mock.post(SEARCH_URL, text="<!DOCTYPE html><title>Runtime Error</title>")
    client = NvoaClient(async_get_clientsession(hass))
    with pytest.raises(NvoaResponseError):
        await client.async_search_addresses("Storgatan")


async def test_waf_block_is_response_error(hass, aioclient_mock):
    aioclient_mock.get(SCHEDULE_URL, status=403, text="Request Rejected")
    client = NvoaClient(async_get_clientsession(hass))
    with pytest.raises(NvoaResponseError):
        await client.async_get_schedule("x (1)")


async def test_timeout_is_connection_error(hass, aioclient_mock):
    aioclient_mock.get(SCHEDULE_URL, exc=TimeoutError)
    client = NvoaClient(async_get_clientsession(hass))
    with pytest.raises(NvoaConnectionError):
        await client.async_get_schedule("x (1)")
