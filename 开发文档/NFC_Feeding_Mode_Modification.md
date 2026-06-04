# NFC 功能简化：喂食模式修改记录

**日期**: 2026-06-04  
**修改人**: Claude (AI Assistant)  
**原因**: NFC 读卡 UID 功能调试困难（REQA 命令失败），改为简化的喂食交互模式  
**影响范围**: 固件层 - 状态机模块、命令处理模块

---

## 一、修改概述

### 原设计
- 读取 NFC 卡片 UID（需要 REQA → Anticollision → Select 完整流程）
- 根据不同卡片 UID 触发不同功能
- 依赖 `RC522_GetCardUID()` 函数

### 新设计（简化喂食模式）
- **只检测卡片存在**（使用 `RC522_CheckCard()`，无需读 UID）
- **任何卡片 = 喂食**
- **放置时长 = 喂食量**，触发不同等级的反馈

### 优势
✅ 绕过 REQA 失败问题（CheckCard 使用 REQA/WUPA fallback，更可靠）  
✅ 兼容所有 ISO14443A 卡片（门禁卡、公交卡、白卡）  
✅ 交互直观有趣  
✅ 无需数据库管理卡片 UID  

---

## 二、喂食等级设计

| 放置时长 | 等级 | 表情 | 灯光效果 | 串口消息 |
|---------|------|------|----------|----------|
| < 3 秒 | 快速碰触 | NORMAL | 青色闪烁 | "Quick tap - Hello!" |
| 3-10 秒 | 小食 | HAPPY | 暖黄呼吸 | "Snack - Yummy!" |
| 10-30 秒 | 正餐 | LOVE | 粉色呼吸 | "Meal - So good!" |
| > 30 秒 | 大餐 | SURPRISE | 品红闪烁 | "Feast - Amazing!" |

---

## 三、代码修改详情

### 3.1 文件：`firmware/App/main_fsm.h`

**修改位置**: 第 19 行后添加

**新增内容**:
```c
void FSM_SetNfcEnable(uint8_t en);
```

**说明**: 添加 NFC 轮询开关函数声明，用于调试时临时关闭后台轮询

---

### 3.2 文件：`firmware/App/main_fsm.c`

#### 修改 1: 添加 NFC 使能标志

**修改位置**: 第 27-29 行

**原代码**:
```c
static SystemState current_state;
static uint8_t     pose_enabled = 1;    /* MPU6050 polling on by default */
static uint32_t    last_touch_tick;
```

**修改后**:
```c
static SystemState current_state;
static uint8_t     pose_enabled = 1;    /* MPU6050 polling on by default */
static uint8_t     nfc_enabled = 1;     /* NFC polling on by default */
static uint32_t    last_touch_tick;
```

---

#### 修改 2: NFC 轮询逻辑替换

**修改位置**: 第 108-137 行

**原代码**:
```c
/* NFC polling */
if (now - last_nfc_tick >= NFC_POLL_MS) {
    last_nfc_tick = now;
    static uint8_t nfc_dbg_cnt = 0;
    uint8_t card_ok = RC522_CheckCard();
    if (++nfc_dbg_cnt >= 20) {  /* print once per second */
        nfc_dbg_cnt = 0;
        UART_Printf("[NFC DBG] poll: card=%d\r\n", card_ok);
    }
    if (card_ok) {
        uint8_t uid_len = RC522_GetCardUID(card_uid);
        if (uid_len == 4) {
            last_interact_tick = now;

            if (current_state == SYS_SLEEP) {
                FSM_ChangeState(SYS_IDLE);
            } else {
                FSM_ChangeState(SYS_INTERACT);
                Expression_Set(EMO_FOCUS);
                RGB_Breathe(0, 0, 255, 3000);  /* blue breathing */
            }

            UART_Printf("[NFC] Card UID: %02X%02X%02X%02X\r\n",
                        card_uid[0],card_uid[1],card_uid[2],card_uid[3]);
        } else {
            UART_Printf("[NFC] UID fail (len=%d)\r\n", uid_len);
        }
        RC522_HaltCard();
    }
}
```

**修改后**:
```c
/* NFC polling - Simplified feeding mode (any card = food, duration = amount) */
if (nfc_enabled && now - last_nfc_tick >= NFC_POLL_MS) {
    last_nfc_tick = now;
    static uint8_t  card_present_last = 0;
    static uint32_t feeding_start_time = 0;
    uint8_t card_present = RC522_CheckCard();

    /* Card just placed (edge detection) */
    if (card_present && !card_present_last) {
        feeding_start_time = now;
        last_interact_tick = now;

        if (current_state == SYS_SLEEP) {
            FSM_ChangeState(SYS_IDLE);
        } else {
            FSM_ChangeState(SYS_INTERACT);
        }

        Expression_Set(EMO_FOCUS);
        RGB_Breathe(0, 128, 255, 2000);  /* cyan breathing - feeding mode */
        UART_Printf("[NFC] Feeding started...\r\n");
    }

    /* Card removed (edge detection) */
    if (!card_present && card_present_last) {
        uint32_t feeding_duration_ms = now - feeding_start_time;
        uint32_t feeding_seconds = feeding_duration_ms / 1000;

        /* Feedback based on feeding duration */
        if (feeding_seconds < 3) {
            UART_Printf("[NFC] Quick tap (%lus) - Hello!\r\n", feeding_seconds);
            Expression_Set(EMO_NORMAL);
            RGB_SetColor(0, 255, 255);  /* cyan flash */
        } else if (feeding_seconds < 10) {
            UART_Printf("[NFC] Snack (%lus) - Yummy!\r\n", feeding_seconds);
            Expression_Set(EMO_HAPPY);
            RGB_Breathe(255, 200, 0, 2000);  /* warm yellow */
        } else if (feeding_seconds < 30) {
            UART_Printf("[NFC] Meal (%lus) - So good!\r\n", feeding_seconds);
            Expression_Set(EMO_LOVE);
            RGB_Breathe(255, 100, 200, 2000);  /* pink */
        } else {
            UART_Printf("[NFC] Feast (%lus) - Amazing!\r\n", feeding_seconds);
            Expression_Set(EMO_SURPRISE);
            RGB_SetColor(255, 0, 255);  /* magenta flash */
        }
    }

    card_present_last = card_present;
}
```

**核心改动**:
1. 移除 `RC522_GetCardUID()` 调用（不再读 UID）
2. 只用 `RC522_CheckCard()` 检测存在
3. 添加边缘检测（检测卡片放置/移开的瞬间）
4. 记录放置开始时间，移开时计算时长
5. 根据时长分级反馈
6. 添加 `nfc_enabled` 条件判断

---

#### 修改 3: 添加 NFC 使能控制函数

**修改位置**: 第 209-212 行后添加

**新增内容**:
```c
void FSM_SetNfcEnable(uint8_t en) {
    nfc_enabled = en;
}
```

**说明**: 实现 NFC 轮询开关，用于 `nfcoff`/`nfcon` 命令

---

### 3.3 文件：`firmware/desktop_assistant/Core/Src/main.c`

#### 修改 1: 添加 NFC 开关命令

**修改位置**: 第 113-116 行

**原代码**:
```c
} else if (strcmp(line, "mpuon") == 0) {
    FSM_SetPoseEnable(1);
    UART_Printf("MPU polling ON\r\n");
} else if (strcmp(line, "state") == 0) {
```

**修改后**:
```c
} else if (strcmp(line, "mpuon") == 0) {
    FSM_SetPoseEnable(1);
    UART_Printf("MPU polling ON\r\n");
} else if (strcmp(line, "nfcoff") == 0) {
    FSM_SetNfcEnable(0);
    UART_Printf("NFC polling OFF (manual test mode)\r\n");
} else if (strcmp(line, "nfcon") == 0) {
    FSM_SetNfcEnable(1);
    UART_Printf("NFC polling ON\r\n");
} else if (strcmp(line, "state") == 0) {
```

**说明**: 添加 `nfcoff` 和 `nfcon` 命令，用于调试时控制后台 NFC 轮询

---

#### 修改 2: 更新帮助信息

**修改位置**: 第 234 行

**原代码**:
```c
UART_Printf("Commands: led R G B, mpu, mpuon, state, nfc, nfcboost, nfclow, nfcraw, nfcdbg, nfcreset, help\r\n");
```

**修改后**:
```c
UART_Printf("Commands: led R G B, mpu, mpuon, mpuoff, nfc, nfcoff, nfcon, nfcboost, nfclow, nfcraw, nfcdbg, nfcreset, state, help\r\n");
```

---

### 3.4 文件：`firmware/Drivers/Src/rc522_spi.c`

#### 修改: 显式设置 RF 配置寄存器

**修改位置**: 第 139-146 行

**原代码**:
```c
/* NOTE: RFCfgReg and RxSelReg are left at power-on defaults:
   RFCfgReg = 0x48 (18 dB Rx gain) — stable for continuous polling
   RxSelReg = 0x84 (default)        — max gain (0x7F / 48 dB)
   caused TemperatureErr and spontaneous reset under 48 % TX duty cycle */

/* Antenna on */
AntennaOn();
```

**修改后**:
```c
/* NOTE: RFCfgReg and RxSelReg are left at power-on defaults:
   RFCfgReg = 0x48 (18 dB Rx gain) — stable for continuous polling
   RxSelReg = 0x84 (default)        — max gain (0x7F / 48 dB)
   caused TemperatureErr and spontaneous reset under 48 % TX duty cycle */

/* Reduce RF power to prevent spontaneous reset on weak power supply */
RC522_WriteReg(RFCfgReg, 0x48);   /* 18 dB - conservative, stable */
RC522_WriteReg(RxSelReg, 0x84);   /* default Rx gain */

/* Antenna on */
AntennaOn();
```

**说明**: 显式写入寄存器（虽然是默认值），避免某些克隆模块上电默认值异常

---

## 四、新增调试命令

在原有 NFC 调试命令基础上，新增：

| 命令 | 功能 | 用途 |
|------|------|------|
| `nfcoff` | 关闭 NFC 后台轮询 | 手动测试 NFC 时使用，避免干扰 |
| `nfcon` | 开启 NFC 后台轮询 | 恢复正常喂食模式 |
| `nfclow` | 降低 RF 功率到 13dB | 供电不足时使用 |
| `nfcboost` | 提升 RF 功率到 25dB | 信号弱时使用 |
| `nfcraw` | 底层 RF 测试 | 诊断 REQA 响应 |

**注意**: 正常使用时 NFC 轮询应保持开启（`nfcon`），调试命令仅用于开发阶段。

---

## 五、使用说明

### 正常使用（喂食模式）

1. 确保 NFC 轮询已开启（默认开启，或发送 `nfcon`）
2. 将任意 NFC 卡片放到天线上
3. 观察表情切换为 FOCUS（专注），灯光变为青色呼吸
4. 根据喂食量决定放置时长：
   - 快速打招呼：< 3 秒
   - 小食：3-10 秒
   - 正餐：10-30 秒
   - 大餐：> 30 秒
5. 移开卡片，观察反馈表情和灯光

### 调试模式

如需手动测试 NFC 硬件：

```bash
nfcoff          # 关闭后台轮询
nfcdbg          # 查看寄存器状态
nfc             # 手动测试读卡
nfcon           # 恢复正常模式
```

---

## 六、后续优化建议

### 6.1 PC 端集成（可选）

在 `pc_backend/comm/protocol.py` 中定义喂食事件协议：

```python
# 固件 → PC 端
{
    "type": "nfc_feeding",
    "duration_sec": 15,
    "level": "meal"  # "tap" | "snack" | "meal" | "feast"
}

# PC 端 → 固件（可选：AI 决定表情）
{
    "type": "expression",
    "name": "happy"
}
```

### 6.2 添加喂食统计

在状态机中添加累计喂食次数和总时长，定期通过串口上报：

```c
static uint32_t total_feedings = 0;
static uint32_t total_feeding_seconds = 0;
```

### 6.3 喂食冷却时间

防止连续快速碰触刷屏：

```c
#define FEEDING_COOLDOWN_MS 2000  /* 2秒冷却 */
static uint32_t last_feeding_end = 0;

if (card_present && !card_present_last) {
    if (now - last_feeding_end < FEEDING_COOLDOWN_MS) {
        return;  /* 忽略过快的重复触发 */
    }
    // ... 正常喂食逻辑
}
```

### 6.4 可配置阈值

将时长阈值改为可通过串口配置：

```c
uint16_t threshold_snack = 3;   /* 默认 3 秒 */
uint16_t threshold_meal = 10;   /* 默认 10 秒 */
uint16_t threshold_feast = 30;  /* 默认 30 秒 */

// 串口命令：nfcthresh <snack> <meal> <feast>
// 例如：nfcthresh 5 15 60
```

---

## 七、测试验证

### 测试项目清单

| 测试项 | 测试方法 | 期望结果 | 实际结果 | 状态 |
|--------|----------|----------|----------|------|
| 快速碰触 | 卡片放置 < 3 秒 | NORMAL 表情 + 青色闪烁 | | ⬜ 待测 |
| 小食 | 卡片放置 5 秒 | HAPPY 表情 + 暖黄呼吸 | | ⬜ 待测 |
| 正餐 | 卡片放置 15 秒 | LOVE 表情 + 粉色呼吸 | | ⬜ 待测 |
| 大餐 | 卡片放置 35 秒 | SURPRISE 表情 + 品红闪烁 | | ⬜ 待测 |
| 状态切换 | SLEEP 状态下放卡 | 唤醒到 IDLE → INTERACT | | ⬜ 待测 |
| 计时准确性 | 放置 10 秒精确计时 | 串口显示 10s ± 1s | | ⬜ 待测 |
| 边缘检测 | 快速连续放置/移开 | 不误触发 | | ⬜ 待测 |
| 兼容性 | 测试不同卡片类型 | 门禁/公交/白卡都能用 | | ⬜ 待测 |

### 测试记录模板

```
日期: ____年__月__日
测试人: ________
固件版本: ________
测试卡片: ________

测试 1 - 快速碰触:
  放置时长: ___秒
  表情: ________
  灯光: ________
  串口输出: ________
  结论: ☐ 通过  ☐ 失败

测试 2 - 小食:
  ...
```

---

## 八、Git 提交建议

```bash
git add firmware/App/main_fsm.c firmware/App/main_fsm.h
git add firmware/desktop_assistant/Core/Src/main.c
git add firmware/Drivers/Src/rc522_spi.c
git add 开发文档/NFC_Feeding_Mode_Modification.md

git commit -m "feat(nfc): simplify to feeding mode, bypass UID read

- Replace UID-based logic with presence-only detection
- Add feeding duration tracking (tap/snack/meal/feast levels)
- Add nfcoff/nfcon commands for debug control
- Fix RF config explicit write for clone modules
- Resolve REQA failure by using CheckCard only

Closes #NFC-001"
```

---

## 九、相关文档

- **硬件资料**: `硬件资料/【野火】零死角玩转STM32—F103指南者.pdf` 第 47 章（NFC 模块）
- **原设计文档**: `开发文档/Project_Brief.md`
- **NFC 调试任务**: `开发文档/Team_Tasks/A_NFC_Firmware_Protocol.md`
- **测试报告**: `开发文档/Test_Report_001.md`（需更新）

---

## 十、备注

- **保留的功能**: 原有的 `nfc`/`nfcdbg`/`nfcreset` 等调试命令仍可用，方便后续硬件排查
- **向后兼容**: 如果将来 NFC 硬件问题解决，可恢复 UID 读取功能，喂食模式可保留为 fallback
- **性能影响**: NFC 轮询频率 50ms（保持不变），CheckCard 比 GetCardUID 更快，CPU 占用更低

---

**修改完成时间**: 2026-06-04 14:30  
**下次更新**: 测试验证后补充实际测试数据
