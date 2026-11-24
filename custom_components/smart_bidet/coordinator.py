"""状态协调器：把 BLE 推送的数据分发给各实体。"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ble_client import BidetBLEClient, BidetError
from .const import CONF_ADDRESS, EVENT_NAMES, NAME, UI_REFRESH_INTERVAL
from .protocol import BidetEvent, BidetStatus, BidetVoice

_LOGGER = logging.getLogger(__name__)


class BidetCoordinator(DataUpdateCoordinator[BidetStatus]):
    """BLE 是推送式的，这里不做轮询，只做数据汇聚。"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=NAME,
            update_interval=None,
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self.client = BidetBLEClient(hass, self.address)
        self.last_event: str | None = None
        self.last_event_at: float | None = None
        self.voice: BidetVoice | None = None
        self._pending_status: BidetStatus | None = None
        self._unsub_flush: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------ 生命周期
    async def async_start(self) -> None:
        self.client.set_handlers(
            self._handle_status, self._handle_event, self._handle_voice, self._handle_availability
        )
        self._unsub_flush = async_track_time_interval(
            self.hass, self._flush_status, timedelta(seconds=UI_REFRESH_INTERVAL)
        )
        await self.client.async_start()

    async def async_shutdown(self) -> None:
        if self._unsub_flush is not None:
            self._unsub_flush()
        self._unsub_flush = None
        await self.client.async_stop()

    # ------------------------------------------------------------ 下行命令
    async def async_send(self, key: str, value: int | None = None) -> None:
        try:
            await self.client.async_send(key, value)
        except BidetError as err:
            raise HomeAssistantError(str(err)) from err

    # ------------------------------------------------------------ 上行回调
    @callback
    def _handle_status(self, status: BidetStatus) -> None:
        """只缓存最新一帧，由 1 秒一次的 flush 统一交付给实体。"""
        self._pending_status = status

    @callback
    def _flush_status(self, _now: object) -> None:
        status = self._pending_status
        if status is None:
            return
        self._pending_status = None
        self.async_set_updated_data(status)

    @callback
    def _handle_event(self, event: BidetEvent) -> None:
        self.last_event = EVENT_NAMES.get(event.code, f"未知事件 {event.code}")
        self.last_event_at = time.time()
        _LOGGER.debug("收到事件 %s: %s", event.code, self.last_event)
        if self.data is not None:
            # 数据未变化，仅刷新监听者以更新"最近事件"
            self.async_update_listeners()

    @callback
    def _handle_voice(self, voice: BidetVoice) -> None:
        self.voice = voice
        if self.data is not None:
            self.async_update_listeners()

    @callback
    def _handle_availability(self, available: bool) -> None:
        """断链即可用性立即失效：不允许「已经断开却还能操作」。"""
        if available:
            _LOGGER.debug("%s: 链路恢复", self.address)
            if not self.last_update_success or self.data is not None:
                self.last_update_success = True
                if self.data is not None:
                    self.async_set_updated_data(self.data)
                else:
                    self.async_update_listeners()
        else:
            _LOGGER.debug("%s: 链路断开，实体立即置为不可用", self.address)
            self.async_set_update_error(BidetError("蓝牙连接不可用"))

    @property
    def voice_enabled(self) -> bool | None:
        return self.voice.enabled if self.voice is not None else None

    @property
    def volume_gear(self) -> int | None:
        return self.voice.volume_gear if self.voice is not None else None

    # ------------------------------------------------------------ 诊断
    def diagnostics_snapshot(self) -> dict[str, object]:
        return {
            "address": self.address,
            "connected": self.client._available,  # noqa: SLF001 - 仅用于诊断输出
            "handshake_ok": self.client._handshake_ok,  # noqa: SLF001
            "write_failures": self.client._write_failures,  # noqa: SLF001
            "status_raw": self.data.raw.hex() if self.data is not None else None,
            "last_event": self.last_event,
            "voice": None if self.voice is None else {
                "enabled": self.voice.enabled,
                "volume_gear": self.voice.volume_gear,
            },
        }
