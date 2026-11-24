"""二进制传感器。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[BidetCoordinator], bool | None]


BINARY_SENSORS: tuple[BidetBinarySensorDescription, ...] = (
    BidetBinarySensorDescription(
        key="flushing",
        name="正在冲水",
        icon="mdi:water",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda c: c.data.flushing if c.data else None,
    ),
    BidetBinarySensorDescription(
        key="room_temp_fault",
        name="室温传感器故障",
        icon="mdi:thermometer-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        # 0xFF 表示故障；0xFF 时 room_temperature 也为 None，所以直接看原始字节
        value_fn=lambda c: (c.data.raw[9] == 0xFF) if c.data else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class BidetBinarySensor(BidetEntity, BinarySensorEntity):
    entity_description: BidetBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)
