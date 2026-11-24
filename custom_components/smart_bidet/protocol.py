"""智慧云马桶 BLE-UART 帧编解码。

下行：``AT+UART=`` + 8 字节 payload + ``0x01`` + ``'#'``
payload：``A5 FA 00 cmd0 cmd1 00 chk FB``，``chk = ~sum(payload[0:6]) & 0xFF``

上行 payload 有三种：
* 状态快照 ``A5 FA 01 d0..d10 chk FB``（16 字节，``chk = ~sum(0:14)``）
* 事件应答   ``A5 FA 00 03 code 00 chk FB``（``chk = ~sum(0:6)``）
* 语音状态   ``A5 FA 00 A1 on lvl chk FB``（``chk = sum(0:6)``，普通求和）
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .const import AT_PREFIX, FRAME_MARK, HANDSHAKE_OK, TIME_COMMANDS

STATUS_BLOCK_LEN = 16
EVENT_BLOCK_LEN = 8


def inverted_checksum(data: bytes, count: int) -> int:
    """小程序里的 ``255 & ~sum(data[0:count])``。"""
    return (~sum(data[:count])) & 0xFF


def plain_checksum(data: bytes, count: int) -> int:
    """语音帧使用普通求和。"""
    return sum(data[:count]) & 0xFF


def build_command(cmd0: int, cmd1: int, data: int = 0) -> bytes:
    """构造一条下行帧（18 字节）。"""
    head = bytes((0xA5, 0xFA, 0x00, cmd0 & 0xFF, cmd1 & 0xFF, data & 0xFF))
    payload = head + bytes((inverted_checksum(head, 6), 0xFB))
    return AT_PREFIX + payload + b"\x01#"


def build_command_for(key: str, commands: dict[str, tuple[int, int]], value: int | None = None) -> bytes:
    """按命令名构造帧；时间设置类命令的 value 会写进 cmd1。"""
    cmd0, cmd1 = commands[key]
    if key in TIME_COMMANDS:
        if value is None:
            raise ValueError(f"{key} 需要秒数")
        return build_command(cmd0, int(value))
    return build_command(cmd0, cmd1)


# ---------------------------------------------------------------- 状态快照


@dataclass(slots=True)
class BidetStatus:
    """一帧状态快照的解析结果（字段含义见 docs/protocol.md）。"""

    raw: bytes
    wind_speed_gear: int = 0          # d3：1..5，15 = 关闭
    hip_wash_time: int = 0            # d4：秒
    female_wash_time: int = 0         # d5：秒
    elapsed_time: int = 0             # d6：秒（洗涤计时）
    water_temp_gear: int = 0          # d7 低 4 位
    light_ring: bool = False          # d7 bit7
    energy_saving: bool = False       # d7 bit5
    reciprocating_clean: bool = False # d7 bit4
    seat_temp_gear: int = 0           # d8 高 4 位
    wind_temp_gear: int = 0           # d8 低 4 位
    room_temperature: int | None = None  # d9，None = 传感器故障
    water_pressure_gear: int = 0      # d10 高 4 位
    spout_position_gear: int = 0      # d10 低 4 位
    water_level_gear: int = 0         # d11 低 4 位
    sensing_distance_gear: int = 0    # d11 高 4 位（15 = 无模块）
    action: int = 0                   # d12 高 4 位
    flushing: bool = False            # d12 bit2
    auto_flush: bool = False          # d13 bit7
    auto_foam: bool = False           # d13 bit6
    flush_before_drying: bool = False # d13 bit5
    auto_lid_flip: bool = False       # d13 bit4
    strong_weak_massage: bool = False # d13 bit3
    hot_cold_massage: bool = False    # d13 bit2
    cover_state: int = 0              # d13 低 2 位

    @property
    def sensing_distance_mm(self) -> int | None:
        """感距档换算成小程序显示的百分比（20 * 档）。"""
        if self.sensing_distance_gear == 15:
            return None
        return 20 * self.sensing_distance_gear

    @property
    def wash_total_time(self) -> int:
        """当前洗涤模式的设定时间。"""
        if self.action == 3:
            return self.female_wash_time
        return self.hip_wash_time

    @property
    def wash_progress(self) -> int | None:
        """洗涤进度（%），数据不足时返回 None。"""
        total = self.wash_total_time
        if not total:
            return None
        return max(0, min(100, round(self.elapsed_time * 100 / total)))


def status_from_block(block: bytes) -> BidetStatus | None:
    """校验并解析 16 字节状态块。"""
    if len(block) < STATUS_BLOCK_LEN:
        return None
    block = bytes(block[:STATUS_BLOCK_LEN])
    if block[0] != 0xA5 or block[1] != 0xFA or block[2] != 0x01:
        return None
    if block[14] != inverted_checksum(block, 14):
        return None

    d = block
    # 室温：bit7 为符号位，低 7 位为数值；0xFF 表示传感器故障
    room_temperature: int | None
    if d[9] == 0xFF:
        room_temperature = None
    elif d[9] & 0x80:
        room_temperature = -(d[9] & 0x7F)
    else:
        room_temperature = d[9] & 0x7F

    return BidetStatus(
        raw=block,
        wind_speed_gear=d[3] & 0x0F,
        hip_wash_time=d[4],
        female_wash_time=d[5],
        elapsed_time=d[6],
        water_temp_gear=d[7] & 0x0F,
        light_ring=bool(d[7] & 0x80),
        energy_saving=bool(d[7] & 0x20),
        reciprocating_clean=bool(d[7] & 0x10),
        seat_temp_gear=(d[8] >> 4) & 0x0F,
        wind_temp_gear=d[8] & 0x0F,
        room_temperature=room_temperature,
        water_pressure_gear=(d[10] >> 4) & 0x0F,
        spout_position_gear=d[10] & 0x0F,
        water_level_gear=d[11] & 0x0F,
        sensing_distance_gear=(d[11] >> 4) & 0x0F,
        action=(d[12] >> 4) & 0x0F,
        flushing=bool(d[12] & 0x04),
        auto_flush=bool(d[13] & 0x80),
        auto_foam=bool(d[13] & 0x40),
        flush_before_drying=bool(d[13] & 0x20),
        auto_lid_flip=bool(d[13] & 0x10),
        strong_weak_massage=bool(d[13] & 0x08),
        hot_cold_massage=bool(d[13] & 0x04),
        cover_state=d[13] & 0x03,
    )


# ---------------------------------------------------------------- 事件 / 语音


@dataclass(slots=True)
class BidetEvent:
    code: int
    sub: int = 0


@dataclass(slots=True)
class BidetVoice:
    enabled: bool
    volume_gear: int


def event_from_block(block: bytes) -> BidetEvent | None:
    """校验并解析 8 字节事件块。"""
    if len(block) < EVENT_BLOCK_LEN:
        return None
    block = bytes(block[:EVENT_BLOCK_LEN])
    if block[0] != 0xA5 or block[1] != 0xFA:
        return None
    if block[6] != inverted_checksum(block, 6):
        return None
    return BidetEvent(code=block[4], sub=block[5])


def voice_from_block(block: bytes) -> BidetVoice | None:
    """校验并解析 8 字节语音状态块（校验和是普通求和）。"""
    if len(block) < EVENT_BLOCK_LEN:
        return None
    block = bytes(block[:EVENT_BLOCK_LEN])
    if block[0] != 0xA5 or block[1] != 0xFA or block[3] != 0xA1:
        return None
    if block[6] != plain_checksum(block, 6):
        return None
    return BidetVoice(enabled=bool(block[4]), volume_gear=block[5] & 0x0F)


# ---------------------------------------------------------------- 流式组帧


class FrameKind(Enum):
    HANDSHAKE = "handshake"
    STATUS = "status"
    EVENT = "event"
    VOICE = "voice"


@dataclass(slots=True)
class Frame:
    kind: FrameKind
    status: BidetStatus | None = None
    event: BidetEvent | None = None
    voice: BidetVoice | None = None


class FrameAssembler:
    """把 BLE notify 的分片数据拼成完整帧（以 ``0x23`` 结尾）。"""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes | bytearray) -> list[Frame]:
        self._buffer += bytearray(data)
        frames: list[Frame] = []
        while True:
            index = self._buffer.find(FRAME_MARK)
            if index < 0:
                # 丢弃明显跑飞的数据，避免缓冲区无限增长
                if len(self._buffer) > 512:
                    del self._buffer[:-64]
                break
            chunk = bytes(self._buffer[:index])
            del self._buffer[: index + 1]
            frame = self._parse_chunk(chunk)
            if frame is not None:
                frames.append(frame)
        return frames

    @staticmethod
    def _parse_chunk(chunk: bytes) -> Frame | None:
        chunk = chunk.strip(b"\x00\r\n ")
        if not chunk:
            return None

        if chunk.startswith(b"AT+CMD="):
            if HANDSHAKE_OK in chunk:
                return Frame(FrameKind.HANDSHAKE)
            return None

        if chunk.startswith(AT_PREFIX):
            body = chunk[len(AT_PREFIX) :]
        else:
            start = chunk.find(b"\xa5\xfa")
            if start < 0:
                return None
            body = chunk[start:]

        # 上行帧尾部可能还带 0x01（与下行一致）
        body = body.rstrip(b"\x01")

        status = status_from_block(body)
        if status is not None:
            return Frame(FrameKind.STATUS, status=status)

        voice = voice_from_block(body)
        if voice is not None:
            return Frame(FrameKind.VOICE, voice=voice)

        event = event_from_block(body)
        if event is not None:
            return Frame(FrameKind.EVENT, event=event)

        return None
