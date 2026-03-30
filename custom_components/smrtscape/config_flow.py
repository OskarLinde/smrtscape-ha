from __future__ import annotations

from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmrtScapeApiClient
from .const import CONF_BASE_URL, CONF_POLL_INTERVAL, DEFAULT_BASE_URL, DEFAULT_POLL_INTERVAL, DOMAIN


def _validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise vol.Invalid("Base URL must use https")
    if not parsed.netloc:
        raise vol.Invalid("Base URL must include a hostname")
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"smrtscape.com", "www.smrtscape.com"}:
        raise vol.Invalid("Base URL must be smrtscape.com")
    return f"https://{hostname}"


class SmrtScapeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                normalized_base_url = _validate_base_url(user_input[CONF_BASE_URL])
            except vol.Invalid:
                errors[CONF_BASE_URL] = "invalid_base_url"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                client = SmrtScapeApiClient(
                    session=async_get_clientsession(self.hass),
                    base_url=normalized_base_url,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                try:
                    await client.async_login()
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"SMRTScape ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_BASE_URL: normalized_base_url,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmrtScapeOptionsFlowHandler(config_entry)


class SmrtScapeOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=3600)),
                }
            ),
        )
