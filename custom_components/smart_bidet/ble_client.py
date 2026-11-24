"""智慧云马桶的 BLE 连接封装（基于 bleak + HA bluetooth）。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    BLE_HANDSHAKE,
    COMMANDS,
    DOMAIN,
    RECONNECT_MAX_DELAY,
    RECONNECT_MIN_DELAY,
    WRITE_TIMEOUT,
)
from .protocol import BidetEvent, BidetStatus, BidetVoice, Frame, FrameAssembler, FrameKind, build_command_for

_LOGGER = logging.getLogger(__name__)


class BidetError(Exception):
    """集成内部错误基类。"""


class BidetNotConnected(BidetError):
    """当前没有可用链路。"""


StatusCallback = Callable[[BidetStatus], None]
EventCallback = Callable[[BidetEvent], None]
VoiceCallback = Callable[[BidetVoice], None]
AvailabilityCallback = Callable[[bool], None]


def _characteristics(client: BleakClient) -> list[tuple[BleakGATTCharacteristic, str]]:
    """兼容不同 bleak 版本，返回 (特征值, 所属服务 uuid)。"""
    out: list[tuple[BleakGATTCharacteristic, str]] = []
    services = getattr(client.services, "services", None)
    collection = list(services.values()) if isinstance(services, dict) else list(client.services)
    for service in collection:
        for char in getattr(service, "characteristics", []):
            out.append((char, getattr(service, "uuid", "")))
    return out


class BidetBLEClient:
    """维持一条常驻的 BLE 链路，负责收发与重连。"""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self._client: BleakClient | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._write_with_response = True
        self._assembler = FrameAssembler()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._closing = False
        self._connected_at = 0.0
        self._available = False
        self._wrote_anything = False
        self._handshake_ok = False
        self._write_failures = 0

        self._on_status: StatusCallback | None = None
        self._on_event: EventCallback | None = None
        self._on_voice: VoiceCallback | None = None
        self._on_availability: AvailabilityCallback | None = None

    # ------------------------------------------------------------ 生命周期
    @callback
    def set_handlers(
        self,
        on_status: StatusCallback,
        on_event: EventCallback,
        on_voice: VoiceCallback,
        on_availability: AvailabilityCallback,
    ) -> None:
        self._on_status = on_status
        self._on_event = on_event
        self._on_voice = on_voice
        self._on_availability = on_availability

    async def async_start(self) -> None:
        self._closing = False
        self._task = self.hass.async_create_background_task(
            self._run(), f"{DOMAIN} link {self.address}", eager_start=True
        )

    async def async_stop(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self._async_disconnect()

    # ------------------------------------------------------------ 连接主循环
    async def _run(self) -> None:
        delay = RECONNECT_MIN_DELAY
        while not self._closing:
            self._wrote_anything = False
            self._connected_at = 0.0
            try:
                await self._async_connect()
                await self._keepalive()
            except asyncio.CancelledError:
                raise
            except BidetError as err:
                _LOGGER.debug("%s: %s", self.address, err)
            except Exception as err:  # noqa: BLE001 - 任何异常都要进入重连
                _LOGGER.debug("%s: 未预期的错误 %s", self.address, err)
            finally:
                await self._async_disconnect()
            if self._closing:
                break
            # 连上了但一条命令都写不进去（写入通道被拒/超时），需要放大退避，
            # 否则会陷入「连上→写失败→断开」的快速循环
            lived = time.monotonic() - self._connected_at if self._connected_at else 0.0
            if self._wrote_anything or lived > 30:
                delay = RECONNECT_MIN_DELAY
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _async_connect(self) -> None:
        device, source = self._pick_device()
        if device is None:
            raise BidetError("蓝牙范围内找不到该设备")

        _LOGGER.debug("%s: 正在连接（接入来源 %s）", self.address, source)
        client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            self.address,
            max_attempts=1,
            use_services_cache=True,
            disconnected_callback=self._handle_disconnect,
        )

        try:
            write_char, notify_char = self._pick_characteristics(client)
            if write_char is None or notify_char is None:
                raise BidetError("没有找到可写/可订阅的特征值")
        except Exception:
            await self._safe_disconnect(client)
            raise

        props = write_char.properties or []
        _LOGGER.debug(
            "%s: 特征值 写=%s %s / 通知=%s %s",
            self.address, write_char.uuid, list(props), notify_char.uuid,
            list(getattr(notify_char, "properties", []) or []),
        )

        self._client = client
        self._write_char = write_char
        self._write_with_response = "write" in props and "write-without-response" not in props
        self._connected_at = time.monotonic()
        self._handshake_ok = False

        # 先订阅通知，避免握手回应在订阅完成前到达而丢失。
        try:
            await client.start_notify(notify_char, self._handle_notify)
        except Exception as err:
            await self._safe_disconnect(client)
            self._client = None
            self._write_char = None
            self._set_available(False)
            raise BidetError(f"订阅通知失败: {err}") from err

        # 小程序连接后发送一次握手，不周期发送额外状态查询帧。
        try:
            await self._write(BLE_HANDSHAKE, label="握手")
        except BidetError as err:
            _LOGGER.warning("%s: %s，链路可能需要重置", self.address, err)
            await self._safe_disconnect(client)
            self._client = None
            self._write_char = None
            self._set_available(False)
            raise

        self._set_available(True)
        _LOGGER.debug(
            "%s: 已连接（写 %s / 通知 %s / 写方式 %s / 来源 %s）",
            self.address, write_char.uuid, notify_char.uuid,
            "带响应" if self._write_with_response else "无响应", source,
        )

    def _pick_device(self) -> tuple[object | None, str]:
        """由 Home Assistant 选择该设备当前可用的蓝牙适配器。"""
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        source = (getattr(device, "details", None) or {}).get("source", "unknown") if device else "none"
        return device, str(source)

    async def _keepalive(self) -> None:
        """等待 BLE 实际断开；设备状态为推送式，不主动轮询或拆链。"""
        while not self._closing:
            client = self._client
            if client is None or not client.is_connected:
                raise BidetError("链路已断开")
            await asyncio.sleep(1)

    async def _async_disconnect(self) -> None:
        client = self._client
        self._client = None
        self._write_char = None
        if client is not None:
            await self._safe_disconnect(client)
        if self._available:
            self._set_available(False)

    @staticmethod
    async def _safe_disconnect(client: BleakClient) -> None:
        try:
            if client.is_connected:
                await client.disconnect()
        except (BleakError, TimeoutError, EOFError):
            pass

    @staticmethod
    def _pick_characteristics(
        client: BleakClient,
    ) -> tuple[BleakGATTCharacteristic | None, BleakGATTCharacteristic | None]:
        write_char: BleakGATTCharacteristic | None = None
        write_fallback: BleakGATTCharacteristic | None = None
        notify_char: BleakGATTCharacteristic | None = None
        indicate_char: BleakGATTCharacteristic | None = None

        for char, _service_uuid in _characteristics(client):
            props = char.properties or []
            if "write" in props and write_char is None:
                write_char = char
            elif "write-without-response" in props and write_fallback is None:
                write_fallback = char
            if "notify" in props and notify_char is None:
                notify_char = char
            elif "indicate" in props and indicate_char is None:
                indicate_char = char

        return write_char or write_fallback, notify_char or indicate_char

    # ------------------------------------------------------------ 收发
    @callback
    def _handle_notify(self, _sender: object, data: bytearray) -> None:
        for frame in self._assembler.feed(data):
            self._dispatch(frame)

    @callback
    def _dispatch(self, frame: Frame) -> None:
        if frame.kind is FrameKind.STATUS and frame.status is not None and self._on_status:
            self._on_status(frame.status)
        elif frame.kind is FrameKind.EVENT and frame.event is not None and self._on_event:
            self._on_event(frame.event)
        elif frame.kind is FrameKind.VOICE and frame.voice is not None and self._on_voice:
            self._on_voice(frame.voice)
        elif frame.kind is FrameKind.HANDSHAKE:
            self._handshake_ok = True
            _LOGGER.debug("%s: 握手完成", self.address)

    @callback
    def _handle_disconnect(self, _client: object) -> None:
        _LOGGER.debug("%s: BLE 连接已断开", self.address)
        self._set_available(False)

    @callback
    def _set_available(self, available: bool) -> None:
        if available == self._available:
            return
        self._available = available
        if self._on_availability:
            self._on_availability(available)

    async def async_send(self, key: str, value: int | None = None) -> None:
        """下发一条命令（命令名来自 const.COMMANDS）。"""
        if key not in COMMANDS:
            raise BidetError(f"未知命令 {key}")
        frame = build_command_for(key, COMMANDS, value)
        await self._write(frame)

    async def _write(self, frame: bytes, label: str = "") -> None:
        async with self._lock:
            client = self._client
            char = self._write_char
            if client is None or char is None or not client.is_connected:
                raise BidetNotConnected("马桶未连接")
            try:
                await asyncio.wait_for(
                    client.write_gatt_char(char, frame, response=self._write_with_response),
                    timeout=WRITE_TIMEOUT,
                )
            except TimeoutError as err:
                self._write_failures += 1
                raise BidetError(
                    f"{label or '写入'}超时（{WRITE_TIMEOUT}s 未得到响应）"
                ) from err
            except (BleakError, EOFError) as err:
                self._write_failures += 1
                raise BidetError(f"{label or '写入'}失败: {err}") from err
            self._wrote_anything = True
            _LOGGER.debug("%s: 已下发%s %s", self.address, f"（{label}）" if label else "", frame.hex())
