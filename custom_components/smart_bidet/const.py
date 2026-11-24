"""智慧云马桶（Intelligence bidet）常量与命令表。

命令表由微信小程序 `wxf105815db957545f` 的 `pages/mainInterface/index.js`
命令数组 + `settingInterfaceUartSend` 映射逆向而来，详见 docs/protocol.md。
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "smart_bidet"
NAME: Final = "智慧云马桶"
MANUFACTURER: Final = "Smart Bidet"
MODEL: Final = "Intelligence bidet"

# ---------------------------------------------------------------- 传输层
BLE_LOCAL_NAME: Final = "Intelligence bidet"
AT_PREFIX: Final = b"AT+UART="
BLE_HANDSHAKE: Final = b"AT+CMD=BLECONNECTOK#"
HANDSHAKE_OK: Final = b"AT+CMD=OK"
FRAME_MARK: Final = 0x23  # '#'
DEFAULT_CMD0: Final = 0x81

CONF_ADDRESS: Final = "address"

# UI/recorder 只按 1 秒聚合一次
UI_REFRESH_INTERVAL: Final = 1
# 单次写入的上限，卡住的写不能一直挂着
WRITE_TIMEOUT: Final = 5
RECONNECT_MIN_DELAY: Final = 1
RECONNECT_MAX_DELAY: Final = 60

# 时间设置范围（小程序 picker：1..3 分钟 + 0..59 秒）
WASH_TIME_MIN: Final = 60
WASH_TIME_MAX: Final = 239

# ---------------------------------------------------------------- 命令表
COMMANDS: dict[str, tuple[int, int]] = {
    # 状态查询
    "query_status": (DEFAULT_CMD0, 0xC8),
    # 开关量
    "auto_flush_on": (DEFAULT_CMD0, 0x18),
    "auto_flush_off": (DEFAULT_CMD0, 0x19),
    "energy_saving_on": (DEFAULT_CMD0, 0x16),
    "energy_saving_off": (DEFAULT_CMD0, 0x17),
    "auto_foam_on": (DEFAULT_CMD0, 0x88),
    "auto_foam_off": (DEFAULT_CMD0, 0x89),
    "light_ring_on": (DEFAULT_CMD0, 0x41),
    "light_ring_off": (DEFAULT_CMD0, 0x42),
    "light_ring_toggle": (DEFAULT_CMD0, 0x43),
    "night_light_toggle": (DEFAULT_CMD0, 0x49),
    # 清洗按摩
    "reciprocating_on": (DEFAULT_CMD0, 0x0A),
    "reciprocating_off": (DEFAULT_CMD0, 0x0B),
    "hot_cold_on": (DEFAULT_CMD0, 0x0C),
    "hot_cold_off": (DEFAULT_CMD0, 0x0D),
    "strong_weak_on": (DEFAULT_CMD0, 0x0E),
    "strong_weak_off": (DEFAULT_CMD0, 0x0F),
    # 一次性动作
    "hip_wash_on": (DEFAULT_CMD0, 0x08),
    "female_wash_on": (DEFAULT_CMD0, 0x09),
    "child_wash_on": (DEFAULT_CMD0, 0x07),
    "washing_stop": (DEFAULT_CMD0, 0x14),
    "drying_on": (DEFAULT_CMD0, 0x12),
    "drying_off": (DEFAULT_CMD0, 0x15),
    "flush": (DEFAULT_CMD0, 0x13),
    "foam_on": (DEFAULT_CMD0, 0x10),
    "foam_off": (DEFAULT_CMD0, 0x11),
    "lid_open": (DEFAULT_CMD0, 0x02),
    "lid_close": (DEFAULT_CMD0, 0x03),
    "ring_open": (DEFAULT_CMD0, 0x04),
    "ring_close": (DEFAULT_CMD0, 0x05),
    "nozzle_clean": (DEFAULT_CMD0, 0x06),
    "stop_all": (DEFAULT_CMD0, 0x7C),
    "power_on": (DEFAULT_CMD0, 0x2D),
    "power_off": (DEFAULT_CMD0, 0x2B),
    # 设置项
    "flush_before_drying": (DEFAULT_CMD0, 0x1B),
    "flush_after_leaving": (DEFAULT_CMD0, 0x1A),
    "auto_lid_flip": (DEFAULT_CMD0, 0x1E),
    "lid_only": (DEFAULT_CMD0, 0x1F),
    "auto_lid_on": (DEFAULT_CMD0, 0x1C),
    "auto_lid_off": (DEFAULT_CMD0, 0x1D),
    "reset_factory": (DEFAULT_CMD0, 0x28),
    # 时间设置：cmd1 直接就是秒数
    "hip_time_set": (0x79, 0x00),
    "female_time_set": (0x80, 0x00),
    # 语音（cmd0 = 0xA0）
    "voice_on": (0xA0, 0x01),
    "voice_off": (0xA0, 0x02),
}

# cmd1 承载"秒数"的命令
TIME_COMMANDS: Final = ("hip_time_set", "female_time_set")

WATER_TEMP_CODES: Final = {0: 0x68, 1: 0x63, 2: 0x64, 3: 0x65, 4: 0x66, 5: 0x67}
SEAT_TEMP_CODES: Final = {0: 0x54, 1: 0x4F, 2: 0x50, 3: 0x51, 4: 0x52, 5: 0x53}
WIND_TEMP_CODES: Final = {0: 0x5E, 1: 0x59, 2: 0x5A, 3: 0x5B, 4: 0x5C, 5: 0x5D}
FLUSH_LEVEL_CODES: Final = {1: 0x31, 2: 0x32, 3: 0x33, 4: 0x34, 5: 0x35}
WATER_PRESSURE_CODES: Final = {0: 0x72, 20: 0x6D, 40: 0x6E, 60: 0x6F, 80: 0x70, 100: 0x71}
SPOUT_POSITION_CODES: Final = {0: 0x77, 25: 0x78, 50: 0x79, 75: 0x7A, 100: 0x7B}
WIND_SPEED_CODES: Final = {0: 0x8E, 25: 0x8F, 50: 0x90, 75: 0x91, 100: 0x92}
VOLUME_CODES: Final = {0: 0x09, 1: 0x04, 2: 0x05, 3: 0x06, 4: 0x07, 5: 0x08}
# 感距（组 6 索引 15..20）：0 档复用「关自动翻盖」的 0x1D（小程序就这么发）
SENSING_DISTANCE_CODES: Final = {0: 0x1D, 1: 0x22, 2: 0x23, 3: 0x24, 4: 0x25, 5: 0x26}

for _gear, _code in WATER_TEMP_CODES.items():
    COMMANDS[f"water_temp_{_gear}"] = (DEFAULT_CMD0, _code)
for _gear, _code in SEAT_TEMP_CODES.items():
    COMMANDS[f"seat_temp_{_gear}"] = (DEFAULT_CMD0, _code)
for _gear, _code in WIND_TEMP_CODES.items():
    COMMANDS[f"wind_temp_{_gear}"] = (DEFAULT_CMD0, _code)
for _gear, _code in FLUSH_LEVEL_CODES.items():
    COMMANDS[f"flush_level_{_gear}"] = (DEFAULT_CMD0, _code)
for _percent, _code in WATER_PRESSURE_CODES.items():
    COMMANDS[f"water_pressure_{_percent}"] = (DEFAULT_CMD0, _code)
for _percent, _code in SPOUT_POSITION_CODES.items():
    COMMANDS[f"spout_position_{_percent}"] = (DEFAULT_CMD0, _code)
for _percent, _code in WIND_SPEED_CODES.items():
    COMMANDS[f"wind_speed_{_percent}"] = (DEFAULT_CMD0, _code)
for _gear, _code in VOLUME_CODES.items():
    COMMANDS[f"volume_{_gear}"] = (0xA0, _code)
for _gear, _code in SENSING_DISTANCE_CODES.items():
    COMMANDS[f"sensing_distance_{_gear}"] = (DEFAULT_CMD0, _code)

# ---------------------------------------------------------------- 展示用标签
ACTION_NAMES: Final = {
    0: "关机",
    1: "待机",
    2: "臀洗",
    3: "妇洗",
    4: "儿童洗",
    5: "烘干",
    6: "泡沫",
    7: "喷口清洗",
    8: "初始化",
    9: "关机",
}
ACTION_OPTIONS: Final = ["关机", "待机", "臀洗", "妇洗", "儿童洗", "烘干", "泡沫", "喷口清洗", "初始化"]

COVER_STATE_NAMES: Final = {
    0: "全关",
    1: "盖开·圈关",
    2: "盖开·圈开",
    3: "无圈盖手动款",
}
COVER_STATE_OPTIONS: Final = ["全关", "盖开·圈关", "盖开·圈开", "无圈盖手动款"]

EVENT_NAMES: Final = {
    7: "有入座，不执行",
    20: "烘干已打开",
    21: "冲水",
    22: "已停止",
    43: "未入座，不执行",
    91: "停止工作",
    92: "停止臀洗",
    93: "停止妇洗",
    105: "儿童模式已开启",
    106: "妇洗模式已开启",
    113: "臀洗模式已开启",
    200: "臀洗时间设置成功",
    201: "臀洗时间设置失败",
    202: "妇洗时间设置成功",
    203: "妇洗时间设置失败",
}

WATER_TEMP_LABELS: Final = {
    0: "关闭",
    1: "32 ℃",
    2: "34 ℃",
    3: "36 ℃",
    4: "38 ℃",
    5: "40 ℃",
}
SEAT_TEMP_LABELS: Final = dict(WATER_TEMP_LABELS)
WIND_TEMP_LABELS: Final = {
    0: "关闭",
    1: "40 ℃",
    2: "45 ℃",
    3: "50 ℃",
    4: "55 ℃",
    5: "60 ℃",
}
VOLUME_LABELS: Final = {0: "静音", 1: "1 档", 2: "2 档", 3: "3 档", 4: "4 档", 5: "5 档"}
FLUSH_LEVEL_LABELS: Final = {1: "1 档", 2: "2 档", 3: "3 档", 4: "4 档", 5: "5 档"}
SENSING_DISTANCE_LABELS: Final = {
    0: "关闭",
    1: "20%",
    2: "40%",
    3: "60%",
    4: "80%",
    5: "100%",
}

FLUSH_MODE_OPTIONS: Final = ["离座后冲水", "烘干前冲水"]
LID_MODE_OPTIONS: Final = ["翻圈翻盖", "仅翻盖"]
