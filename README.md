# 智慧云马桶 Home Assistant 集成

从微信小程序 `wxf105815db957545f` 逆向而来的 Home Assistant 自定义集成，**完全走本地蓝牙**（`Intelligence bidet` 设备名），不经过厂商云端。

- 协议解析依据：`docs/protocol.md`
- 命令表逐条比对过小程序原始命令数组：`python tools/verify_protocol.py`
- 运行时依赖：`bleak` + `bleak-retry-connector`（HA 自带），`bluetooth` 集成必须可用

## 安装

1. 把 `custom_components/smart_bidet` 整个目录拷到 HA 配置目录：
   ```
   /config/custom_components/smart_bidet/
   ```
2. 重启 Home Assistant。
3. 「设置 → 设备与服务 → 添加集成」搜索 **智慧云马桶**。
   - 蓝牙范围内会自动发现 `Intelligence bidet`，点确认即可；
   - 也可以手动填马桶的蓝牙 MAC（`AA:BB:CC:DD:EE:FF`）。

> HACS 自定义仓库安装：把本仓库根目录（含 `custom_components/`、`hacs.json`）添加为 HACS 集成即可。

> 集成图标：`custom_components/smart_bidet/brand/icon.png`（256×256）与 `logo.png`（512×512）。HA 重启后生效，浏览器端若还是旧图标，强制刷一次页面（`Ctrl+F5`）。

## 连接方式

和小程序完全相同的链路流程：

1. 扫描按名字 `Intelligence bidet` 过滤设备；
2. 连接后遍历主服务，取 `write` 特征值作下行、`notify/indicate` 特征值作上行（UUID 不写死）；
3. 与小程序顺序一致：**先发一次握手 `AT+CMD=BLECONNECTOK#`，再订阅通知**；
4. 之后**不再有任何周期写入**。源码里没有心跳、没有轮询（命令表组 0 的状态查询在页面代码里 0 次调用），链路靠设备自己推送维持；断了就 1 秒后重连（退避上限 60 秒），不追求无限保活。单次写超时 5 秒。
5. **断链即刻不可用**：连接一断实体立刻变 `unavailable`，不会出现「提示未连接却还能操作」的错位；链路恢复后自动重新可用并刷新状态。
6. 固件推送本身是 100~300ms 一帧，集成只按 1 秒把最新一帧交付给实体（`UI_REFRESH_INTERVAL`），避免日志、recorder 和前端被高频刷新拖垮；事件帧（如「臀洗开启」）仍即时投递。

## 实体清单（对照小程序功能）

| 小程序功能 | 实体 | 说明 |
| --- | --- | --- |
| 工作状态 | `sensor.工作状态` | 关机/待机/臀洗/妇洗/儿童洗/烘干/泡沫/喷口清洗/初始化 |
| 进度圆环 | `sensor.洗涤进度`、`sensor.洗涤计时` | 剩余/已用时间由状态帧 d6 推算 |
| 室温显示 | `sensor.室温` | 0xFF 时另有「室温传感器故障」二进制传感器报警 |
| 温度档位 | `select.水温`、`select.座温`、`select.风温` | 关闭 / 32~40 ℃ / 40~60 ℃ |
| 冲水量 1~5 档 | `select.冲水量` | |
| 感距 0~100% | `select.感距` | 关闭 / 20 / 40 / 60 / 80 / 100%（组 6 索引 15~20；0 档与小程序一样复用 `0x81/0x1D` 关自动翻盖） |
| 冲水方式 | `select.冲水方式` | 离座后冲水 / 烘干前冲水 |
| 自动翻圈翻盖模式 | `select.翻盖模式` | 翻圈翻盖 / 仅翻盖 |
| 音量 0~5 档 | `select.音量` | 0 = 静音，数据来自语音状态帧 |
| 自动冲水 | `switch.自动冲水` | |
| 自动泡沫 | `switch.自动泡沫` | |
| 自动翻盖 | `switch.自动翻盖` | 状态由「感距档 1~14」推导（小程序无独立回读位） |
| 灯圈 / 夜灯 | `switch.灯圈`、`button.夜灯切换` | |
| 节能 | `switch.节能` | |
| 往复清洗 | `switch.往复清洗` | |
| 冷热 / 强弱按摩 | `switch.冷热按摩`、`switch.强弱按摩` | |
| 语音开关 | `switch.语音` | |
| 水压滑条 | `number.水压` | 0~100%，步长 20 |
| 风速滑条 | `number.风速` | 0~100%，步长 25 |
| 喷管位置滑条 | `number.喷管位置` | 0~100%，步长 25 |
| 臀洗/妇洗时间 | `number.臀洗时间`、`number.妇洗时间` | 60~239 秒（小程序是 1~3 分 + 0~59 秒） |
| 臀洗 / 妇洗 / 儿童洗 / 停止洗涤 | `button.*` | |
| 烘干 / 停止烘干 | `button.*` | |
| 冲水 / 泡沫 / 停止泡沫 | `button.*` | |
| 翻盖 / 合盖 / 翻圈 / 落圈 | `button.*` | |
| 喷口清洗 | `button.喷口清洗` | |
| 全部停止 | `button.全部停止` | `0x81/0x7C` |
| 开机 / 关机 | `button.开机`、`button.关机` | 小程序里的确认弹窗在这里由按钮直接下发 |
| 恢复出厂设置 | `button.恢复出厂设置` | 配置类实体，**慎点** |
| 圈盖状态 | `sensor.圈盖状态` | 全关 / 盖开·圈关 / 盖开·圈开 / 无圈盖手动款 |
| 冲水中 | `binary_sensor.正在冲水` | |
| 事件提示（未入座、设置成功等） | `sensor.最近事件` | 对应小程序 toast |

## 已知限制

1. **单人单链路**：马桶同一时间只接受一个 BLE 连接，HA 连着时微信小程序连不上，反之亦然。小程序的策略是切后台 4 秒后自动断开，HA 这边是常驻连接。
2. **感距写法的坑**：小程序里 0% 走的是「关自动翻盖」同一个码 `0x81/0x1D`（关闭感距等于关掉人来自动翻盖），20%~100% 依次是 `0x22/0x23/0x24/0x25/0x26`。插件按小程序的映射原样实现，另外保留只读的 `sensor.感距档位`（附 `percent` / `no_module` 属性）；感距档 15 表示没有感距模块，此时 `select.感距` 会显示 `unknown`。
3. **没有真机回归**：本集成是按源码协议实现的，帧格式、命令码、状态位都做了离线自检（`tools/verify_protocol.py`），但没见过实体设备。首次上机建议打开 HA 日志的 `debug`：
   ```yaml
   logger:
     default: info
     logs:
       custom_components.smart_bidet: debug
   ```
   日志会打印每一条上行帧的 hex，对不上时先看「设置 → 设备与服务 → 集成 → 智慧云马桶 → 下载诊断信息」，里面带原始状态帧。
4. 状态帧里没有「已入座」独立回读位，只能通过事件码 7/43 间接触发，因此没做「有人/无人」二进制传感器。
5. 语音的开关与音量是独立帧（`0xA1`），如果设备不上报，`switch.语音` / `select.音量` 会保持 `unknown`（不影响下发命令）。

## 目录结构

```
custom_components/smart_bidet/
├── __init__.py          # 入口，装载 6 个平台
├── manifest.json        # bluetooth 自动发现（local_name: Intelligence bidet）
├── const.py             # 命令表 / 档位标签 / 事件码
├── protocol.py          # 帧编解码、状态解析、流式组帧
├── ble_client.py        # 连接、特征值挑选、握手、重连、下发
├── coordinator.py       # 推送式数据汇聚 + 事件
├── entity.py            # 设备信息/唯一 ID 基类
├── switch.py select.py number.py button.py sensor.py binary_sensor.py
├── config_flow.py       # 蓝牙发现 + 手动 MAC
├── diagnostics.py
├── brand/               # 集成图标（icon.png 256 / logo.png 512）
└── strings.json translations/{zh-Hans,en}.json
docs/protocol.md         # 协议逆向文档
tools/verify_protocol.py # 离线自检
```

## 排错

| 现象 | 排查方向 |
| --- | --- |
| 添加集成时搜不到设备 | 确认 HA 主机蓝牙适配器可用、马桶在 2~5 米内；改用手动填 MAC |
| `xxx 秒没有收到状态数据` | 说明连上了但设备不推送，检查是否有其它手机的小程序占着连接 |
| 实体全部 `unknown` | 打开 debug 日志看是否收到 `AT+CMD=OK#`，没有则是握手/特征值选错 |
| 下发没反应 | 用「下载诊断信息」对比 `status_raw`，确认命令码是否被设备接受（部分固件只认小程序白名单） |
| 连上后约 6 秒就断、日志里 `error=133` | 固件的「自己 6 秒不发送就休眠断链」策略，`133` 是断链瞬间写特征值失败的连带报错。集成不做任何心跳写入，断了 1 秒后自动重连，实体在这一刻立即变 `unavailable`；要减少掉线应从信号看：关掉手机小程序/厂商 App（单连接设备）、缩短距离、换 USB 延长线避开干扰 |
| 单次写入卡住 | 写入用 5 秒超时封顶（`WRITE_TIMEOUT`），超时即判定失败并触发重连，不会一直挂着 |
| 数据一直在刷，但 30 秒后突然断开，日志 `Timeout waiting for BluetoothGATTWriteResponse ... after 30.0s` | 这是 **ESP32 蓝牙代理**的报文措辞，被杀掉的是写入通道（推送通道是好的）：固件没回应代理的写请求，代理 30 秒后主动掐连接。优先让 HA 用本机适配器直连马桶，或换位/断电重启代理 |
| 日志里 `Insufficient authorization (8)` | 设备 GATT 服务端拒绝写入（ATT 0x08 权限不足），反复重连几十次后固件容易进入这种僵死态：**给马桶断电（拔插头/关插座）10 秒再上电**，同时重启 ESP 代理清掉它缓存的连接与密钥 |
| `ESP_GATT_CONN_FAIL_ESTABLISH` 长时间连不上 | 设备此刻不可连接（休眠中或已被手机占着），不是适配器坏了；靠近设备、唤醒一次面板键，或手机断开后等它重新广播 |
