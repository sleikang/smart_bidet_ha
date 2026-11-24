"""数值类实体（水压 / 风速 / 喷管位置 / 洗涤时间）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SPOUT_POSITION_CODES,
    WASH_TIME_MAX,
    WASH_TIME_MIN,
    WATER_PRESSURE_CODES,
    WIND_SPEED_CODES,
)
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetNumberDescription(NumberEntityDescription):
    """取值函数 + 离散档位命令表（或连续性命令）。"""

    value_fn: Callable[[BidetCoordinator], float | None]
    command_map: dict[float, str] | None = None
    value_command: str | None = None


NUMBERS: tuple[BidetNumberDescription, ...] = (
    BidetNumberDescription(
        key="water_pressure",
        name="水压",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=20,
        mode=NumberMode.SLIDER,
        value_fn=lambda c: 20 * c.data.water_pressure_gear if c.data else None,
        command_map={float(p): f"water_pressure_{p}" for p in WATER_PRESSURE_CODES},
    ),
    BidetNumberDescription(
        key="wind_speed",
        name="风速",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=25,
        mode=NumberMode.SLIDER,
        # 档位 15 表示关闭
        value_fn=lambda c: (
            None if c.data is None
            else 0 if c.data.wind_speed_gear in (0, 15)
            else (c.data.wind_speed_gear - 1) * 25
        ),
        command_map={float(p): f"wind_speed_{p}" for p in WIND_SPEED_CODES},
    ),
    BidetNumberDescription(
        key="spout_position",
        name="喷管位置",
        icon="mdi:arrow-left-right",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=25,
        mode=NumberMode.SLIDER,
        value_fn=lambda c: (
            None if c.data is None
            else 0 if c.data.spout_position_gear == 0
            else (c.data.spout_position_gear - 1) * 25
        ),
        command_map={float(p): f"spout_position_{p}" for p in SPOUT_POSITION_CODES},
    ),
    BidetNumberDescription(
        key="hip_wash_time",
        name="臀洗时间",
        icon="mdi:timer-outline",
        native_min_value=WASH_TIME_MIN,
        native_max_value=WASH_TIME_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda c: float(c.data.hip_wash_time) if c.data else None,
        value_command="hip_time_set",
    ),
    BidetNumberDescription(
        key="female_wash_time",
        name="妇洗时间",
        icon="mdi:timer-sand",
        native_min_value=WASH_TIME_MIN,
        native_max_value=WASH_TIME_MAX,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda c: float(c.data.female_wash_time) if c.data else None,
        value_command="female_time_set",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetNumber(coordinator, desc) for desc in NUMBERS)


class BidetNumber(BidetEntity, NumberEntity):
    entity_description: BidetNumberDescription

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        if desc.value_command is not None:
            await self.coordinator.async_send(desc.value_command, int(round(value)))
            return
        if desc.command_map:
            nearest = min(desc.command_map, key=lambda key: abs(key - value))
            await self.coordinator.async_send(desc.command_map[nearest])
            return
        raise ValueError("该数值实体没有配置下发命令")
