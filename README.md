# 🤖 皮皮 PiPi — 智能桌面陪伴宠物

> 一个会笑、会生气、会识别你表情的桌面 AI 陪伴机器人，陪你度过大学时光。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![MCU](https://img.shields.io/badge/MCU-STM32F103VET6-03234B?logo=stmicroelectronics)](https://www.st.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)](https://python.org)
[![Web](https://img.shields.io/badge/Web-Dashboard-teal)](http://localhost:5000)

**🎬 [在线展示页 (Showcase)](https://pnnooy.github.io/AI-company/showcase/index.html)** — 交互式功能演示，无需硬件即可体验所有功能。

---

## 它能做什么？

```
         🎭 动态表情              🎨 氛围灯光
        8种表情 × 3帧动画        RGB 全彩呼吸灯
         
         ✋ 触摸互动              🫀 姿态感应
      左右双触摸传感器        MPU6050 六轴加速度
      
         📸 情绪识别               💬 AI 对话
      摄像头人脸+情绪分析      多后端 LLM 智能聊天
      
         📳 NFC 喂养              🌐 Web 控制台
      刷卡触发互动反馈        Flask 仪表盘实时操控
```

**皮皮**是一台运行在 STM32F103VET6 微控制器上的桌面机器人，通过 LCD 屏幕展现丰富的动态表情，配合 RGB 氛围灯、电容触摸、六轴姿态感应和 NFC 读卡实现多模态交互。PC 端运行 AI 大脑，通过摄像头识别用户的情绪，接入大语言模型实现智能对话，所有功能都可以通过 Web 仪表盘实时查看和控制。

---

## 🎬 在线展示

无需下载代码或连接硬件，打开浏览器即可体验全部功能：

👉 **[pnnooy.github.io/AI-company/showcase/](https://pnnooy.github.io/AI-company/showcase/index.html)**

展示页包含 13 个交互式板块：虚拟表情、对话演示、触摸交互、加速度感应、摄像头情绪识别、NFC 喂养、系统架构图、技术栈、团队介绍等。支持键盘导航（方向键翻页）。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      硬件层 (STM32F103VET6)                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐│
│  │ LCD  │ │RGB灯 │ │ 触摸 │ │MPU   │ │ NFC  │ │  UART    ││
│  │3.2"  │ │PWM   │ │TTP223│ │6050  │ │RC522 │ │ 115200   ││
│  │FSMC  │ │TIM3  │ │EXTI  │ │软I2C │ │SPI   │ │  bps     ││
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └────┬─────┘│
└────────────────────────────────────────────────────┼───────┘
                                                     │ UART
┌────────────────────────────────────────────────────┼───────┐
│                      PC 端 (Python)                 │       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┴─────┐│
│  │ 串口通信  │ │ AI 引擎  │ │ 摄像头    │ │  Web 仪表盘   ││
│  │ UART协议 │ │ 状态机   │ │ 人脸检测  │ │  Flask API   ││
│  │ 二进制帧  │ │ LLM客户端│ │ 表情识别  │ │  实时控制     ││
│  │ CRC-8    │ │ 角色设定  │ │ ONNX模型  │ │  对话界面     ││
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘│
└───────────────────────────────────────────────────────────┘
```

**双系统通过 UART 串口通信**（115200 bps，二进制协议 + CRC-8 校验）：

- **下位机 (STM32)**：负责硬件驱动、表情渲染、传感器轮询、灯光控制
- **上位机 (Python)**：负责 AI 决策、情绪识别、LLM 对话、Web 服务

---

## 🚀 快速开始

### 硬件需求

| 模块 | 型号 | 连接方式 |
|------|------|----------|
| 主控板 | 野火·指南者 STM32F103VET6 | — |
| 显示屏 | 3.2" ILI9341 TFT LCD | 板载 FSMC 并口 |
| 烧录器 | Fire-Debugger (CMSIS-DAP) | SWD (PA13/PA14) |
| 姿态传感器 | MPU6050 六轴模块 | 软 I2C (PA11/PA12) |
| NFC 读卡器 | MFRC-522 RFID | SPI1 (PA4-7, PA3) |
| 触摸传感器 | TTP223 电容触摸 ×2 | EXTI (PC4, PC5) |
| RGB LED | 共阳 RGB 模块 | TIM3 PWM (PB5/PB0/PB1) |
| 串口 | CH340 USB-TTL | USART1 (PA9/PA10) |

> ⚠️ **重要引脚冲突**：FSMC 的 NADV 与硬件 I2C1_SDA 共用 PB7，因此 **不能使用硬件 I2C1**。MPU6050 已改用软件 I2C 驱动（PA11/PA12），修改代码时请勿开启硬件 I2C1。

### 1. 固件编译与烧录

**环境准备：**

- **Keil MDK-ARM V5** (V5.06 update 6+) + 芯片包 `Keil.STM32F1xx_DFP.2.4.1`
- Fire-Debugger 烧录器（CMSIS-DAP 兼容，其他 DAP-Link 亦可）

**编译烧录：**

```bash
git clone https://github.com/pnnooy/AI-company.git
cd AI-company
```

1. 打开 `firmware/desktop_assistant/MDK-ARM/desktop_assistant.uvprojx`
2. Keil 中按 **F7** 编译（应 0 Error 0 Warning）
3. 连接 Fire-Debugger，按 **F8** 烧录

> 💡 当前使用 HSI 内部 64MHz 时钟（HSE 外部晶振暂未起振，约 11% 性能损失）。

### 2. PC 后端启动

**环境要求：** Python 3.9+

```bash
cd pc_backend
pip install -r requirements.txt

# 启动全部功能
python main.py --port COM6 --baud 115200

# 仅启动 Web 仪表盘（无串口/摄像头）
python main.py --no-camera --port COM6

# 调试模式（详细日志）
python main.py --debug
```

启动后访问 **http://localhost:5000** 打开 Web 仪表盘。

**依赖项：**

| 包 | 用途 |
|----|------|
| `pyserial` | 串口通信 |
| `opencv-python` | 摄像头 + 人脸检测 |
| `flask` | Web API + 仪表盘 |
| `numpy` | 数据处理 |
| `deepface` | 情绪识别（可选，帧速更优） |

### 3. 串口连接测试

1. 打开 `串口调试工具SSCOM/sscom.5.13.1.exe`
2. 设置 COM6, 115200-8-N-1
3. **关闭 DTR 和 RTS**（防止 CH340 自动复位）
4. 按下开发板 RESET 键
5. 应看到启动信息 `Desktop Assistant Ready`
6. 输入 `help` 查看所有命令

---

## 📖 使用指南

### 串口命令

通过串口工具发送文本命令（以 `\r\n` 结尾）：

| 命令 | 功能 | 示例 |
|------|------|------|
| `led R G B` | 设置 RGB 灯颜色 (0-255) | `led 255 128 0` |
| `mpu` | 读取加速度/角速度/姿态角 | `mpu` |
| `mpuon` / `mpuoff` | 开启/关闭 MPU6050 轮询 | `mpuoff` |
| `emo <name>` | 切换表情 | `emo happy` |
| `lcd R G B` | LCD 全屏填充纯色 | `lcd 255 0 0` |
| `calib` | LCD 颜色校准测试图案 | `calib` |
| `state` | 查看当前状态机状态 | `state` |
| `nfc` | 手动读卡 | `nfc` |
| `nfcdbg` | 导出 MFRC522 全部寄存器 | `nfcdbg` |
| `nfcreset` | 软复位 MFRC522 | `nfcreset` |
| `help` | 列出所有可用命令 | `help` |

**可用表情：** `normal` `happy` `focus` `angry` `sleep` `surprise` `sad` `love`

### Web 仪表盘

启动 PC 后端后访问 `http://localhost:5000`：

- 📊 **实时状态**：机器人当前表情、情绪值、灯光颜色
- 🎭 **表情控制**：点击切换 8 种动态表情（3 帧动画）
- 💬 **AI 对话**：与皮皮聊天，支持多 LLM 后端
- 📸 **摄像头预览**：实时人脸检测 + 情绪识别画面
- 💡 **LED 控制**：远程调节 RGB 氛围灯
- 📈 **调试信息**：串口帧统计、LLM 响应记录、系统日志

### 物理交互

| 交互方式 | 触发条件 | 机器人反应 |
|----------|----------|------------|
| **左触摸** | 单击左触摸传感器 | 表情切换为 happy，灯光暖色 |
| **右触摸** | 单击右触摸传感器 | 表情切换为 focus，灯光冷色 |
| **长按** | 持续触摸 >1s | 进入 INTERACT 状态 |
| **摇动** | 加速度突变 | ALERT 状态，表情 surprise |
| **倾倒** | 倾角 >60° | ALERT 状态，表情 sad |
| **NFC 刷卡** | 靠近 MIFARE 卡 | 触发喂养互动（4 级强度） |

### 情绪识别

PC 摄像头自动检测用户：
- **人脸检测**：Haar Cascade，每秒检测一次
- **情绪识别**：DeepFace（TensorFlow）或 ONNX FER+ 模型双后端
- **识别人脸情绪**：neutral / happy / sad / angry / surprise
- **用户出现/离开**：自动调整机器人状态
- **情绪联动**：用户笑 → 皮皮变 happy，用户难过 → 皮皮变 sad

---

## 📁 项目结构

```
AI-company/
├── README.md                          # 本文件
├── CLAUDE.md                          # Claude Code 开发规范
├── .gitignore
│
├── firmware/                          # 🔌 STM32 固件
│   ├── desktop_assistant/             # CubeMX Keil 工程
│   │   ├── Core/Src/                  # HAL 初始化 (main, tim, spi, fsmc...)
│   │   └── MDK-ARM/                   # Keil 项目文件 (.uvprojx)
│   ├── Drivers/                       # BSP 驱动层
│   │   ├── Inc/ & Src/               # 7 个硬件驱动
│   │   │   ├── ili9341_fsmc          # LCD 显示 (FSMC 8080)
│   │   │   ├── rgb_led               # RGB LED (PWM)
│   │   │   ├── mpu6050_hal           # MPU6050 姿态 (软件 I2C)
│   │   │   ├── soft_i2c              # 软件 I2C 实现
│   │   │   ├── rc522_spi             # NFC 读卡 (SPI)
│   │   │   ├── touch_sensor          # 电容触摸 (EXTI)
│   │   │   └── uart_comm             # 串口通信协议
│   ├── App/                           # 应用层
│   │   ├── main_fsm                   # 主状态机
│   │   ├── expression_engine          # 表情引擎
│   │   ├── expression_types.h         # 表情枚举
│   │   └── expression_assets          # 表情素材数据
│   └── Assets/                        # 表情 PNG 源文件 + faceset/
│
├── pc_backend/                        # 🧠 PC 端 AI 引擎
│   ├── main.py                        # 主入口 (多线程协调)
│   ├── web_api.py                     # Flask Web API
│   ├── requirements.txt               # Python 依赖
│   ├── comm/
│   │   ├── uart_link.py               # 串口链接管理 (五状态帧解析器)
│   │   └── protocol.py                # v2.0 二进制协议定义
│   ├── ai_engine/
│   │   ├── state_machine.py           # AI 情绪状态机
│   │   ├── rules.py                   # 规则决策引擎
│   │   ├── llm_client.py              # 多后端 LLM 客户端
│   │   └── character.py               # 皮皮角色设定
│   ├── camera/
│   │   ├── face_detect.py             # 人脸检测 + 情绪识别
│   │   └── emotion-ferplus-8.onnx     # ONNX 情绪模型 (需下载)
│   ├── static/                        # 前端静态资源
│   │   ├── css/dashboard.css          # 仪表盘样式 (teal 主题)
│   │   ├── js/dashboard.js            # 仪表盘逻辑
│   │   └── img/                       # 8×3 表情帧图片
│   ├── templates/
│   │   └── index.html                 # 仪表盘 HTML
│   └── tests/                         # 测试脚本
│
├── showcase/                          # 🎬 在线展示页
│   ├── index.html                     # 交互式展示页 (13 板块)
│   └── team_photo/                    # 团队照片
│
├── tools/                             # 🛠️ 素材工具
│   ├── make_assets.py                 # PNG → C 数组批量转换
│   └── png2rgb565.py                  # 单张转换
│
├── 开发文档/                           # 📚 中文开发文档
│   ├── Project_Brief.md               # 项目规范书
│   ├── CubeMX_Config_Guide.md         # CubeMX 配置指南
│   ├── Expression_Task_Brief.md       # 表情素材制作指南
│   ├── Protocol_Test_Guide.md         # 协议测试指南
│   ├── Complete_Test_Guide.md         # 完整测试指南
│   └── Team_Tasks/                    # 任务分工文档
│
├── 硬件资料/                           # 📋 硬件参考 (gitignored)
├── 视频/                              # 🎥 演示视频素材 (gitignored)
└── 串口调试工具SSCOM/                  # 🔧 团队统一串口工具
```

---

## 🎭 表情系统

皮皮的表情是项目的核心亮点。每帧 80×80 像素，运行时 2 倍放大至 160×160 显示在 3.2" LCD 上。

### 当前表情列表

| 表情 | 英文名 | 帧数 | 动画间隔 | 触发条件 |
|------|--------|------|----------|----------|
| 😊 开心 | happy | 3 | 500ms | 触摸互动、正面情绪识别 |
| 😐 普通 | normal | 3 | — | 默认状态、空闲 |
| 🤔 专注 | focus | 3 | 500ms | 右触摸、学习模式 |
| 😠 生气 | angry | 3 | — | 抖动、负面情绪 |
| 😴 睡觉 | sleep | 3 | 1000ms | 5 分钟无交互自动休眠 |
| 😲 惊讶 | surprise | 3 | — | 加速度突变 |
| 😢 伤心 | sad | 3 | 400ms | 倾倒检测、负面情绪 |
| 🥰 喜欢 | love | 3 | 400ms | NFC 喂养、强正面情绪 |

**规格：** 80×80 PNG → RGB565 C 数组 → 2× Nearest-Neighbor 缩放 → 160×160 LCD 显示

### 自定义表情

```bash
# 1. 绘制 80×80 PNG（黑底），命名 emo_{name}_v{1-3}.png
# 2. 放入 firmware/Assets/faceset/
# 3. 生成 C 数组
python tools/make_assets.py --size 80
# 4. 在 firmware/App/expression_types.h 添加枚举
# 5. 重新编译烧录
```

---

## 🔧 开发指南

### 环境要求

| 工具 | 版本 |
|------|------|
| Keil MDK-ARM | V5.06 update 6+ |
| 芯片包 | Keil.STM32F1xx_DFP.2.4.1 |
| STM32CubeMX | 6.x (仅外设配置重生成时需要) |
| Python | 3.9+ |
| 烧录器 | Fire-Debugger 或 CMSIS-DAP 兼容 |
| 串口工具 | 仓库自带 SSCOM V5.13.1 |

### 代码规范

- **文件命名**：`snake_case`（如 `ili9341_fsmc.c`）
- **函数命名**：`ModulePrefix_PascalCase`（如 `ILI9341_DrawPixel`）
- **宏/常量**：`UPPER_SNAKE_CASE`（如 `COLOR_BLACK`）
- **外设句柄**：使用 CubeMX 生成的 `hspi1`, `htim3`, `huart1`
- **禁止阻塞**：统一用 `HAL_GetTick()` 非阻塞计时，不得使用 `HAL_Delay()`
- **LCD 写像素**：必须通过 `PIXEL()` 宏补偿 PCB 布线交叉（详见下方 LCD 说明）
- **每个驱动**：独立 `.c` + `.h` 文件，头文件使用 `#ifndef` / `#define` 防护

### 开发流程

```bash
# 固件开发
1. 编辑 firmware/Drivers/ 或 firmware/App/ 源码
2. Keil F7 编译 → 确保 0 Error 0 Warning
3. Keil F8 烧录
4. SSCOM 串口验证

# PC 后端开发
1. 编辑 pc_backend/ 源码
2. 重启 python main.py
3. 浏览器访问 localhost:5000 验证

# Git 工作流
git checkout -b feature/my-feature
git commit -m "feat(firmware): 描述改动"
git push origin feature/my-feature
# 创建 Pull Request → main（main 分支有保护，禁止直接推送）
```

### CubeMX 重生成注意事项

CubeMX 重新生成代码会覆盖以下文件，必须手动恢复：

1. `Core/Src/tim.c`：恢复 `Period=255`, `OCPolarity=LOW`
2. `Core/Src/main.c`：`SystemClock_Config` 中 HSE → HSI（直到外部晶振修复）
3. `Core/Src/spi.c`：恢复 MFRC522 初始化中的分频器 (`SPI_BAUDRATEPRESCALER_32`)
4. `Core/Src/main.c`：确保所有 USER CODE 区域内容保留
5. MDK-ARM `.uvprojx`：重新添加 `firmware/Drivers/Inc` 和 `firmware/App` 的 include 路径

> 💡 **最佳实践**：避免 CubeMX 重生成，除非需要添加新外设。尽可能在代码中直接修改外设配置。

---

## 🖥️ LCD 颜色校准

### 问题

野火指南者 PCB 上 STM32 FSMC 与 ILI9341 的 **数据线存在交叉**：D[15:11] 与 D[10:6] 两组 5-bit 通道互换，导致 RGB565 中的 R 和 G 通道高 5 位发生交换。

### 补偿宏

所有通过 FSMC 写入 ILI9341 的 16-bit 像素数据必须经过 `PIXEL()` 变换（定义在 `ili9341_fsmc.c`）：

```c
static __inline uint16_t PIXEL(uint16_t c) {
    uint16_t r = (c >> 11) & 0x1F;   // 提取 R[4:0]
    uint16_t g = (c >>  5) & 0x3F;   // 提取 G[5:0]
    uint16_t b =  c        & 0x1F;   // 提取 B[4:0]
    // 按 PCB 映射重组: {G[5:1], R[4:0], G[0], B[4:0]}
    return ((g >> 1) << 11) | (r << 6) | ((g & 1) << 5) | b;
}
```

### 验证

发送 `calib` 命令，屏幕显示 8 个原色条 + 4×4 位行走网格。当前结果：**8/8 全部通过** ✅

---

## ⚠️ 已知问题

| 问题 | 状态 | 影响 | 备注 |
|------|------|------|------|
| HSE 晶振未起振 | 🔴 待修复 | 只能跑 HSI 64MHz，性能损失 ~11% | PCB 级问题，待排查 |
| NFC 读卡 REQA 失败 | 🟡 调试中 | 无法读取卡号，但刷卡检测正常 | SPI 链路稳定(2MHz)，疑似 RF 电路或芯片问题 |
| 触摸 HOLD 阈值偏高 | 🟢 低优先级 | 需按住 1s 才触发 | 可调节阈值至 700ms |
| 触摸 DOUBLE 难触发 | 🟢 低优先级 | 需同时双点触 | 实用性低，可忽略 |

---

## 👥 团队成员

| 角色 | 姓名 | 主要贡献 |
|------|------|----------|
| 🎯 项目统筹 | 韩宇飞 | 系统架构、LCD 驱动、软 I2C、主状态机、LLM 对话、情绪识别、Web API、展示页、视频 |
| 🔧 固件开发 | 李哲 | MPU6050、触摸传感器、NFC 驱动、UART 协议、AI 状态机、Keil 工程维护 |
| 🔌 硬件 & 测试 | 姜新晨 | RGB LED 驱动、硬件选型接线、外设调试、测试验证、素材生成脚本、文档 |
| 🎨 前端 & 设计 | 李飞翰 | 表情引擎、表情素材绘制、聊天界面、Dashboard 面板、展示页特效、前端设计 |

上海交通大学 · 2025-2026

---

## 📄 许可证

MIT License

Copyright (c) 2025-2026 PiPi Team
