# 角色 A：NFC 调试 + 固件协议改造

> **负责人**: A
> **工期**: 预计 2-3 天
> **前置条件**: STM32 开发板、RC522 模块、Fire-Debugger 烧录器、Keil MDK 已装

---

## 一、任务总览

你有两个并行任务，按此优先级：

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 固件协议改造 | 改 `uart_comm.c`，让 STM32 和 PC 说同一种语言 |
| P1 | NFC 调试 | 调通 RC522，让板子能读到 S50 白卡 UID |
| P2 | 固件端事件上报 | 把触摸/NFC/姿态事件改成发二进制帧而不是文本日志 |

**策略**：NFC 调试会有等待时间（查数据手册、示波器抓波形），等待时切到协议改造，两边交替推进。

---

## 二、P0：固件协议改造

### 2.1 目标

把 `firmware/Drivers/Src/uart_comm.c` 的帧格式改成和 PC 端一致，使 PC 能下发指令控制板子。

### 2.2 改什么：帧格式对比

```
当前固件格式 (旧):
┌──────┬──────┬──────┬──────────┬──────┐
│ SYNC │ CMD  │ LEN  │ PAYLOAD  │ CRC  │
│ 0xA5 │  1B  │  1B  │  0~32B   │ XOR  │
└──────┴──────┴──────┴──────────┴──────┘

目标格式 (新, 与PC一致):
┌──────┬──────┬──────┬──────────────┬──────┬──────┐
│ SYNC │ SYNC │ LEN  │   PAYLOAD    │ CRC  │ END  │
│ 0xA5 │ 0x5A │  1B  │ CMD(1B)+Data │ CRC-8│ 0xEE │
└──────┴──────┴──────┴──────────────┴──────┴──────┘
```

**核心变化**：
1. 同步头从 1 字节变 2 字节 `A5 5A`
2. CMD 移到了 PAYLOAD 的第一个字节
3. CRC 从简单 XOR 变成 CRC-8（多项式 `0x07`）
4. 加了帧尾 `0xEE`

### 2.3 要改的函数

**文件**：`firmware/Drivers/Src/uart_comm.c` 和 `firmware/Drivers/Inc/uart_comm.h`

#### 改法 1：`calc_crc()` 改为 CRC-8

```c
// 旧：简单 XOR
static uint8_t calc_crc(uint8_t cmd, uint8_t len, const uint8_t *payload) {
    uint8_t crc = cmd ^ len;
    for (uint8_t i = 0; i < len; i++) crc ^= payload[i];
    return crc;
}

// 新：CRC-8 (多项式 0x07)
static uint8_t calc_crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80)
                crc = (crc << 1) ^ 0x07;
            else
                crc <<= 1;
        }
    }
    return crc;
}
```

#### 改法 2：`UART_SendPacket()` 改为新格式

```c
// 新格式: [A5][5A][LEN][CMD][PAYLOAD...][CRC8][EE]
void UART_SendPacket(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    uint8_t buf[38];  // 2(SYNC) + 1(LEN) + 1(CMD) + 32(MAX) + 1(CRC) + 1(END)
    buf[0] = 0xA5;   // SYNC0
    buf[1] = 0x5A;   // SYNC1
    buf[2] = 1 + len; // LEN = CMD + payload
    buf[3] = cmd;     // CMD
    if (len > 0 && payload) memcpy(buf + 4, payload, len);
    uint8_t body_len = 1 + len;  // CMD + payload
    buf[4 + len] = calc_crc8(buf + 3, body_len);  // CRC over [CMD+PAYLOAD]
    buf[5 + len] = 0xEE;  // END
    HAL_UART_Transmit(&huart1, buf, 6 + len, 100);
}
```

#### 改法 3：`UART_ParseFrames()` 改为新格式

状态机改成：`WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_CRC → GET_END`

```c
void UART_ParseFrames(void) {
    static enum { WAIT_SYNC0, WAIT_SYNC1, GET_LEN, GET_BODY, GET_CRC, GET_END } state = WAIT_SYNC0;
    static uint8_t pkt_len, pkt_idx;
    static uint8_t pkt_buf[34];  // 1(CMD) + 32(MAX payload) + 1(CRC)

    uint8_t b;
    while (ring_get(&b)) {
        switch (state) {
        case WAIT_SYNC0:
            if (b == 0xA5) state = WAIT_SYNC1;
            break;
        case WAIT_SYNC1:
            state = (b == 0x5A) ? GET_LEN : WAIT_SYNC0;
            break;
        case GET_LEN:
            pkt_len = (b > 33) ? 0 : b;  // max 1+32+1
            pkt_idx = 0;
            state = (pkt_len > 0) ? GET_BODY : WAIT_SYNC0;
            break;
        case GET_BODY:
            pkt_buf[pkt_idx++] = b;
            if (pkt_idx >= pkt_len) state = GET_CRC;  // CRC is last byte of body
            break;
        case GET_CRC:
            // b is actually END byte
            if (b == 0xEE) {
                uint8_t data_len = pkt_len - 1;  // exclude CRC byte
                uint8_t crc_expected = calc_crc8(pkt_buf, data_len);
                if (pkt_buf[data_len] == crc_expected) {
                    uint8_t cmd = pkt_buf[0];
                    if (cmd_callback) cmd_callback(cmd, pkt_buf + 1, data_len - 1);
                }
            }
            state = WAIT_SYNC0;
            break;
        default:
            state = WAIT_SYNC0;
            break;
        }
    }
}
```

#### 改法 4：头文件宏定义更新

```c
// uart_comm.h 中更新：
#define UART_SYNC0_BYTE  0xA5
#define UART_SYNC1_BYTE  0x5A
#define UART_END_BYTE    0xEE
#define UART_MAX_PAYLOAD 32

// 命令码 (PC → MCU):
#define UART_CMD_SET_EXPR  0x01   // payload: [emo_id:1B]
#define UART_CMD_SET_RGB   0x02   // payload: [R:1B][G:1B][B:1B]
#define UART_CMD_QUERY     0x03   // 查询传感器，无 payload
#define UART_CMD_HEARTBEAT 0x04   // 心跳，payload: [seq:1B]

// 事件码 (MCU → PC):
#define UART_EVT_TOUCH     0x10   // payload: [side:1B][type:1B]
#define UART_EVT_NFC       0x11   // payload: [uid_len:1B][uid:N]
#define UART_EVT_POSE      0x12   // payload: [state:1B]
#define UART_EVT_ACK       0x05   // ACK, payload: [ack_cmd:1B][status:1B]
```

### 2.4 验证方法

1. 编译烧录后，SSCOM 连接 COM6
2. **PC 下发测试**：在 SSCOM 中发送 HEX：`A5 5A 01 01 00 07 EE`
   - 这表示：设置表情=NORMAL(0x00)
   - 如果板子 LCD 表情变化 → 协议通了 ✅
3. **MCU 上发测试**：在固件 `main()` 初始化后加一行 `UART_SendPacket(0x10, (uint8_t[]){0x00,0x01}, 2);`
   - SSCOM 应收到的 HEX：`A5 5A 03 10 00 01 XX EE`
   - 其中 XX 是 CRC-8 值

---

## 三、P1：NFC 调试

### 3.1 目标

让 MFRC-522 通过 SPI1 读到 S50 白卡的 4 字节 UID。

### 3.2 硬件接线确认

| RC522 引脚 | STM32 引脚 | 说明 |
|------------|-----------|------|
| SDA (CS) | PA4 | SPI1 片选 |
| SCK | PA5 | SPI1 时钟 |
| MOSI | PA7 | SPI1 主出从入 |
| MISO | PA6 | SPI1 主入从出 |
| RST | PA3 | 复位脚 |
| 3.3V | 3.3V | 电源 |
| GND | GND | 地 |

### 3.3 调试步骤

**Step 1: 确认 SPI 时钟**
- 用示波器/逻辑分析仪抓 PA5 (SCK)，确认有 9MHz 时钟
- 没有时钟 → 检查 CubeMX SPI1 配置和 `MX_SPI1_Init()` 调用

**Step 2: 确认 RC522 复位**
```c
// 手动复位 RC522
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
HAL_Delay(10);  // 这里的 HAL_Delay 是初始化阶段，可以接受
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
HAL_Delay(50);
```

**Step 3: 读 VersionReg (0x37)**
RC522 的 VersionReg 应该返回 `0x92`（克隆片可能 `0x12`）。
如果读回来是 `0x00` 或 `0xFF` → SPI 通信有问题（接线、时序、模式）。

**Step 4: 寻卡**
调用 `RC522_Request()` / `RC522_Anticoll()` → 拿到 4 字节 UID。

### 3.4 现有代码位置

- 驱动：`firmware/Drivers/Src/rc522_spi.c`、`firmware/Drivers/Inc/rc522_spi.h`
- 测试入口：`main_fsm.c` 中已有 NFC 轮询代码，每 50ms 调用 `RC522_CheckCard()`
- 调试日志：`main_fsm.c` 每秒打印一次 `[NFC DBG] poll: card=X`

### 3.5 常见问题

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| VersionReg 返回 0x00 | SPI 没通 | 查 PA4 片选是否拉低、SCK/MOSI 波形 |
| VersionReg 返回 0xFF | MISO 浮空 | 查接线、查 GPIO 模式 |
| 寻卡无响应 | 天线未调谐 | RC522 天线匹配电路需要调整，先换一张卡试试 |
| 寻卡偶尔成功 | 电源不稳 | RC522 峰值电流大，3.3V 要能提供 >150mA |

---

## 四、P2：固件端事件上报

### 4.1 目标

把 `main_fsm.c` 中的 `UART_Printf()` 调试日志替换成 `UART_SendEvent()` 二进制事件帧。

### 4.2 具体改动

**文件**：`firmware/App/main_fsm.c`

```c
// 旧：文本日志
UART_Printf("[TOUCH] %s %s\r\n", side_names[touch.side], touch_evt_names[touch.event]);

// 新：二进制事件帧
uint8_t touch_payload[2] = { touch.side, touch.event };
UART_SendEvent(UART_EVT_TOUCH, touch_payload, 2);
```

```c
// 旧：
UART_Printf("[NFC] Card UID: %02X%02X%02X%02X\r\n", ...);

// 新：
UART_SendEvent(UART_EVT_NFC, card_uid, uid_len);
```

```c
// 旧：
UART_Printf("[POSE] FALL\r\n");

// 新：
UART_SendEvent(UART_EVT_POSE, (uint8_t[]){0x01}, 1);  // 0x00=稳定, 0x01=倾倒, 0x02=摇晃
```

**保留文本输出**：`UART_Printf("[FSM] %s -> %s\r\n", ...)` 等调试信息可以保留，用 `#ifdef DEBUG` 包裹，不影响二进制帧通信。

---

## 五、命令响应（PC 指令 → STM32 执行）

当收到 PC 下发的指令时，需要执行并回复 ACK。

### 5.1 在回调函数中添加指令处理

```c
// 在 main.c 或 main_fsm.c 的 CmdCallback 中：
void OnPcCommand(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    switch (cmd) {
    case UART_CMD_SET_EXPR:  // 0x01
        if (len >= 1) {
            Expression_Set((Expression)payload[0]);
            UART_SendPacket(UART_CMD_HEARTBEAT, (uint8_t[]){0x01, 0x00}, 2);  // ACK
        }
        break;
    case UART_CMD_SET_RGB:   // 0x02
        if (len >= 3) {
            RGB_SetColor(payload[0], payload[1], payload[2]);
            UART_SendPacket(UART_CMD_HEARTBEAT, (uint8_t[]){0x02, 0x00}, 2);
        }
        break;
    case UART_CMD_QUERY:     // 0x03
        // 上报当前状态
        break;
    case UART_CMD_HEARTBEAT: // 0x04
        UART_SendPacket(UART_CMD_HEARTBEAT, (uint8_t[]){0x04, 0x00}, 2);  // pong
        break;
    }
}
```

---

## 六、接口规范 — 与 B 的联调约定

### 6.1 协议文档（双方共用）

**PC 端对应文件**：`pc_backend/comm/protocol.py`
**固件端对应文件**：`firmware/Drivers/Src/uart_comm.c`

双方必须保持以下定义完全一致：

```
帧格式:     [A5][5A][LEN][CMD+PAYLOAD][CRC-8][EE]
CRC-8 多项式: 0x07 (MSB first)
最大 PAYLOAD:  32 字节 (含 CMD = 33 字节 body)
```

### 6.2 命令码对照表

| 值 | 方向 | 含义 | Payload |
|----|------|------|---------|
| 0x01 | PC→MCU | 设置表情 | [emo_id:1B] |
| 0x02 | PC→MCU | 设置RGB灯 | [R:1B][G:1B][B:1B] |
| 0x03 | PC→MCU | 查询状态 | 无 |
| 0x04 | PC→MCU | 心跳 | [seq:1B] |
| 0x05 | MCU→PC | ACK | [ack_cmd:1B][status:1B] |
| 0x10 | MCU→PC | 触摸事件 | [side:1B][type:1B] |
| 0x11 | MCU→PC | NFC刷卡 | [uid_len:1B][uid:N] |
| 0x12 | MCU→PC | 姿态事件 | [state:1B] |

### 6.3 表情 ID 对照

| ID | 枚举名 | 含义 |
|----|--------|------|
| 0 | NORMAL | 普通/默认 |
| 1 | HAPPY | 开心 |
| 2 | FOCUS | 专注 |
| 3 | ANGRY | 生气 |
| 4 | SLEEP | 休眠 |
| 5 | SURPRISE | 惊讶 |
| 6 | SAD | 难过 |
| 7 | LOVE | 爱心 |

### 6.4 联调流程

1. **A 先自测**：固件端用 UART_SendEvent 发测试帧，SSCOM 确认 HEX 格式正确
2. **B 先自测**：PC 端用 SSCOM 虚拟串口发测试帧，确认解析正确
3. **联调**：板子插 USB，B 运行 `python main.py`，A 触发触摸事件，B 的终端应打印收到的事件

---

## 七、完成标准

- [ ] `uart_comm.c` 帧格式改为新协议，编译 0 Error 0 Warning
- [ ] PC 通过 SSCOM 发送 `A5 5A 01 01 00 XX EE`，板子 LCD 切到 NORMAL 表情
- [ ] 固件端触摸事件以二进制帧发出，SSCOM 能收到正确的 HEX
- [ ] NFC 读到至少一张 S50 白卡的 4 字节 UID（串口打印即可）
- [ ] PC 指令 SET_EXPR / SET_RGB 在板子上正确响应
- [ ] 代码提交到 GitHub 自己的 feature 分支

---

## 八、参考文件

| 文件 | 用途 |
|------|------|
| `pc_backend/comm/protocol.py` | PC 端协议定义（帧格式、CMD枚举、CRC-8） |
| `firmware/Drivers/Src/uart_comm.c` | 你主要改的文件 |
| `firmware/Drivers/Inc/uart_comm.h` | 你主要改的头文件 |
| `firmware/App/main_fsm.c` | FSM 中改事件上报 |
| `firmware/Drivers/Src/rc522_spi.c` | NFC 驱动 |
| `开发文档/Project_Brief.md` | 项目总规范 |
