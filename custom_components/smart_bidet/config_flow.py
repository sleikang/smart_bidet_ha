"""配置流程：蓝牙自动发现 + 手动填 MAC。"""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv

from .const import BLE_LOCAL_NAME, CONF_ADDRESS, DOMAIN, NAME


def _normalize_address(value: str) -> str:
    """接受 AA:BB:CC:DD:EE:FF / aabbccddeeff / macOS UUID 三种写法。"""
    value = value.strip()
    if len(value) == 36 and value.count("-") == 4:
        return value.upper()
    hex_only = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(hex_only) != 12:
        raise vol.Invalid("invalid address")
    return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2)).upper()


class SmartBidetConfigFlow(ConfigFlow, domain=DOMAIN):
    """处理发现与手动配置。"""

    VERSION = 1

    _address: str | None = None
    _device_name: str | None = None

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        address = _normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._address = address
        self._device_name = discovery_info.name or BLE_LOCAL_NAME
        self.context["title_placeholders"] = {"name": self._device_name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None and self._address is not None:
            return self.async_create_entry(
                title=self._device_name or NAME,
                data={CONF_ADDRESS: self._address},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._device_name or NAME},
        )

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                address = _normalize_address(str(user_input[CONF_ADDRESS]))
            except vol.Invalid:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data={CONF_ADDRESS: address})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS, default=""): cv.string}),
            errors=errors,
        )
