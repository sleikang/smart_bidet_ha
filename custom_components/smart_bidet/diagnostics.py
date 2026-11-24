"""诊断数据导出（用于排查协议问题）。"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BidetCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry_data": dict(entry.data),
        "runtime": coordinator.diagnostics_snapshot(),
    }
