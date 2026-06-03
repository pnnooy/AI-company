# 桌面学术助手机器人 (Desktop Academic Assistant Robot)

> 面向大学生的桌面级 AI 伴侣，基于 STM32F103VET6 + 多模态传感器

## 项目概述

一个运行在**野火指南者开发板**上的桌面机器人，通过 LCD 动态表情、RGB 氛围灯、电容触摸、六轴姿态感应、NFC 刷卡实现多模态桌面交互。PC 端通过串口连接 AI 大脑进行决策。

**当前阶段**：硬件驱动层基本完成，应用层状态机运行中，LCD 颜色显示已校准，表情动画可用。正在完善表情素材和 PC 端 AI 集成。

## 硬件架构

| 模块 | 设备 | 协议 | 引脚 | 状态 |
|------|------|------|------|------|
| 主控 | STM32F103VET6 | Cortex-M3 72MHz | — | ✅ |
| 显示 | 3.2" ILI9341 LCD | FSMC 8080 16-bit | 板载并口 | ✅ 颜色已校准 |
| 串口 | CH340 USB-TTL | USART1 | PA9(TX) PA10(RX) | ✅ |
| RGB灯 | 共阳 RGB LED | TIM3 PWM | PB5(R) PB0(G) PB1(B) | ✅ |
| 左触摸 | TTP223-A | EXTI | PC4 | ✅ |
| 右触摸 | TTP223-B | EXTI | PC5 | ✅ |
| 姿态 | MPU6050 | 软 I2C | PA11(SCL) PA12(SDA) | ✅ |
| NFC | MFRC-522 | SPI1 | PA5(SCK) PA6(MISO) PA7(MOSI) PA4(CS) PA3(RST) | ⚠️ SPI稳定，读卡仍在调试 |

> ⚠️ **重要**：FSMC NADV 与硬件 I2C1_SDA 共用 PB7，**不可使用硬件 I2C1**。MPU6050 已改用软件 I2C (PA11/PA12) 规避冲突。

## 快速开始

### 开发环境

| 工具 | 版本/说明 |
|------|-----------|
| IDE | Keil MDK-ARM V5 (V5.06 update 6) |
| 芯片包 | Keil.STM32F1xx_DFP.2.4.1 |
| 配置工具 | STM32CubeMX (生成 HAL 初始化代码) |
| HAL 库 | STM32Cube_FW_F1 |
| 烧录器 | Fire-Debugger (野火 DAP, CMSIS-DAP 标准) |
| 串口工具 | SSCOM V5.13.1（仓库自带 `串口调试工具SSCOM/`，**关 DTR/RTS**）|
| Python | 3.9+ (Pillow 用于图片素材生成) |

### 克隆与编译

```bash
git clone https://github.com/pnnooy/AI-company.git
cd AI-company
```

1. 打开 `firmware/desktop_assistant/MDK-ARM/desktop_assistant.uvprojx`
2. Keil 中 F7 编译（应 0 Error 0 Warning）
3. F8 烧录（Fire-Debugger 连接 SWD 接口）
4. 打开 `串口调试工具SSCOM/sscom.5.13.1.exe`，COM6, 115200-8-N-1，关闭 DTR/RTS
5. 复位后应看到 `Desktop Assistant Ready`

### 时钟说明

当前使用 **HSI 内部 64MHz**（HSE 外部 8MHz 晶振未起振，待排查）。CubeMX 配置文件中目标为 72MHz PLL，实际运行在 HSI 64MHz。

## 项目结构

```
AI-company/
├── CLAUDE.md                     # 项目总规范（开发前必读）
├── README.md                     # 本文件
├── .gitignore
├── 开发文档/
│   ├── Project_Brief.md          # 项目规范书 V2.1
│   ├── Development_Plan.md       # 开发计划
│   ├── CubeMX_Config_Guide.md    # CubeMX 配置指南
│   ├── Expression_Task_Brief.md  # 表情素材任务书（给美术同学）
│   └── Test_Report_001.md        # 首次测试报告
├── 硬件资料/
│   ├── 硬件清单05-01.pdf
│   └── 【野火】零死角玩转STM32—F103指南者.pdf
├── 串口调试工具SSCOM/           # 团队统一串口工具 (SSCOM V5.13.1)
│   ├── sscom.5.13.1.exe
│   └── sscom51.ini               # 预配置: COM6, 115200-8-N-1
├── firmware/
│   ├── desktop_assistant/        # CubeMX 生成的 Keil 工程
│   │   ├── Core/Src/main.c       # 主入口 + 串口命令处理
│   │   ├── Core/Src/fsmc.c       # FSMC 初始化 (CubeMX 生成)
│   │   ├── Core/Src/tim.c        # TIM3 PWM 初始化
│   │   ├── Core/Src/spi.c        # SPI1 初始化
│   │   └── MDK-ARM/              # Keil 工程文件 (.uvprojx)
│   ├── Drivers/                  # 自定义 BSP 驱动层
│   │   ├── Inc/                  # 7 个头文件
│   │   │   ├── ili9341_fsmc.h    #   LCD 驱动
│   │   │   ├── rgb_led.h         #   RGB LED 驱动
│   │   │   ├── uart_comm.h       #   串口通信协议
│   │   │   ├── touch_sensor.h    #   TTP223 触摸
│   │   │   ├── mpu6050_hal.h     #   MPU6050 六轴
│   │   │   ├── soft_i2c.h        #   软件 I2C
│   │   │   └── rc522_spi.h       #   NFC 读卡
│   │   └── Src/                  # 7 个对应源文件
│   ├── App/                      # 应用层
│   │   ├── main_fsm.c/.h         #   主状态机
│   │   ├── expression_engine.c/.h #  表情引擎
│   │   ├── expression_types.h    #   表情枚举
│   │   └── expression_assets.c/.h #  表情素材数据 (14帧 80×80 RGB565)
│   └── Assets/                   # 表情 PNG 素材源文件
└── tools/
    ├── png2rgb565.py             # PNG → RGB565 C数组 转换
    └── make_assets.py            # 表情素材批量生成脚本
```

## 串口命令

通过 SSCOM 发送文本命令（115200 bps, 以 `\r\n` 结尾）：

| 命令 | 功能 | 示例 |
|------|------|------|
| `led R G B` | 设置 RGB 灯颜色 (0-255) | `led 255 128 0` |
| `mpu` | 读取 MPU6050 加速度/角速度/姿态 | `mpu` |
| `mpuoff` | 关闭 MPU6050 轮询 | `mpuoff` |
| `mpuon` | 开启 MPU6050 轮询 | `mpuon` |
| `emo <name>` | 切换表情 | `emo happy` |
| `lcd R G B` | LCD 全屏填充纯色 | `lcd 255 0 0` |
| `calib` | LCD 颜色诊断测试图案 | `calib` |
| `state` | 查看当前状态机状态 | `state` |
| `nfc` | 手动读卡（显示UID或失败原因） | `nfc` |
| `nfcdbg` | 读取 MFRC522 全部寄存器 | `nfcdbg` |
| `nfcreset` | 软复位 MFRC522 | `nfcreset` |
| `help` | 列出所有命令 | `help` |

表情名称：`normal`, `happy`, `focus`, `angry`, `sleep`, `surprise`, `sad`, `love`

触摸传感器和 MPU6050 姿态变化也会自动触发表情切换和灯光效果。

## 模块开发状态

| 模块 | 文件 | 状态 | 备注 |
|------|------|------|------|
| UART 通信 | uart_comm.c | ✅ 完成 | printf重定向, 环形缓冲, 二进制帧+CRC |
| ILI9341 LCD | ili9341_fsmc.c | ✅ 完成 | FSMC 8080, PIXEL颜色补偿, calib 8/8通过 |
| RGB LED | rgb_led.c | ✅ 完成 | TIM3 PWM, 呼吸/纯色/关灯 |
| MPU6050 | mpu6050_hal.c | ✅ 完成 | 软I2C, SHAKE+FALL检测 |
| 软 I2C | soft_i2c.c | ✅ 完成 | PA11/PA12, 规避FSMC冲突 |
| TTP223 触摸 | touch_sensor.c | ✅ 完成 | EXTI中断, TAP/HOLD/DOUBLE |
| NFC RC522 | rc522_spi.c | ⚠️ 调试中 | SPI已稳定(2MHz), 读卡REQA失败待排查 |
| 表情引擎 | expression_engine.c | ✅ 完成 | 8表情14帧, 动画轮播, 2x缩放 |
| 主状态机 | main_fsm.c | ✅ 完成 | IDLE→ACTIVE→INTERACT→SLEEP→ALERT |

## LCD 颜色校准 (重要)

### 问题背景

野火指南者 PCB 上 STM32 FSMC 与 ILI9341 的数据线存在交叉布线：**D[15:11] 与 D[10:6] 两组 5-bit 通道互换**，导致 R 和 G 通道高 5 位交换。这不是简单的 byte_swap，也不是 bit_reverse。

### PCB 实际映射

```
STM32 FSMC  →  ILI9341
D[15:11]    →  D[10:6]    ← R[4:0] 与 G[5:1] 互换
D[10:6]     →  D[15:11]   ←
D[5]        →  D[5]       ← G[0] 不动
D[4:0]      →  D[4:0]     ← B[4:0] 不动
```

### 补偿公式 (PIXEL)

所有通过 FSMC 写入 ILI9341 的 16-bit 像素数据必须经过此变换：

```c
static __inline uint16_t PIXEL(uint16_t c) {
    uint16_t r = (c >> 11) & 0x1F;   // 提取 R[4:0]
    uint16_t g = (c >>  5) & 0x3F;   // 提取 G[5:0]
    uint16_t b =  c        & 0x1F;   // 提取 B[4:0]
    // 按 PCB 映射重组: {G[5:1], R[4:0], G[0], B[4:0]}
    return ((g >> 1) << 11) | (r << 6) | ((g & 1) << 5) | b;
}
```

### 验证方法

发送 `calib` 命令，屏幕分为两部分：
- **上半**：8 个原色条（黑红绿蓝黄青品白），应全部正确
- **下半**：4×4 位行走网格（bit0-15 逐一点亮），用于诊断 PCB 位映射

当前 calib 结果：**8/8 全部通过** ✅

### 相关配置

```c
MADCTL = 0x20   // BGR=0 (RGB 顺序), MV=1 (横屏)
PIXFMT = 0x55   // 16-bit RGB565
INVON  = 关闭   // 注意：不要开启，会反转所有颜色
```

> 详细调试过程见 [记忆/lcd_color_debug.md](https://github.com/pnnooy/AI-company/blob/main/.claude/projects/d--AI-company/memory/lcd_color_debug.md)（注：此文件在本地 `.claude` 目录中）

## 状态机设计

```
                   触摸/NFC
   IDLE ────────────────────→ ACTIVE ────────────→ INTERACT
    ↑                           ↑       30s无交互     │
    │ 5min无交互                └────────────────────┘
    ↓                                                  10s无交互
  SLEEP ←── 姿态倾倒触发 ALERT ──→ 回到之前状态
```

## 表情系统

### 素材规格

| 参数 | 值 |
|------|-----|
| 单帧尺寸 | 80×80 像素 |
| 颜色格式 | RGB565 (R=5bit, G=6bit, B=5bit, 16-bit/像素) |
| 背景色 | 纯黑 #000000 (0x0000) |
| 输出格式 | C 语言 const uint16_t 数组 |
| 最大帧数 | 3 帧/表情 |
| 缩放方式 | 运行时 Nearest-Neighbor 2x 放大 |

### 8 组表情 14 帧

| 表情 | 帧数 | 动画间隔 | 说明 |
|------|------|----------|------|
| normal | 1 | — | 静态中性脸 |
| happy | 3 | 500ms | 眨眼+笑嘴 |
| focus | 2 | 500ms | 微眯眼（可加眼镜） |
| angry | 1 | — | 倒眉+三角眼 |
| sleep | 2 | 1000ms | 闭眼慢速呼吸感 |
| surprise | 1 | — | 大眼+O嘴 |
| sad | 2 | 400ms | 泪滴闪烁 |
| love | 2 | 300ms | 爱心眼+腮红 |

### 生成素材

```bash
# 将 PNG 素材放到 firmware/Assets/ 目录
# 命名格式: emo_{表情名}_f{帧号}.png  如 emo_happy_f0.png

# 生成 C 数组文件
python tools/make_assets.py --size 80

# 如需反色 (黑白反转)
python tools/make_assets.py --size 80 --invert
```

## 已知问题

| 问题 | 严重度 | 详情 |
|------|--------|------|
| HSE 晶振未起振 | 中 | 只能跑 HSI 64MHz，性能损失约 11% |
| 表情粉色偏青 | 低 | --invert 副作用，更新 PNG 素材可解决 |
| CH340 自动下载 | 低 | 用 SSCOM 并关 DTR/RTS 可规避 |
| 触摸 HOLD 阈值偏高 | 低 | 当前 1s，建议降至 700ms |
| 触摸 DOUBLE 难以触发 | 低 | 需要两人同时触，实用性低 |
| NFC 读卡 REQA 失败 | 高 | SPI 链路已稳定(2MHz)，CheckCard 正常判卡，但 GetCardUID 的 REQA 始终返回 len=0，疑似 RF 发射/接收或 MFRC522 芯片硬件问题 |

## 开发管线

### 修改代码流程

1. 打开 Keil 工程 `firmware/desktop_assistant/MDK-ARM/desktop_assistant.uvprojx`
2. 编辑源文件（`firmware/Drivers/` 或 `firmware/App/`）
3. F7 编译 → 确保 0 Error 0 Warning
4. F8 烧录 (Fire-Debugger SWD)
5. SSCOM 串口验证

### CubeMX 重生成注意事项

CubeMX 重新生成代码会覆盖以下文件，需手动恢复：
1. `tim.c`: Period=255, OCPolarity=LOW
2. `main.c` SystemClock_Config: HSE→HSI
3. `main.c` USER CODE 区域新增代码需保留

### 代码规范

- 文件名：`snake_case`（如 `ili9341_fsmc.c`）
- 函数名：模块前缀 + PascalCase（如 `ILI9341_DrawPixel`）
- 宏/常量：UPPER_SNAKE_CASE（如 `COLOR_BLACK`）
- 外设句柄：使用 CubeMX 生成的 `hspi1`, `htim3`, `huart1` 等
- 禁止 `HAL_Delay()`，统一用 `HAL_GetTick()` 非阻塞计时
- 每个驱动模块独立 .c/.h 文件

### 添加新表情素材

> 详细任务书见 `开发文档/Expression_Task_Brief.md`

1. 绘制 80×80 PNG 图片（黑底，圆润可爱风）
2. 按 `emo_{name}_f{frame}.png` 命名放入 `firmware/Assets/`
3. 运行 `python tools/make_assets.py --size 80` 生成 C 数组
4. 如需动画多帧，在 `tools/make_assets.py` 的 `EXPRESSIONS` 字典中配置帧数和间隔
5. 重新编译烧录

## Git 工作流

- 主分支：`main`
- 功能开发：`feature/<功能名>` 分支 → PR 合入 main
- 五人协作，贡献者：pnnooy

```bash
git clone https://github.com/pnnooy/AI-company.git
git checkout -b feature/my-feature
# ... 开发 ...
git add <files>
git commit -m "描述改动"
git push origin feature/my-feature
# 然后在 GitHub 上创建 Pull Request
```

## 硬件连接速查

### SWD 烧录接口 (Fire-Debugger)

| 调试器 | 开发板 |
|--------|--------|
| SWCLK | PA14 (SWCLK) |
| SWDIO | PA13 (SWDIO) |
| GND | GND |
| 3.3V | 3.3V |

### 外部模块接线

```
MPU6050:
  VCC → 3.3V    GND → GND
  SCL → PA11     SDA → PA12

MFRC-522:
  VCC → 3.3V    GND → GND
  SCK → PA5     MISO → PA6    MOSI → PA7
  CS  → PA4     RST  → PA3

TTP223 (左):
  VCC → 3.3V    GND → GND
  OUT → PC4

TTP223 (右):
  VCC → 3.3V    GND → GND
  OUT → PC5
```

## 许可证

MIT License
