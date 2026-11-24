"""按键类实体（一次性动作）。"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetButtonDescription(ButtonEntityDescription):
    """按键仅需一个命令名。"""

    command: str


BUTTONS: tuple[BidetButtonDescription, ...] = (
    BidetButtonDescription(key="hip_wash", name="臀洗", icon="mdi:water", command="hip_wash_on"),
    BidetButtonDescription(key="female_wash", name="妇洗", icon="mdi:water-outline", command="female_wash_on"),
    BidetButtonDescription(key="child_wash", name="儿童洗", icon="mdi:human-child", command="child_wash_on"),
    BidetButtonDescription(key="washing_stop", name="停止洗涤", icon="mdi:stop", command="washing_stop"),
    BidetButtonDescription(key="drying", name="烘干", icon="mdi:air-conditioner", command="drying_on"),
    BidetButtonDescription(key="drying_stop", name="停止烘干", icon="mdi:fan-off", command="drying_off"),
    BidetButtonDescription(key="flush", name="冲水", icon="mdi:water-pump", command="flush"),
    BidetButtonDescription(key="foam", name="泡沫", icon="mdi:chart-bubble", command="foam_on"),
    BidetButtonDescription(key="foam_stop", name="停止泡沫", icon="mdi:bubble-off", command="foam_off"),
    BidetButtonDescription(key="lid_open", name="翻盖", icon="mdi:arrow-up-bold", command="lid_open"),
    BidetButtonDescription(key="lid_close", name="合盖", icon="mdi:arrow-down-bold", command="lid_close"),
    BidetButtonDescription(key="ring_open", name="翻圈", icon="mdi:arrow-up", command="ring_open"),
    BidetButtonDescription(key="ring_close", name="落圈", icon="mdi:arrow-down", command="ring_close"),
    BidetButtonDescription(key="nozzle_clean", name="喷口清洗", icon="mdi:spray", command="nozzle_clean"),
    BidetButtonDescription(key="night_light_toggle", name="夜灯切换", icon="mdi:lightbulb", command="night_light_toggle"),
    BidetButtonDescription(key="stop_all", name="全部停止", icon="mdi:stop-circle", command="stop_all"),
    BidetButtonDescription(key="power_on", name="开机", icon="mdi:power-on", command="power_on"),
    BidetButtonDescription(key="power_off", name="关机", icon="mdi:power-off", command="power_off"),
    BidetButtonDescription(
        key="reset_factory",
        name="恢复出厂设置",
        icon="mdi:backup-restore",
        entity_category=EntityCategory.CONFIG,
        command="reset_factory",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetButton(coordinator, desc) for desc in BUTTONS)


class BidetButton(BidetEntity, ButtonEntity):
    entity_description: BidetButtonDescription

    async def async_press(self) -> None:
        await self.coordinator.async_send(self.entity_description.command)
