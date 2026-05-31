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

## 硬件拓扑与引脚映射 (核心模块)

| 模块 | 设备 | 协议 | 引脚 |
|------|------|------|------|
| 中枢通信 | CH340 USB-TTL | USART1 | PA9(TX), PA10(RX) |
| 视觉呈现 | 3.2" ILI9341 LCD | FSMC 8080 | 板载并口插槽 |
| 氛围指示 | RGB LED | TIM3 PWM | PB5(R), PB0(G), PB1(B) |
| 左触摸 | TTP223-A | EXTI | PC4 (上升沿) |
| 右触摸 | TTP223-B | EXTI | PC5 (上升沿) |
| 姿态传感器 | MPU6050 | I2C1 | PB6(SCL), PB7(SDA) |
| NFC 读卡 | MFRC-522 | SPI1 | PA5(SCK), PA6(MISO), PA7(MOSI), PA4(CS), PA3(RST) |

## CubeMX 底层配置基准 (必须遵守)
- MCU: STM32F103VET6
- 时钟: HSE 外部晶振 → PLL → 72MHz 系统时钟
- 调试: Serial Wire (SWD), 防止芯片锁死
- 串口: USART1, 115200 bps, 8-N-1
- 中断: EXTI 优先级低于 SysTick, 避免阻塞主循环
- 禁止: 不使用 `Soft_Delay` 死延时, 统一用 `HAL_GetTick()` 非阻塞

## 项目结构
```
d:/AI_company/
├── CLAUDE.md              # 本文件 - 项目总规范
├── 开发文档/
│   └── Project_Brief.md   # 详细项目规范书 V2.1
├── 硬件资料/
│   ├── 硬件清单05-01.docx/pdf  # 硬件物料清单
│   └── 【野火】零死角玩转STM32—F103指南者.pdf  # 823页参考书
├── firmware/              # STM32 固件工程 (待创建)
│   ├── Core/              # HAL 初始化 + main.c
│   ├── Drivers/           # BSP 驱动 (ILI9341, MPU6050, RC522)
│   ├── App/               # 应用层 (表情引擎, 状态机, 通信协议)
│   └── MDK-ARM/           # Keil 工程文件
├── tools/                 # PC 端工具脚本
│   └── serial_bridge.py   # Python 串口桥接
└── .claude/               # Claude Code 配置
    └── settings.json
```

## 代码规范
- 文件名: `snake_case` (e.g., `ili9341_driver.c`, `mpu6050_hal.c`)
- 函数名: 模块前缀 + PascalCase (e.g., `ILI9341_DrawPixel`, `MPU6050_ReadAccel`)
- 宏/常量: UPPER_SNAKE_CASE (e.g., `EMO_NORMAL`, `TICK_INTERVAL_MS`)
- 外设句柄: 使用 CubeMX 生成的 `hspi1`, `hi2c1`, `huart1` 等
- 每个驱动模块独立 .c/.h 文件, 头文件使用 `#ifndef` 防护

## 编译与烧录
- 打开 `firmware/MDK-ARM/` 下的 `.uvprojx` 工程文件
- Keil MDK 编译: F7 (Build), F8 (Download)
- 烧录器: Fire-Debugger (野火 DAP, CMSIS-DAP 标准)

## 记忆体系
项目记忆存储在 `~/.claude/projects/d--AI-company/memory/` 目录下。
详见 MEMORY.md 索引文件。
