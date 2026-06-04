# 角色 A：NFC 调试 + 固件协议改造

> **负责人**: A
> **工期**: 预计 2-3 天
> **前置条件**: STM32 开发板、RC522 模块、Fire-Debugger 烧录器、Keil MDK 已装

---

## 一、任务总览

任务按**先后顺序**执行（先调通 NFC，再做协议改造）：

| 阶段 | 优先级 | 任务 | 说明 |
|------|--------|------|------|
| 第一阶段 | P0 | NFC 调试 | 调通 RC522，让板子能读到 S50 白卡 UID |
| 第二阶段 | P1 | AI 审查协议方案 | NFC 调通后，用 AI 模型审查协议改造计划，提出优化建议 |
| 第三阶段 | P2 | 固件协议改造 | 根据 AI 审查后的方案，改 `uart_comm.c` |
| 第四阶段 | P3 | 固件端事件上报 | 把触摸/NFC/姿态事件改成发二进制帧 |

---

## 二、第一阶段：NFC 调试（P0 — 先做这个）

### 2.1 目标

让 MFRC-522 通过 SPI1 读到 S50 白卡的 4 字节 UID。

### 2.2 硬件接线确认

| RC522 引脚 | STM32 引脚 | 说明 |
|------------|-----------|------|
| SDA (CS) | PA4 | SPI1 片选 |
| SCK | PA5 | SPI1 时钟 |
| MOSI | PA7 | SPI1 主出从入 |
| MISO | PA6 | SPI1 主入从出 |
| RST | PA3 | 复位脚 |
| 3.3V | 3.3V | 电源 |
| GND | GND | 地 |

> 接线由 C 角色负责。如果线还没接好，先催 C 接线。

### 2.3 调试步骤

**Step 1: 确认 SPI 时钟**
- 用示波器/逻辑分析仪抓 PA5 (SCK)，确认有 9MHz 时钟
- 没有时钟 → 检查 CubeMX SPI1 配置和 `MX_SPI1_Init()` 调用

**Step 2: 确认 RC522 复位**
```c
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
HAL_Delay(10);
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
HAL_Delay(50);
```

**Step 3: 读 VersionReg (0x37)**
RC522 的 VersionReg 应该返回 `0x92`（克隆片可能 `0x12`）。
读到 `0x00` 或 `0xFF` → SPI 通信有问题。

**Step 4: 寻卡 + 读 UID**
调用 `RC522_Request()` / `RC522_Anticoll()` → 拿到 4 字节 UID。

### 2.4 现有代码位置

- 驱动：`firmware/Drivers/Src/rc522_spi.c`、`firmware/Drivers/Inc/rc522_spi.h`
- 测试入口：`main_fsm.c` 中已有 NFC 轮询代码，每 50ms 调用 `RC522_CheckCard()`
- 调试日志：`main_fsm.c` 每秒打印一次 `[NFC DBG] poll: card=X`

### 2.5 常见问题

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| VersionReg 返回 0x00 | SPI 没通 | 查 PA4 片选是否拉低、SCK/MOSI 波形 |
| VersionReg 返回 0xFF | MISO 浮空 | 查接线、查 GPIO 模式 |
| 寻卡无响应 | 天线未调谐 | 先换一张卡试试 |
| 寻卡偶尔成功 | 电源不稳 | RC522 峰值电流大，3.3V 要 >150mA |

### 2.6 NFC 完成的标志

- [ ] SSCOM 串口打印 `[NFC] Card UID: XXXXXXXXX` 且 UID 正确
- [ ] 同一张卡多次读取 UID 一致
- [ ] 能区分"有卡"和"无卡"状态

---

## 三、第二阶段：AI 审查协议方案（P1）

> **触发条件**：NFC 调通后立即执行。用 AI 模型做方案审查，不要自己闷头改代码。

### 3.1 做什么

将下面的协议改造计划投喂给 AI 模型（如 Claude、ChatGPT 等），让它审查并提出改进建议：

1. **投喂内容**：本文档第四节"固件协议改造方案"的全部内容
2. **追加问题**：
   - "这个方案有没有边界情况遗漏？"
   - "CRC-8 多项式选 0x07 是否合适？有没有更好的选择？"
   - "帧格式有没有冗余或可优化的地方？"
   - "状态机解析逻辑有没有潜在的死锁或丢帧风险？"
   - "错误处理是否完备？"
3. **记录 AI 的建议**：把 AI 的回复保存下来
4. **采纳合理建议**：把 AI 建议中合理的部分整合进方案，标记修改了哪些地方

### 3.2 输出

一份简短的审查记录（写到开发日志或直接发群里）：

```
## 协议方案 AI 审查记录

### 审查工具：Claude / ChatGPT / ...

### AI 建议汇总
1. xxx → 采纳/不采纳，原因：...
2. xxx → 采纳/不采纳，原因：...

### 方案修改
- 修改前：xxx
- 修改后：xxx
```

### 3.3 为什么先审查再动手

- 协议一旦定了，PC 端和固件端都要跟着走，返工成本高
- AI 可能发现你没考虑到的边界情况
- 这是学习"AI 辅助开发"的一个好练习

---

## 四、第三阶段：固件协议改造（P2）

> 以下方案仅供参考基线，**实际实施以第二阶段 AI 审查后修正的版本为准**。

### 4.1 目标

把 `firmware/Drivers/Src/uart_comm.c` 的帧格式改成和 PC 端一致，使 PC 能下发指令控制板子。

### 4.2 改什么：帧格式对比

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

### 4.3 要改的函数

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
    uint8_t buf[38];
    buf[0] = 0xA5;   // SYNC0
    buf[1] = 0x5A;   // SYNC1
    buf[2] = 1 + len; // LEN = CMD + payload
    buf[3] = cmd;     // CMD
    if (len > 0 && payload) memcpy(buf + 4, payload, len);
    uint8_t body_len = 1 + len;
    buf[4 + len] = calc_crc8(buf + 3, body_len);
    buf[5 + len] = 0xEE;  // END
    HAL_UART_Transmit(&huart1, buf, 6 + len, 100);
}
```

#### 改法 3：`UART_ParseFrames()` 改为新格式

状态机改成：`WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_END`

```c
void UART_ParseFrames(void) {
    static enum { WAIT_SYNC0, WAIT_SYNC1, GET_LEN, GET_BODY, GET_END } state = WAIT_SYNC0;
    static uint8_t pkt_len, pkt_idx;
    static uint8_t pkt_buf[34];

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
            pkt_len = (b > 33) ? 0 : b;
            pkt_idx = 0;
            state = (pkt_len > 0) ? GET_BODY : WAIT_SYNC0;
            break;
        case GET_BODY:
            pkt_buf[pkt_idx++] = b;
            if (pkt_idx >= pkt_len) state = GET_END;
            break;
        case GET_END:
            if (b == 0xEE) {
                uint8_t data_len = pkt_len - 1;  // exclude CRC
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
#define UART_SYNC0_BYTE  0xA5
#define UART_SYNC1_BYTE  0x5A
#define UART_END_BYTE    0xEE
#define UART_MAX_PAYLOAD 32

// 命令码 (PC → MCU):
#define UART_CMD_SET_EXPR  0x01
#define UART_CMD_SET_RGB   0x02
#define UART_CMD_QUERY     0x03
#define UART_CMD_HEARTBEAT 0x04

// 事件码 (MCU → PC):
#define UART_EVT_TOUCH     0x10
#define UART_EVT_NFC       0x11
#define UART_EVT_POSE      0x12
#define UART_EVT_ACK       0x05
```

### 4.4 验证方法

1. 编译烧录后，SSCOM 连接 COM6
2. PC 下发测试：发送 HEX `A5 5A 01 01 00 XX EE`，板子 LCD 表情变化 → 通了
3. MCU 上发测试：`UART_SendPacket(0x10, ...)`，SSCOM 收到正确 HEX

---

## 五、第四阶段：固件端事件上报（P3）

### 5.1 目标

把 `main_fsm.c` 中的 `UART_Printf()` 调试日志替换成 `UART_SendEvent()` 二进制事件帧。

### 5.2 具体改动

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
UART_SendEvent(UART_EVT_POSE, (uint8_t[]){0x01}, 1);
```

### 5.3 命令响应（PC 指令 → STM32 执行）

```c
void OnPcCommand(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    switch (cmd) {
    case UART_CMD_SET_EXPR:
        if (len >= 1) Expression_Set((Expression)payload[0]);
        break;
    case UART_CMD_SET_RGB:
        if (len >= 3) RGB_SetColor(payload[0], payload[1], payload[2]);
        break;
    case UART_CMD_HEARTBEAT:
        UART_SendPacket(UART_CMD_HEARTBEAT, (uint8_t[]){0x04, 0x00}, 2);
        break;
    }
}
```

---

## 六、接口规范 — 与 B 的联调约定

| 项目 | 约定 |
|------|------|
| 帧格式 | `[A5][5A][LEN][CMD+PAYLOAD][CRC-8][EE]` |
| CRC-8 | 多项式 0x07, MSB first |
| 最大payload | 32 字节 |
| PC 对应文件 | `pc_backend/comm/protocol.py` |
| 固件文件 | `firmware/Drivers/Src/uart_comm.c` |

### 命令码对照表

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

### 联调流程

1. A 先自测：用 UART_SendEvent 发测试帧，SSCOM 确认 HEX 正确
2. B 先自测：PC 端用测试帧确认解析正确
3. 联调：板子插 USB，B 运行 `python main.py`，A 触发触摸 → B 终端收到事件

---

## 七、完成标准

- [ ] NFC 读到至少一张 S50 白卡的 4 字节 UID（串口打印）
- [ ] AI 审查协议方案完成，审查记录已保存
- [ ] 协议方案根据 AI 建议修改完毕
- [ ] `uart_comm.c` 帧格式改为新协议，编译 0 Error 0 Warning
- [ ] PC 通过 SSCOM 发送 `A5 5A 01 01 00 XX EE`，板子 LCD 切到 NORMAL 表情
- [ ] 固件端触摸/NFC/姿态事件以二进制帧发出
- [ ] PC 指令 SET_EXPR / SET_RGB 在板子上正确响应
- [ ] 代码提交到 GitHub

---

## 八、参考文件

| 文件 | 用途 |
|------|------|
| `firmware/Drivers/Src/rc522_spi.c` | NFC 驱动 |
| `firmware/Drivers/Src/uart_comm.c` | 待改的串口协议文件 |
| `firmware/Drivers/Inc/uart_comm.h` | 待改的串口头文件 |
| `firmware/App/main_fsm.c` | FSM 中改事件上报 |
| `pc_backend/comm/protocol.py` | PC 端协议定义（参考格式） |
| `开发文档/Project_Brief.md` | 项目总规范 |
