"""实体基类。"""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, NAME
from .coordinator import BidetCoordinator


class BidetEntity(CoordinatorEntity[BidetCoordinator]):
    """所有实体共享设备信息与可用性判断。"""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BidetCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"
        self._attr_name = description.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
