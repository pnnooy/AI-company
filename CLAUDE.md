# CLAUDE.md - 桌面学术助手机器人 (Desktop Academic Assistant Robot)

## 项目概述
面向大学生的桌面级学术助手机器人，基于 STM32F103VET6 (野火指南者开发板)。
通过 LCD 表情、RGB 氛围灯、电容触摸、六轴姿态传感器、NFC 卡片实现多模态桌面交互。

## 开发环境
- **MCU**: STM32F103VET6 (Cortex-M3, 72MHz)
- **配置工具**: STM32CubeMX (生成 HAL 初始化代码)
- **IDE**: Keil MDK-ARM V5
- **HAL 库**: STM32Cube_FW_F1
- **代码标准**: C99+, 使用 HAL 库面向对象封装
- **PC 端**: Python 脚本用于串口通信与 AI 决策
- **串口工具**: SSCOM (COM6, 115200-8-N-1, 关 DTR/RTS)
- **烧录器**: Fire-Debugger (野火 DAP, CMSIS-DAP 标准)

## 硬件拓扑与引脚映射 (核心模块)

| 模块 | 设备 | 协议 | 引脚 |
|------|------|------|------|
| 中枢通信 | CH340 USB-TTL | USART1 | PA9(TX), PA10(RX) **板载** |
| 视觉呈现 | 3.2" ILI9341 LCD | FSMC 8080 NE1 | 板载并口插槽 |
| 氛围指示 | RGB LED (板载) | TIM3 PWM | PB5(R-CH2), PB0(G-CH3), PB1(B-CH4) |
| 左触摸 | TTP223-A | EXTI | PC4 (上升沿, EXTI4) |
| 右触摸 | TTP223-B | EXTI | PC5 (上升沿, EXTI9_5) |
| 姿态传感器 | MPU6050 | 软I2C | PA11(SCL), PA12(SDA) |
| NFC 读卡 | MFRC-522 | SPI1 | PA5(SCK), PA6(MISO), PA7(MOSI), PA4(CS), PA3(RST) |

> **⚠️ 关键**: FSMC NADV 与 I2C1_SDA 共用 PB7, **不可使用硬件 I2C1**。MPU6050 使用软件 I2C (PA11/PA12)。详见野火PDF第47章。

## CubeMX 底层配置基准 (必须遵守)
- MCU: STM32F103VET6
- 时钟: **当前 HSI 64MHz** (HSE 晶振未起振, 待排查)。HSE 修复后切回 72MHz。
- 调试: Serial Wire (SWD)
- 串口: USART1, 115200 bps, 8-N-1
- TIM3: Partial Remap, CH2(PB5)/CH3(PB0)/CH4(PB1) PWM, Period=255, Prescaler=1999, OCPolarity=LOW
- FSMC: NE1, 16bit, A23, LCD Interface
- I2C1: **禁用** (与FSMC冲突)。用软I2C替代。
- SPI1: Master, /8=9MHz, CPOL=Low, CPHA=1Edge, NSS=Soft
- 中断: EXTI4(PC4)+EXTI9_5(PC5), 优先级低于 SysTick
- 禁止: 不使用 `HAL_Delay` 死延时, 统一用 `HAL_GetTick()` 非阻塞

## CubeMX 重生成注意事项
CubeMX GENERATE CODE 会覆盖以下配置，每次生成后需手动修复:
1. `tim.c`: Period=255, OCPolarity=LOW
2. `main.c` SystemClock_Config: HSE→HSI
3. `main.c` USER CODE 区域保留 (不会被覆盖, 但新增的需确认)
4. `.uvprojx`: include路径和文件组需重新添加 (如用新工程)

## 项目结构
```
d:/AI_company/
├── CLAUDE.md              # 本文件 - 项目总规范
├── .gitignore
├── 开发文档/
│   ├── Project_Brief.md          # 详细项目规范书 V2.1
│   ├── Development_Plan.md       # 开发计划
│   ├── CubeMX_Config_Guide.md    # CubeMX 配置指南
│   ├── Expression_Task_Brief.md  # 表情素材任务书
│   └── Test_Report_001.md        # 测试报告
├── 硬件资料/
│   ├── 硬件清单05-01.docx
│   └── 【野火】零死角玩转STM32—F103指南者.pdf
├── firmware/
│   ├── desktop_assistant/       # CubeMX 生成的 Keil 工程
│   │   ├── Core/                # HAL 初始化 + main.c
│   │   ├── Drivers/             # HAL 库 (CMSIS + STM32F1xx_HAL)
│   │   └── MDK-ARM/             # Keil 工程 (.uvprojx)
│   ├── Drivers/                 # 自定义 BSP 驱动
│   │   ├── Inc/                 # 头文件
│   │   └── Src/                 # 源文件 (7个驱动)
│   ├── App/                     # 应用层
│   └── Assets/                  # 表情素材
├── tools/
│   └── png2rgb565.py            # PNG→RGB565 转换工具
└── .claude/
```

## 代码规范
- 文件名: `snake_case` (e.g., `ili9341_fsmc.c`, `mpu6050_hal.c`)
- 函数名: 模块前缀 + PascalCase (e.g., `ILI9341_DrawPixel`, `MPU6050_ReadData`)
- 宏/常量: UPPER_SNAKE_CASE (e.g., `EMO_NORMAL`, `TICK_INTERVAL_MS`)
- 外设句柄: 使用 CubeMX 生成的 `hspi1`, `htim3`, `huart1` 等
- 每个驱动模块独立 .c/.h 文件, 头文件使用 `#ifndef` 防护

## 编译与烧录
- 打开 `firmware/desktop_assistant/MDK-ARM/desktop_assistant.uvprojx`
- Keil MDK 编译: F7 (Build), F8 (Download)
- 烧录器: Fire-Debugger (野火 DAP, CMSIS-DAP 标准)
- MicroLIB 已启用 (printf 支持)

## Git 仓库
- Remote: `https://github.com/pnnooy/AI-company`
- 分支: main
- 贡献者: pnnooy (hanyufei24@sjtu.edu.cn)
- 五人协作: feature 分支 + PR 合入 main

## 记忆体系
项目记忆存储在 `~/.claude/projects/d--AI-company/memory/` 目录下。
详见 MEMORY.md 索引文件。
