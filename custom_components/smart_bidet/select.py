"""选择类实体（档位/模式）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLUSH_LEVEL_LABELS,
    FLUSH_MODE_OPTIONS,
    LID_MODE_OPTIONS,
    SEAT_TEMP_LABELS,
    SENSING_DISTANCE_LABELS,
    VOLUME_LABELS,
    WATER_TEMP_LABELS,
    WIND_TEMP_LABELS,
)
from .coordinator import BidetCoordinator
from .entity import BidetEntity


@dataclass(frozen=True, kw_only=True)
class BidetSelectDescription(SelectEntityDescription):
    """当前档位取值 + 选项到命令的映射。"""

    current_fn: Callable[[BidetCoordinator], str | None]
    option_commands: dict[str, str]


def _gear_select(
    key: str,
    name: str,
    icon: str,
    labels: dict[int, str],
    gear_fn: Callable[[BidetCoordinator], int | None],
    command_prefix: str,
) -> BidetSelectDescription:
    options = [labels[gear] for gear in sorted(labels)]
    return BidetSelectDescription(
        key=key,
        name=name,
        icon=icon,
        options=options,
        current_fn=lambda c: (
            labels.get(gear) if (gear := gear_fn(c)) in labels else None
        ),
        option_commands={labels[gear]: f"{command_prefix}{gear}" for gear in labels},
    )


SELECTS: tuple[BidetSelectDescription, ...] = (
    _gear_select(
        "water_temp",
        "水温",
        "mdi:water-thermometer",
        WATER_TEMP_LABELS,
        lambda c: c.data.water_temp_gear if c.data else None,
        "water_temp_",
    ),
    _gear_select(
        "seat_temp",
        "座温",
        "mdi:radiator",
        SEAT_TEMP_LABELS,
        lambda c: c.data.seat_temp_gear if c.data else None,
        "seat_temp_",
    ),
    _gear_select(
        "wind_temp",
        "风温",
        "mdi:hair-dryer",
        WIND_TEMP_LABELS,
        lambda c: c.data.wind_temp_gear if c.data else None,
        "wind_temp_",
    ),
    _gear_select(
        "flush_level",
        "冲水量",
        "mdi:water-pump",
        FLUSH_LEVEL_LABELS,
        lambda c: c.data.water_level_gear if c.data else None,
        "flush_level_",
    ),
    _gear_select(
        "volume",
        "音量",
        "mdi:volume-high",
        VOLUME_LABELS,
        lambda c: c.volume_gear,
        "volume_",
    ),
    _gear_select(
        "sensing_distance",
        "感距",
        "mdi:radar",
        SENSING_DISTANCE_LABELS,
        lambda c: c.data.sensing_distance_gear if c.data else None,
        "sensing_distance_",
    ),
    BidetSelectDescription(
        key="flush_mode",
        name="冲水方式",
        icon="mdi:water-sync",
        options=FLUSH_MODE_OPTIONS,
        current_fn=lambda c: (
            FLUSH_MODE_OPTIONS[1] if c.data and c.data.flush_before_drying
            else FLUSH_MODE_OPTIONS[0] if c.data else None
        ),
        option_commands={
            FLUSH_MODE_OPTIONS[0]: "flush_after_leaving",
            FLUSH_MODE_OPTIONS[1]: "flush_before_drying",
        },
    ),
    BidetSelectDescription(
        key="lid_mode",
        name="翻盖模式",
        icon="mdi:toilet",
        options=LID_MODE_OPTIONS,
        current_fn=lambda c: (
            LID_MODE_OPTIONS[0] if c.data and c.data.auto_lid_flip
            else LID_MODE_OPTIONS[1] if c.data else None
        ),
        option_commands={
            LID_MODE_OPTIONS[0]: "auto_lid_flip",
            LID_MODE_OPTIONS[1]: "lid_only",
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BidetCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BidetSelect(coordinator, desc) for desc in SELECTS)


class BidetSelect(BidetEntity, SelectEntity):
    entity_description: BidetSelectDescription

    @property
    def current_option(self) -> str | None:
        return self.entity_description.current_fn(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        command = self.entity_description.option_commands.get(option)
        if command is None:
            raise ValueError(f"不支持的选项 {option}")
        await self.coordinator.async_send(command)
