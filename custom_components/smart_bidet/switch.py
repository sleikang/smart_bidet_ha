"""开关类实体。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetSwitchDescription(SwitchEntityDescription):
    """状态取值 + 开/关命令。"""

    state_fn: Callable[[BidetCoordinator], bool | None]
    on_cmd: str
    off_cmd: str


SWITCHES: tuple[BidetSwitchDescription, ...] = (
    BidetSwitchDescription(
        key="auto_flush",
        name="自动冲水",
        icon="mdi:water-check",
        state_fn=lambda c: c.data.auto_flush if c.data else None,
        on_cmd="auto_flush_on",
        off_cmd="auto_flush_off",
    ),
    BidetSwitchDescription(
        key="auto_foam",
        name="自动泡沫",
        icon="mdi:chart-bubble",
        state_fn=lambda c: c.data.auto_foam if c.data else None,
        on_cmd="auto_foam_on",
        off_cmd="auto_foam_off",
    ),
    BidetSwitchDescription(
        key="auto_lid",
        name="自动翻盖",
        icon="mdi:toilet",
        # 小程序没有独立回读位，用"感距档 1..14 有模块"推导
        state_fn=lambda c: (0 < c.data.sensing_distance_gear < 15) if c.data else None,
        on_cmd="auto_lid_on",
        off_cmd="auto_lid_off",
    ),
    BidetSwitchDescription(
        key="light_ring",
        name="灯圈",
        icon="mdi:lightbulb-outline",
        state_fn=lambda c: c.data.light_ring if c.data else None,
        on_cmd="light_ring_on",
        off_cmd="light_ring_off",
    ),
    BidetSwitchDescription(
        key="energy_saving",
        name="节能",
        icon="mdi:leaf",
        state_fn=lambda c: c.data.energy_saving if c.data else None,
        on_cmd="energy_saving_on",
        off_cmd="energy_saving_off",
    ),
    BidetSwitchDescription(
        key="reciprocating_clean",
        name="往复清洗",
        icon="mdi:swap-horizontal",
        state_fn=lambda c: c.data.reciprocating_clean if c.data else None,
        on_cmd="reciprocating_on",
        off_cmd="reciprocating_off",
    ),
    BidetSwitchDescription(
        key="hot_cold_massage",
        name="冷热按摩",
        icon="mdi:thermometer-variant",
        state_fn=lambda c: c.data.hot_cold_massage if c.data else None,
        on_cmd="hot_cold_on",
        off_cmd="hot_cold_off",
    ),
    BidetSwitchDescription(
        key="strong_weak_massage",
        name="强弱按摩",
        icon="mdi:pulse",
        state_fn=lambda c: c.data.strong_weak_massage if c.data else None,
        on_cmd="strong_weak_on",
        off_cmd="strong_weak_off",
    ),
    BidetSwitchDescription(
        key="voice",
        name="语音",
        icon="mdi:volume-high",
        state_fn=lambda c: c.voice_enabled,
        on_cmd="voice_on",
        off_cmd="voice_off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetSwitch(coordinator, desc) for desc in SWITCHES)


class BidetSwitch(BidetEntity, SwitchEntity):
    entity_description: BidetSwitchDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.state_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.async_send(self.entity_description.on_cmd)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.async_send(self.entity_description.off_cmd)
