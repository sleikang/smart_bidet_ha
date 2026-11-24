"""自检脚本：用小程序原始命令数组校验插件生成的下行帧。

用法：
    python tools/verify_protocol.py [app-service.js 路径]

脚本会：
1. 从 app-service.js 里抽出 `pages/mainInterface/index.js` 的 10 组命令数组；
2. 校验 const.COMMANDS 里每条命令的 (cmd0, cmd1) 都确实出现在原始数组里；
3. 校验 build_command 生成的字节与小程序 `parseSendDataToBLE` 的拼帧逻辑一致；
4. 用构造的 16 字节状态块跑一遍解析，确认字段取值正确。
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = ROOT / "custom_components" / "smart_bidet"

# 造一个假包，让 protocol.py 里的相对导入生效（真正的 __init__ 依赖 Home Assistant）
_pkg = types.ModuleType("sb")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["sb"] = _pkg


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"sb.{name}", PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"sb.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
protocol = _load("protocol")

COMMANDS = const.COMMANDS
FrameAssembler = protocol.FrameAssembler
FrameKind = protocol.FrameKind
build_command = protocol.build_command
inverted_checksum = protocol.inverted_checksum
status_from_block = protocol.status_from_block

DEFAULT_JS = Path.home() / "Downloads" / "wxf105815db957545f_unpacked" / "app-service.js"


def extract_table(js: str) -> list[list[int]]:
    """取出定义 `i = [` 之后的所有 8 元素命令数组。"""
    start = js.index("i = [")
    end = js.index("];", start)
    block = js[start:end]
    rows = re.findall(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", block)
    return [list(map(int, row)) for row in rows]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JS
    rows = extract_table(path.read_text(encoding="utf-8", errors="ignore"))
    pairs = {(row[3], row[4]) for row in rows}
    print(f"原始命令数组：{len(rows)} 条，去重后 {len(pairs)} 种 (cmd0, cmd1)")

    missing = [
        (key, cmd) for key, cmd in COMMANDS.items() if cmd not in pairs
    ]
    if missing:
        print("!! 以下命令不在小程序命令表中：")
        for key, cmd in missing:
            print(f"   {key}: {cmd[0]:#04x} {cmd[1]:#04x}")
        return 1
    print(f"插件命令表：{len(COMMANDS)} 条，全部能在原始数组中找到")

    # 感距：组 6 索引 15..20，0 档与「关自动翻盖」共用 0x1D
    for gear, code in const.SENSING_DISTANCE_CODES.items():
        assert (0x81, code) in pairs, (gear, hex(code))
    print(
        "感距档码："
        + " ".join(f"{gear}档={code:#04x}" for gear, code in const.SENSING_DISTANCE_CODES.items())
    )

    # 拼帧逻辑：AT+UART= + 8 字节 payload + 0x01 + '#'
    frame = build_command(0x81, 0x08)
    head = bytes((0xA5, 0xFA, 0x00, 0x81, 0x08, 0x00))
    expected = b"AT+UART=" + head + bytes((inverted_checksum(head, 6), 0xFB)) + b"\x01#"
    assert frame == expected, (frame, expected)
    print(f"臀洗开帧：{frame.hex(' ').upper()}（{len(frame)} 字节）")

    # 时间设置：cmd1 就是秒数
    time_frame = build_command(0x79, 120)
    assert time_frame[12] == 120, time_frame.hex()
    print(f"臀洗时间 120s 帧：{time_frame.hex(' ').upper()}")

    # 状态帧解析：构造 d3..d13 全部为已知值的快照
    data = [0x00] * 11
    data[0] = 3          # d3 风速 3 档 -> 50%
    data[1] = 120        # d4 臀洗 120s
    data[2] = 90         # d5 妇洗 90s
    data[3] = 60         # d6 计时 60s
    data[4] = 0x82       # d7 灯圈开 + 水温 2 档
    data[5] = 0x31       # d8 座温 3 档 / 风温 1 档
    data[6] = 26         # d9 室温 26℃
    data[7] = 0x40       # d10 水压 4 档 / 喷管 0
    data[8] = 0x12       # d11 感距 1 档 / 水量 2 档
    data[9] = 0x24       # d12 臀洗 + 冲水
    data[10] = 0xE5      # d13 自动冲水/自动泡沫/冲水方式/翻圈/强弱/盖开圈开
    block = bytes((0xA5, 0xFA, 0x01, *data))
    block += bytes((inverted_checksum(block, 14), 0xFB))

    status = status_from_block(block)
    assert status is not None, "状态帧校验失败"
    print(
        "状态解析：",
        f"状态={status.action} 风速档={status.wind_speed_gear} 臀洗={status.hip_wash_time}s "
        f"妇洗={status.female_wash_time}s 计时={status.elapsed_time}s 进度={status.wash_progress}% "
        f"水温={status.water_temp_gear} 座温={status.seat_temp_gear} 风温={status.wind_temp_gear} "
        f"室温={status.room_temperature}℃ 水压={status.water_pressure_gear} 喷管={status.spout_position_gear} "
        f"感距={status.sensing_distance_mm}% 水量={status.water_level_gear} 冲水={status.flushing} "
        f"灯圈={status.light_ring} 圈盖={status.cover_state}",
    )
    assert status.action == 2 and status.wash_progress == 50 and status.room_temperature == 26
    assert status.flushing and status.auto_flush and status.auto_foam and status.cover_state == 1

    # 组帧：一次 notify 里同时塞状态帧与事件帧
    assembler = FrameAssembler()
    event_block = bytes((0xA5, 0xFA, 0x00, 0x03, 113, 0x00, 0x00, 0xFB))
    event_block = event_block[:6] + bytes((inverted_checksum(event_block, 6), 0xFB))
    voice_block = bytes((0xA5, 0xFA, 0x00, 0xA1, 0x01, 0x04, 0x00, 0xFB))
    voice_block = voice_block[:6] + bytes((sum(voice_block[:6]) & 0xFF, 0xFB))

    frames = assembler.feed(b"AT+UART=" + block + b"\x01#" + b"AT+UART=" + event_block + b"#" + b"AT+UART=" + voice_block + b"#")
    kinds = [frame.kind for frame in frames]
    assert kinds == [FrameKind.STATUS, FrameKind.EVENT, FrameKind.VOICE], kinds
    assert frames[1].event is not None and frames[1].event.code == 113
    assert frames[2].voice is not None and frames[2].voice.volume_gear == 4
    print("组帧/拆帧：状态 + 事件 + 语音 三帧全部解析成功")
    print("全部自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
