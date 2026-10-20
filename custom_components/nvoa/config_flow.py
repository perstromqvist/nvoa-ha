"""Config flow for the NVOA integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .api import (
    NvoaClient,
    NvoaConnectionError,
    NvoaError,
    address_without_id,
    parse_building_id,
)
from .const import (
    CONF_ADDRESS,
    CONF_ADVANCE_DAYS,
    CONF_BUILDING_ID,
    CONF_SEARCH,
    DEFAULT_ADVANCE_DAYS,
    DOMAIN,
    MAX_ADVANCE_DAYS,
    MIN_SEARCH_LENGTH,
)

_LOGGER = logging.getLogger(__name__)


class NvoaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Search for an address, pick it from the hits, verify it has services."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._results: list[str] = []

    # -- shared helpers ---------------------------------------------------------------

    def _client(self) -> NvoaClient:
        return NvoaClient(async_get_clientsession(self.hass))

    async def _async_search(self, text: str) -> str | None:
        """Run the address search. Returns an error key, or None on success."""
        text = text.strip()
        if len(text) < MIN_SEARCH_LENGTH:
            return "search_too_short"
        try:
            self._results = await self._client().async_search_addresses(text)
        except NvoaConnectionError:
            return "cannot_connect"
        except NvoaError:
            return "invalid_response"
        return None if self._results else "no_results"

    async def _async_check_address(self, address: str) -> str | None:
        """Verify the address returns at least one active service."""
        try:
            services = await self._client().async_get_schedule(
                address, dt_util.now().date()
            )
        except NvoaConnectionError:
            return "cannot_connect"
        except NvoaError:
            return "invalid_response"
        return None if services else "no_services"

    def _search_schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        return self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_SEARCH): TextSelector()}), user_input
        )

    def _select_schema(self) -> vol.Schema:
        default = self._results[0] if len(self._results) == 1 else vol.UNDEFINED
        return vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default=default): SelectSelector(
                    SelectSelectorConfig(
                        options=self._results, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

    # -- initial setup ----------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: free-text address search."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._async_search(user_input[CONF_SEARCH]):
                errors["base"] = error
            else:
                return await self.async_step_select()
        return self.async_show_form(
            step_id="user", data_schema=self._search_schema(user_input), errors=errors
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: choose one of the matching addresses."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if (building_id := parse_building_id(address)) is None:
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(building_id)
                self._abort_if_unique_id_configured()
                if error := await self._async_check_address(address):
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title=address_without_id(address),
                        data={CONF_ADDRESS: address, CONF_BUILDING_ID: building_id},
                    )
        return self.async_show_form(
            step_id="select", data_schema=self._select_schema(), errors=errors
        )

    # -- change address ---------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing entry (step 1: search)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := await self._async_search(user_input[CONF_SEARCH]):
                errors["base"] = error
            else:
                return await self.async_step_reconfigure_select()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._search_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of an existing entry (step 2: choose)."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if (building_id := parse_building_id(address)) is None:
                errors["base"] = "invalid_response"
            else:
                existing = await self.async_set_unique_id(building_id)
                if existing is not None and existing.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                if error := await self._async_check_address(address):
                    errors["base"] = error
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=building_id,
                        title=address_without_id(address),
                        data={CONF_ADDRESS: address, CONF_BUILDING_ID: building_id},
                    )
        return self.async_show_form(
            step_id="reconfigure_select",
            data_schema=self._select_schema(),
            errors=errors,
        )

    # -- options ----------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> NvoaOptionsFlow:
        """Return the options flow."""
        return NvoaOptionsFlow()


class NvoaOptionsFlow(OptionsFlow):
    """Advance notice for the 'pickup soon' binary sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_ADVANCE_DAYS: int(user_input[CONF_ADVANCE_DAYS])}
            )
        current = self.config_entry.options.get(CONF_ADVANCE_DAYS, DEFAULT_ADVANCE_DAYS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADVANCE_DAYS, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=MAX_ADVANCE_DAYS,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
