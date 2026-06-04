# 协议方案 AI 审查记录

**日期**: 2026-06-04  
**审查工具**: Claude Opus 4.7  
**审查对象**: `A_NFC_Firmware_Protocol.md` 第四节"固件协议改造方案"

---

## 一、AI 建议汇总

### 建议 1：CRC-8 多项式选择

**问题**: 文档建议使用 CRC-8 多项式 0x07

**AI 分析**:
- 0x07 是常用的 CRC-8 多项式（CRC-8-ATM），检错能力适中
- 对于 UART 通信，推荐使用 **0x07（CRC-8-ATM）** 或 **0x31（CRC-8-Dallas/Maxim）**
- 0x07 更简单，0x31 检错能力稍强但计算复杂度相同

**建议**: ✅ **采纳原方案 0x07**

**理由**:
- 适合短帧通信（< 64 字节）
- 计算简单，嵌入式友好
- 业界广泛使用，参考代码多

---

### 建议 2：帧长度限制

**问题**: PAYLOAD 最大 32 字节，LEN 字段 1 字节（最大 255）

**AI 分析**:
- LEN = CMD(1) + DATA(最多32) = 最多 33 字节
- LEN 字段理论最大 255，但实际只用到 33，有较大冗余
- 当前设计下，LEN > 33 的帧应视为非法帧

**建议**: ✅ **采纳，增加边界检查**

**修改**:
```c
// 在 GET_LEN 状态添加严格边界检查
case GET_LEN:
    if (b == 0 || b > 33) {  // LEN=0 或 >33 都非法
        state = WAIT_SYNC0;
        break;
    }
    pkt_len = b;
    pkt_idx = 0;
    state = GET_BODY;
    break;
```

---

### 建议 3：帧尾 0xEE 的必要性

**问题**: 帧尾 0xEE 是否真的需要？

**AI 分析**:
- **优点**: 提供额外的帧完整性校验，有助于快速丢弃错误帧
- **缺点**: 增加 1 字节开销，且如果 PAYLOAD 末尾恰好是 0xEE 容易混淆
- **结论**: 对于定长协议（已知 LEN），帧尾不是必需的；但对于有噪声的 UART 环境，帧尾可以提高鲁棒性

**建议**: ✅ **采纳原方案，保留 0xEE**

**理由**:
- 野火开发板的 CH340 在高波特率下可能有干扰
- 帧尾可以快速识别"垃圾字节"，避免后续误解析
- 1 字节开销可接受

---

### 建议 4：状态机死锁风险

**问题**: 状态机是否有死锁或丢帧风险？

**AI 分析**:

**潜在问题 1**: 如果收到 `A5 5A LEN BODY...` 后，迟迟收不到 `0xEE`（比如断线），状态机会卡在 `GET_END`

**解决方案**: 添加超时机制

```c
static uint32_t last_byte_tick = 0;
#define FRAME_TIMEOUT_MS 100  // 100ms 内必须收完一帧

// 在每个 state 切换时更新时间戳
void UART_ParseFrames(void) {
    uint32_t now = HAL_GetTick();
    
    // 超时检测（除了 WAIT_SYNC0）
    if (state != WAIT_SYNC0 && (now - last_byte_tick) > FRAME_TIMEOUT_MS) {
        state = WAIT_SYNC0;  // 超时，重置状态机
    }
    
    uint8_t b;
    while (ring_get(&b)) {
        last_byte_tick = now;  // 收到字节，更新时间戳
        switch (state) {
            // ... 原代码
        }
    }
}
```

**潜在问题 2**: 如果收到 `A5 XX`（非 0x5A），会回到 WAIT_SYNC0，但这个 `XX` 如果恰好是 `A5`，会被忽略

**解决方案**: 改进同步头匹配逻辑

```c
case WAIT_SYNC1:
    if (b == 0x5A) {
        state = GET_LEN;
    } else if (b == 0xA5) {
        // 收到连续的 A5，保持在 WAIT_SYNC1
        state = WAIT_SYNC1;
    } else {
        state = WAIT_SYNC0;
    }
    break;
```

**建议**: ⚠️ **必须采纳超时机制**，可选采纳同步头改进

---

### 建议 5：CRC 计算范围

**问题**: CRC-8 应该计算哪些字节？

**AI 分析**:

文档中的代码：
```c
uint8_t data_len = pkt_len - 1;  // exclude CRC
uint8_t crc_expected = calc_crc8(pkt_buf, data_len);
```

这里 `pkt_buf` = `[CMD][DATA...][CRC]`，长度 = `pkt_len`

CRC 应该覆盖：`CMD + DATA`，不包括 CRC 本身 ✅

**但要注意**: 发送端和接收端必须一致！

**建议**: ✅ **采纳，但需明确文档**

**补充说明**:
```
CRC-8 计算范围: 从 CMD 字节开始，到 PAYLOAD 最后一个字节结束
不包括: SYNC0, SYNC1, LEN, CRC 本身, END
```

---

### 建议 6：错误处理完备性

**问题**: 是否有完善的错误处理？

**AI 分析**:

当前方案中，以下情况会静默丢弃帧：
1. LEN 超限 → 回到 WAIT_SYNC0 ✅
2. CRC 校验失败 → 回到 WAIT_SYNC0 ✅
3. END 字节不是 0xEE → 回到 WAIT_SYNC0 ✅

**缺少的**:
- 没有错误计数器（用于调试）
- 没有错误日志（生产环境可关闭）

**建议**: ⚠️ **建议添加错误统计**

```c
// 全局错误计数器（可选，调试用）
static struct {
    uint32_t invalid_len;
    uint32_t crc_fail;
    uint32_t end_byte_err;
    uint32_t timeout;
} uart_err_stats;

// 在相应位置递增计数器
case GET_LEN:
    if (b == 0 || b > 33) {
        uart_err_stats.invalid_len++;
        state = WAIT_SYNC0;
        break;
    }
    // ...

// 提供查询接口（串口命令）
// 命令: "uartstats" → 打印错误统计
```

---

### 建议 7：命令码冲突检测

**问题**: PC→MCU 和 MCU→PC 的命令码是否会冲突？

**AI 分析**:

当前约定：
- PC→MCU: 0x01 ~ 0x04
- MCU→PC: 0x05, 0x10 ~ 0x12

**潜在风险**: 如果 PC 误发送 0x10，MCU 会当作"查询状态"还是忽略？

**建议**: ✅ **采纳，明确方向位**

**改进方案**:
```c
// 使用最高位区分方向
#define CMD_PC2MCU_MASK   0x00  // PC→MCU: 0x00~0x7F
#define CMD_MCU2PC_MASK   0x80  // MCU→PC: 0x80~0xFF

// PC → MCU 命令（0x00~0x7F）
#define UART_CMD_SET_EXPR  0x01
#define UART_CMD_SET_RGB   0x02
#define UART_CMD_QUERY     0x03
#define UART_CMD_HEARTBEAT 0x04

// MCU → PC 事件（0x80~0xFF）
#define UART_EVT_ACK       0x85
#define UART_EVT_TOUCH     0x90
#define UART_EVT_NFC       0x91
#define UART_EVT_POSE      0x92
```

**或者更简单**: 保持现有编码，在命令处理函数中只处理合法方向的命令

```c
void OnPcCommand(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    // 只处理 PC→MCU 命令（0x01~0x04）
    if (cmd < 0x01 || cmd > 0x04) return;  // 忽略非法命令
    
    switch (cmd) {
        case UART_CMD_SET_EXPR:
            // ...
    }
}
```

**建议**: ⚠️ **必须采纳命令过滤**

---

### 建议 8：喂食模式与协议集成

**问题**: 当前 NFC 已改为喂食模式（不读 UID），如何与协议对接？

**AI 分析**:

原协议设计：
```c
// 0x11 MCU→PC NFC刷卡: [uid_len:1B][uid:N]
```

喂食模式下不读 UID，应该上报什么？

**建议**: ✅ **采纳，修改 NFC 事件协议**

**新协议定义**:
```c
// MCU→PC NFC 喂食事件: [duration_sec:2B][level:1B]
// duration_sec: 喂食时长（秒），小端序
// level: 0=tap, 1=snack, 2=meal, 3=feast

// 示例：喂食 15 秒（正餐）
// Payload: [0x0F, 0x00, 0x02]  // 15 秒, level=2
```

**或者保留原协议，UID 填 0**:
```c
// Payload: [0x00, 0x00, 0x00, 0x00, duration_low, duration_high]
```

**推荐**: 第一种方案更清晰

---

## 二、方案修改汇总

| 原方案 | AI 建议 | 采纳 | 修改后 |
|--------|---------|------|--------|
| CRC-8 多项式 0x07 | 保持 | ✅ | 无修改 |
| LEN 边界检查宽松 | 严格检查 LEN ∈ [1, 33] | ✅ | 添加边界检查 |
| 帧尾 0xEE | 保留 | ✅ | 无修改 |
| 无超时机制 | 添加 100ms 超时 | ✅ 必须 | 添加超时逻辑 |
| 同步头匹配 | 改进连续 A5 处理 | ✅ 可选 | 改进状态机 |
| CRC 范围 | 明确文档 | ✅ | 补充说明 |
| 无错误统计 | 添加统计计数器 | ✅ 推荐 | 添加调试接口 |
| 命令码无过滤 | 添加方向过滤 | ✅ 必须 | 添加范围检查 |
| NFC 上报 UID | 改为上报喂食时长+等级 | ✅ 必须 | 修改协议定义 |

---

## 三、最终协议规范（修正版）

### 帧格式
```
┌──────┬──────┬──────┬──────────────┬──────┬──────┐
│ SYNC │ SYNC │ LEN  │   PAYLOAD    │ CRC  │ END  │
│ 0xA5 │ 0x5A │  1B  │ CMD(1B)+Data │ CRC-8│ 0xEE │
└──────┴──────┴──────┴──────────────┴──────┴──────┘

LEN: PAYLOAD 总长度（CMD + DATA），范围 [1, 33]
CRC-8: 多项式 0x07，计算范围 = PAYLOAD（CMD + DATA）
超时: 帧接收超时 100ms
```

### 命令码（修正版）

| 值 | 方向 | 含义 | Payload |
|----|------|------|---------|
| 0x01 | PC→MCU | 设置表情 | [emo_id:1B] |
| 0x02 | PC→MCU | 设置RGB灯 | [R:1B][G:1B][B:1B] |
| 0x03 | PC→MCU | 查询状态 | 无 |
| 0x04 | PC→MCU | 心跳 | [seq:1B] |
| 0x05 | MCU→PC | ACK | [ack_cmd:1B][status:1B] |
| 0x10 | MCU→PC | 触摸事件 | [side:1B][type:1B] |
| 0x11 | MCU→PC | **NFC喂食事件** | [duration_sec_low:1B][duration_sec_high:1B][level:1B] |
| 0x12 | MCU→PC | 姿态事件 | [state:1B] |

**NFC 喂食等级定义**:
```c
#define NFC_LEVEL_TAP   0  // < 3秒
#define NFC_LEVEL_SNACK 1  // 3-10秒
#define NFC_LEVEL_MEAL  2  // 10-30秒
#define NFC_LEVEL_FEAST 3  // > 30秒
```

---

## 四、关键代码片段（修正版）

### 1. 改进的状态机解析（带超时）

```c
void UART_ParseFrames(void) {
    static enum { WAIT_SYNC0, WAIT_SYNC1, GET_LEN, GET_BODY, GET_END } state = WAIT_SYNC0;
    static uint8_t pkt_len, pkt_idx;
    static uint8_t pkt_buf[34];
    static uint32_t last_byte_tick = 0;
    
    uint32_t now = HAL_GetTick();
    
    // 超时检测
    if (state != WAIT_SYNC0 && (now - last_byte_tick) > 100) {
        state = WAIT_SYNC0;
        uart_err_stats.timeout++;
    }
    
    uint8_t b;
    while (ring_get(&b)) {
        last_byte_tick = now;
        
        switch (state) {
        case WAIT_SYNC0:
            if (b == 0xA5) state = WAIT_SYNC1;
            break;
            
        case WAIT_SYNC1:
            if (b == 0x5A) {
                state = GET_LEN;
            } else if (b == 0xA5) {
                // 连续 A5，保持等待
                state = WAIT_SYNC1;
            } else {
                state = WAIT_SYNC0;
            }
            break;
            
        case GET_LEN:
            if (b == 0 || b > 33) {
                uart_err_stats.invalid_len++;
                state = WAIT_SYNC0;
                break;
            }
            pkt_len = b;
            pkt_idx = 0;
            state = GET_BODY;
            break;
            
        case GET_BODY:
            pkt_buf[pkt_idx++] = b;
            if (pkt_idx >= pkt_len) state = GET_END;
            break;
            
        case GET_END:
            if (b == 0xEE) {
                uint8_t data_len = pkt_len - 1;
                uint8_t crc_expected = calc_crc8(pkt_buf, data_len);
                if (pkt_buf[data_len] == crc_expected) {
                    uint8_t cmd = pkt_buf[0];
                    if (cmd_callback) cmd_callback(cmd, pkt_buf + 1, data_len - 1);
                } else {
                    uart_err_stats.crc_fail++;
                }
            } else {
                uart_err_stats.end_byte_err++;
            }
            state = WAIT_SYNC0;
            break;
        }
    }
}
```

### 2. 命令过滤

```c
void OnPcCommand(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    // 只处理 PC→MCU 命令范围
    if (cmd < 0x01 || cmd > 0x04) return;
    
    switch (cmd) {
    case UART_CMD_SET_EXPR:
        if (len >= 1) Expression_Set((Expression)payload[0]);
        break;
    case UART_CMD_SET_RGB:
        if (len >= 3) RGB_SetColor(payload[0], payload[1], payload[2]);
        break;
    case UART_CMD_QUERY:
        // TODO: 上报当前状态
        break;
    case UART_CMD_HEARTBEAT:
        if (len >= 1) {
            UART_SendPacket(UART_EVT_ACK, (uint8_t[]){cmd, 0x00}, 2);
        }
        break;
    }
}
```

### 3. NFC 喂食事件上报（修正）

在 `main_fsm.c` 中：

```c
/* Card removed (edge detection) */
if (!card_present && card_present_last) {
    uint32_t feeding_duration_ms = now - feeding_start_time;
    uint32_t feeding_seconds = feeding_duration_ms / 1000;
    
    // 确定等级
    uint8_t level;
    if (feeding_seconds < 3) {
        level = NFC_LEVEL_TAP;
        Expression_Set(EMO_NORMAL);
        RGB_SetColor(0, 255, 255);
    } else if (feeding_seconds < 10) {
        level = NFC_LEVEL_SNACK;
        Expression_Set(EMO_HAPPY);
        RGB_Breathe(255, 200, 0, 2000);
    } else if (feeding_seconds < 30) {
        level = NFC_LEVEL_MEAL;
        Expression_Set(EMO_LOVE);
        RGB_Breathe(255, 100, 200, 2000);
    } else {
        level = NFC_LEVEL_FEAST;
        Expression_Set(EMO_SURPRISE);
        RGB_SetColor(255, 0, 255);
    }
    
    // 上报喂食事件（修正版）
    uint8_t nfc_payload[3];
    nfc_payload[0] = feeding_seconds & 0xFF;        // 低字节
    nfc_payload[1] = (feeding_seconds >> 8) & 0xFF; // 高字节
    nfc_payload[2] = level;
    UART_SendPacket(UART_EVT_NFC, nfc_payload, 3);
    
    // 保留串口日志（可选，调试用）
    const char* level_names[] = {"tap", "snack", "meal", "feast"};
    UART_Printf("[NFC] Feeding: %lus - %s\r\n", feeding_seconds, level_names[level]);
}
```

---

## 五、审查结论

✅ **原方案整体合理**，帧格式设计清晰，CRC 选择合适

⚠️ **必须修改项**（3 项）:
1. 添加帧接收超时机制（100ms）
2. 添加命令码方向过滤
3. 修改 NFC 事件协议以适配喂食模式

✅ **推荐修改项**（3 项）:
1. 严格 LEN 边界检查
2. 改进连续 A5 同步头处理
3. 添加错误统计计数器

📋 **文档改进项**（2 项）:
1. 明确 CRC 计算范围
2. 补充 NFC 喂食事件协议

---

## 六、下一步行动

1. ✅ **审查完成** - 本文档即为审查记录
2. ⏭️ **进入第三阶段** - 根据审查意见修改 `uart_comm.c`
3. 📝 **同步 B 角色** - 将修正后的协议规范发给 PC 端开发者

---

**审查完成时间**: 2026-06-04 15:30  
**审查结论**: 方案可行，建议采纳上述 8 项改进后实施
