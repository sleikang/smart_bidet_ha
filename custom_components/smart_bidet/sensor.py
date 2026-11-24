"""传感器类实体。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_NAMES,
    ACTION_OPTIONS,
    COVER_STATE_NAMES,
    COVER_STATE_OPTIONS,
    DOMAIN,
)
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetSensorDescription(SensorEntityDescription):
    """取值函数直接吃 coordinator，便于读取事件/语音等非状态快照数据。"""

    value_fn: Callable[[BidetCoordinator], Any]
    attrs_fn: Callable[[BidetCoordinator], dict[str, Any]] | None = None


SENSORS: tuple[BidetSensorDescription, ...] = (
    BidetSensorDescription(
        key="action",
        name="工作状态",
        icon="mdi:toilet",
        device_class=SensorDeviceClass.ENUM,
        options=ACTION_OPTIONS,
        value_fn=lambda c: ACTION_NAMES.get(c.data.action) if c.data else None,
    ),
    BidetSensorDescription(
        key="hip_wash_time",
        name="臀洗设定时间",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.hip_wash_time if c.data else None,
    ),
    BidetSensorDescription(
        key="female_wash_time",
        name="妇洗设定时间",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.female_wash_time if c.data else None,
    ),
    BidetSensorDescription(
        key="elapsed_time",
        name="洗涤计时",
        icon="mdi:progress-clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.elapsed_time if c.data else None,
    ),
    BidetSensorDescription(
        key="wash_progress",
        name="洗涤进度",
        icon="mdi:progress-check",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.wash_progress if c.data else None,
    ),
    BidetSensorDescription(
        key="room_temperature",
        name="室温",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.room_temperature if c.data else None,
    ),
    BidetSensorDescription(
        key="sensing_distance",
        name="感距档位",
        icon="mdi:radar",
        value_fn=lambda c: c.data.sensing_distance_gear if c.data else None,
        attrs_fn=lambda c: (
            {}
            if c.data is None
            else {
                "percent": c.data.sensing_distance_mm,
                "no_module": c.data.sensing_distance_gear == 15,
            }
        ),
    ),
    BidetSensorDescription(
        key="cover_state",
        name="圈盖状态",
        icon="mdi:toilet",
        device_class=SensorDeviceClass.ENUM,
        options=COVER_STATE_OPTIONS,
        value_fn=lambda c: COVER_STATE_NAMES.get(c.data.cover_state) if c.data else None,
    ),
    BidetSensorDescription(
        key="last_event",
        name="最近事件",
        icon="mdi:message-text-outline",
        value_fn=lambda c: c.last_event,
        attrs_fn=lambda c: (
            {} if c.last_event_at is None else {"timestamp": c.last_event_at}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetSensor(coordinator, desc) for desc in SENSORS)


class BidetSensor(BidetEntity, SensorEntity):
    entity_description: BidetSensorDescription

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator) or None
