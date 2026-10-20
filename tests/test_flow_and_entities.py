"""Config flow, setup and entity tests."""

from datetime import date
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nvoa.api import NvoaConnectionError, parse_services
from custom_components.nvoa.const import (
    CONF_ADDRESS,
    CONF_ADVANCE_DAYS,
    CONF_BUILDING_ID,
    CONF_SEARCH,
    DOMAIN,
)

ADDRESS = "Exempelvägen 1, Saltsjö-Boo (000000)"


def _patch_api(search_payload, schedule_payload):
    services = parse_services(schedule_payload, date(2026, 10, 20))
    return (
        patch(
            "custom_components.nvoa.config_flow.NvoaClient.async_search_addresses",
            return_value=search_payload["Buildings"],
        ),
        patch(
            "custom_components.nvoa.api.NvoaClient.async_get_schedule",
            return_value=services,
        ),
        patch(
            "custom_components.nvoa.config_flow.NvoaClient.async_get_schedule",
            return_value=services,
        ),
    )


async def test_full_flow(hass: HomeAssistant, search_payload, schedule_payload):
    p1, p2, p3 = _patch_api(search_payload, schedule_payload)
    with p1, p2, p3:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "Ex"}
        )
        assert result["errors"] == {"base": "search_too_short"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "Exempelvägen"}
        )
        assert result["step_id"] == "select"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Exempelvägen 1, Saltsjö-Boo"
        assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_BUILDING_ID: "000000"}
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "000000"


async def test_search_connection_error(hass: HomeAssistant):
    with patch(
        "custom_components.nvoa.config_flow.NvoaClient.async_search_addresses",
        side_effect=NvoaConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "Exempelvägen"}
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_address_aborts(
    hass: HomeAssistant, search_payload, schedule_payload
):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000",
        data={CONF_ADDRESS: ADDRESS, CONF_BUILDING_ID: "000000"},
    ).add_to_hass(hass)
    p1, p2, p3 = _patch_api(search_payload, schedule_payload)
    with p1, p2, p3:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "Exempelvägen"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _setup(hass, search_payload, schedule_payload, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000",
        title="Exempelvägen 1, Saltsjö-Boo",
        data={CONF_ADDRESS: ADDRESS, CONF_BUILDING_ID: "000000"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    p1, p2, p3 = _patch_api(search_payload, schedule_payload)
    with p1, p2, p3:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_entities(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, search_payload, schedule_payload
):
    freezer.move_to("2026-10-22 12:00:00+02:00")
    await _setup(hass, search_payload, schedule_payload)

    states = {s.entity_id: s for s in hass.states.async_all()}
    names = sorted(states)
    print(names)

    mat = states["sensor.nvoa_exempelvagen_1_mat_rest"]
    assert mat.state == "2026-10-23"
    assert mat.attributes["days_until"] == 1
    assert mat.attributes["frequency"] == "Fredag udda vecka"
    assert mat.attributes["bin_size"] == "240 L"

    nxt = states["sensor.nvoa_exempelvagen_1_next_pickup"]
    assert nxt.state == "2026-10-23"
    assert sorted(nxt.attributes["types"]) == ["Mat/Rest", "Restavfall"]

    soon = states["binary_sensor.nvoa_exempelvagen_1_pickup_soon"]
    assert soon.state == "on"
    assert sorted(soon.attributes["types"]) == ["Mat/Rest", "Restavfall"]


async def test_pickup_soon_window(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, search_payload, schedule_payload
):
    freezer.move_to("2026-10-20 12:00:00+02:00")  # 3 days before the 23rd
    await _setup(hass, search_payload, schedule_payload)
    eid = "binary_sensor.nvoa_exempelvagen_1_pickup_soon"
    assert hass.states.get(eid).state == "off"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={CONF_ADVANCE_DAYS: 3})
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == "on"


async def test_reconfigure_changes_address(
    hass: HomeAssistant, search_payload, schedule_payload
):
    entry = await _setup(hass, search_payload, schedule_payload)
    new_address = "Exempelvägen 2, Saltsjö-Boo (000001)"
    p1, p2, p3 = _patch_api(search_payload, schedule_payload)
    with p1, p2, p3:
        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "Exempelvägen"}
        )
        assert result["step_id"] == "reconfigure_select"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: new_address}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "000001"
    assert entry.data[CONF_ADDRESS] == new_address
    assert entry.title == "Exempelvägen 2, Saltsjö-Boo"
