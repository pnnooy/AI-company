# 固件协议改造 - 测试指南

**日期**: 2026-06-04  
**版本**: v2.0 (新协议)  
**状态**: 代码已完成，待测试

---

## 一、修改概述

✅ **已完成的代码修改**:

1. ✅ `uart_comm.h` - 协议定义更新（新帧格式、命令码、NFC喂食协议）
2. ✅ `uart_comm.c` - CRC-8 实现、新帧发送/解析、超时机制、错误统计
3. ✅ `main.c` - PC 命令处理函数、错误统计查询命令
4. ✅ `main_fsm.c` - NFC 喂食事件上报（时长+等级）

---

## 二、新协议规格

### 帧格式
```
┌──────┬──────┬──────┬──────────────┬──────┬──────┐
│ SYNC │ SYNC │ LEN  │   PAYLOAD    │ CRC  │ END  │
│ 0xA5 │ 0x5A │  1B  │ CMD(1B)+Data │ CRC-8│ 0xEE │
└──────┴──────┴──────┴──────────────┴──────┴──────┘

LEN: 范围 [1, 33] = CMD(1) + DATA(0-32)
CRC-8: 多项式 0x07, 计算范围 = CMD + DATA
超时: 帧接收超时 100ms
```

### 命令码对照表

| 值 | 方向 | 含义 | Payload | 示例 |
|----|------|------|---------|------|
| 0x01 | PC→MCU | 设置表情 | [emo_id:1B] | `A5 5A 02 01 00 06 EE` (normal) |
| 0x02 | PC→MCU | 设置RGB灯 | [R:1B][G:1B][B:1B] | `A5 5A 04 02 FF 00 00 FE EE` (红) |
| 0x03 | PC→MCU | 查询状态 | 无 | `A5 5A 01 03 03 EE` |
| 0x04 | PC→MCU | 心跳 | [seq:1B] | `A5 5A 02 04 01 04 EE` |
| 0x05 | MCU→PC | ACK | [ack_cmd:1B][status:1B] | `A5 5A 03 05 04 00 02 EE` |
| 0x10 | MCU→PC | 触摸事件 | [side:1B][type:1B] | `A5 5A 03 10 00 01 12 EE` |
| 0x11 | MCU→PC | NFC喂食 | [dur_low:1B][dur_high:1B][level:1B] | `A5 5A 04 11 0F 00 02 1A EE` |
| 0x12 | MCU→PC | 姿态事件 | [state:1B] | `A5 5A 02 12 01 12 EE` |

### 表情 ID
```
0 = normal
1 = happy
2 = focus
3 = angry
4 = sleep
5 = surprise
6 = sad
7 = love
```

### NFC 喂食等级
```
0 = tap   (< 3秒)
1 = snack (3-10秒)
2 = meal  (10-30秒)
3 = feast (> 30秒)
```

---

## 三、测试准备

### 3.1 编译烧录

```bash
# 在 Keil 中
F7  # 编译（应该 0 Error 0 Warning）
F8  # 烧录到开发板
```

### 3.2 打开串口工具

打开 `串口调试工具SSCOM/sscom.5.13.1.exe`
- 端口: COM6
- 波特率: 115200
- 数据位: 8
- 停止位: 1
- 校验: None
- **重要**: 关闭 DTR 和 RTS

---

## 四、测试步骤

### 测试 1：验证固件启动

**操作**: 复位开发板

**期望输出**:
```
UART Comm Ready
RC522 OK: SPI 2MHz, Ver=0x92
Desktop Assistant Ready
```

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 2：PC→MCU - 设置表情 (0x01)

**目的**: 测试 PC 发送命令到 MCU

**帧构造**:
```
设置为 HAPPY 表情 (emo_id=1):

A5 5A 02 01 01 01 EE

分解:
A5 5A       - SYNC
02          - LEN = 2 (CMD + 1 字节 DATA)
01          - CMD = 0x01 (SET_EXPR)
01          - DATA = 0x01 (HAPPY)
01          - CRC-8 = CRC8([01 01]) = 0x01
EE          - END
```

**操作**:
1. SSCOM 切换到 HEX 发送模式
2. 输入: `A5 5A 02 01 01 01 EE`
3. 点击发送

**期望**:
- LCD 表情切换为 HAPPY（笑脸）
- 串口输出: `[PC CMD] Set expression: 1`

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 3：PC→MCU - 设置 RGB 灯 (0x02)

**帧构造**:
```
设置为红色 (R=255, G=0, B=0):

A5 5A 04 02 FF 00 00 FE EE

分解:
A5 5A       - SYNC
04          - LEN = 4
02          - CMD = 0x02 (SET_RGB)
FF 00 00    - DATA = R=255, G=0, B=0
FE          - CRC-8 = CRC8([02 FF 00 00])
EE          - END
```

**操作**: 发送 `A5 5A 04 02 FF 00 00 FE EE`

**期望**:
- RGB LED 变为红色
- 串口输出: `[PC CMD] Set RGB: (255,0,0)`

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 4：PC→MCU - 心跳 (0x04)

**帧构造**:
```
心跳 seq=1:

A5 5A 02 04 01 04 EE

分解:
A5 5A       - SYNC
02          - LEN = 2
04          - CMD = 0x04 (HEARTBEAT)
01          - DATA = seq=1
04          - CRC-8 = CRC8([04 01])
EE          - END
```

**操作**: 发送 `A5 5A 02 04 01 04 EE`

**期望**:
- 串口输出: `[PC CMD] Heartbeat seq=1`
- **收到回复帧**: `A5 5A 03 05 04 00 02 EE` (ACK)

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 5：MCU→PC - 触摸事件 (0x10)

**操作**: 用手触摸左侧触摸传感器（PC4）

**期望**:
- 串口输出: `[TOUCH] LEFT TAP`
- **收到二进制帧**: `A5 5A 03 10 00 01 XX EE`
  - `10` = UART_EVT_TOUCH
  - `00` = side (LEFT)
  - `01` = type (TAP)
  - `XX` = CRC-8

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 6：MCU→PC - NFC 喂食事件 (0x11)

**操作**:
1. 将 NFC 卡片放到天线上
2. 等待 5 秒
3. 移开卡片

**期望**:
- 串口输出: `[NFC] Feeding started...`
- 表情切换为 HAPPY
- RGB 灯呼吸（暖黄色）
- 串口输出: `[NFC] Feeding: 5s - snack (level=1)`
- **收到二进制帧**: `A5 5A 04 11 05 00 01 XX EE`
  - `11` = UART_EVT_NFC
  - `05 00` = duration = 5 秒（小端序）
  - `01` = level (SNACK)
  - `XX` = CRC-8

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 7：错误统计查询

**操作**: 发送文本命令 `uartstats`

**期望输出**:
```
=== UART Error Statistics ===
Invalid LEN:  0
CRC fail:     0
END byte err: 0
Timeout:      0
```

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 8：错误帧测试 - CRC 错误

**目的**: 验证 CRC 校验有效

**操作**: 发送错误的 CRC
```
A5 5A 02 01 01 FF EE  (CRC 故意错误，应该是 01 不是 FF)
```

**期望**:
- 表情**不变**（命令被丢弃）
- 无 `[PC CMD]` 输出
- 发送 `uartstats` 后，`CRC fail` 计数 +1

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 9：错误帧测试 - LEN 超限

**操作**: 发送 LEN=50（超出 33 的限制）
```
A5 5A 32 01 ...  (LEN=50, 超限)
```

**期望**:
- 帧被丢弃
- `uartstats` 显示 `Invalid LEN` +1

**结果**: ⬜ 通过 / ⬜ 失败

---

### 测试 10：超时测试

**操作**:
1. 发送不完整的帧: `A5 5A 02 01`
2. 等待 200ms
3. 发送完整帧: `A5 5A 02 01 01 01 EE`

**期望**:
- 第一个不完整帧超时后被丢弃
- 第二个完整帧正常处理
- `uartstats` 显示 `Timeout` +1

**结果**: ⬜ 通过 / ⬜ 失败

---

## 五、CRC-8 计算参考

如需手动验证 CRC，使用以下 Python 代码：

```python
def calc_crc8(data):
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
        crc &= 0xFF
    return crc

# 示例
payload = [0x01, 0x01]  # CMD=0x01, DATA=0x01
print(f"CRC-8: 0x{calc_crc8(payload):02X}")  # 输出: 0x01
```

---

## 六、常见帧示例

### PC→MCU 完整示例

```
# 设置为 NORMAL 表情
A5 5A 02 01 00 06 EE

# 设置为绿色
A5 5A 04 02 00 FF 00 FD EE

# 设置为白色
A5 5A 04 02 FF FF FF 00 EE

# 查询状态
A5 5A 01 03 03 EE

# 心跳 seq=10
A5 5A 02 04 0A 0F EE
```

### MCU→PC 完整示例

```
# 触摸事件：右侧 HOLD
A5 5A 03 10 01 02 14 EE

# NFC喂食：15秒，MEAL
A5 5A 04 11 0F 00 02 1A EE

# 姿态事件：SHAKE
A5 5A 02 12 01 12 EE

# ACK 心跳
A5 5A 03 05 04 00 02 EE
```

---

## 七、故障排查

### 问题 1：发送命令后无响应

**检查**:
1. CRC 是否正确？用 Python 脚本验证
2. `uartstats` 显示什么？CRC fail? Invalid LEN?
3. 帧尾是否是 `EE`？
4. LEN 是否正确？（CMD + DATA 的总长度）

### 问题 2：串口收到乱码

**检查**:
1. 波特率是否 115200？
2. DTR/RTS 是否关闭？
3. 是否开启了 HEX 显示模式？

### 问题 3：NFC 事件上报格式不对

**检查**:
1. 喂食时长是否超过 255 秒？需要用 2 字节（小端序）
2. Level 是否在 0-3 范围内？

---

## 八、测试完成标准

**全部 10 项测试通过后，协议改造验证完成**

- [ ] 测试 1：固件启动
- [ ] 测试 2：设置表情
- [ ] 测试 3：设置 RGB
- [ ] 测试 4：心跳+ACK
- [ ] 测试 5：触摸事件上报
- [ ] 测试 6：NFC 喂食事件上报
- [ ] 测试 7：错误统计查询
- [ ] 测试 8：CRC 错误检测
- [ ] 测试 9：LEN 超限检测
- [ ] 测试 10：超时机制

---

## 九、下一步

测试通过后：

1. ✅ 固件端协议改造完成
2. ⏭️ 与 B 角色联调（PC 端 `pc_backend/comm/protocol.py`）
3. ⏭️ 完成第四阶段：其他事件上报（触摸、姿态）
4. ⏭️ 提交代码到 GitHub

---

**测试日期**: ________  
**测试人**: ________  
**测试结果**: ⬜ 全部通过 / ⬜ 部分通过 / ⬜ 失败
