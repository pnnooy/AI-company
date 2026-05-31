# 桌面学术助手机器人 - 开发计划 V1.0

## 项目时间线: 2026-05-21 启动

**当前状态**: 阶段 1-2 部分完成, 3 个模块已验证通过。

---

## 阶段 0: 环境搭建 ✅ 完成

### 0.1 开发工具安装
- [x] 安装 Keil MDK-ARM V5 (V5.06 update 6)
- [x] 安装 STM32F1 芯片包 (Keil.STM32F1xx_DFP.2.4.1)
- [x] 安装 STM32CubeMX
- [x] 安装 Fire-Debugger (野火 DAP) 驱动
- [x] 板载 CH340 USB-TTL 驱动正常

### 0.2 硬件连接验证
- [x] 烧录链路: Fire-Debugger → SWD ✅
- [x] 串口: 板载 USB 转串口 (CH340), COM6 ✅
- [x] 板载 RGB LED 可控制 ✅

---

## 阶段 1: CubeMX 基础工程 🔄 进行中

### 1.1 CubeMX 配置
- [x] MCU: STM32F103VET6 (LQFP100)
- [x] RCC: 当前 HSI 64MHz (HSE 未起振, 待排查)
- [x] SYS: Debug = Serial Wire (SWD)
- [x] USART1: 115200, 8-N-1, PA9/PA10
- [x] I2C1: **禁用** (FSMC冲突, 改用软I2C PA11/PA12)
- [x] SPI1: Master, /8=9MHz, PA5/PA6/PA7, PA4(CS), PA3(RST)
- [x] TIM3: CH2(PB5)/CH3(PB0)/CH4(PB1) PWM, Period=255, Prescaler=1999, Partial Remap
- [x] FSMC: NE1, 16bit, A23, LCD Interface
- [x] GPIO: PA3(RC522 RST), PA4(RC522 CS), PC4(EXTI4), PC5(EXTI5)
- [x] NVIC: EXTI4 prio=5, EXTI9_5 prio=5, USART1 prio=3

### 1.2 生成与编译
- [x] 生成 Keil MDK-ARM V5 工程 ✅
- [x] 编译 0 Error 0 Warning ✅
- [x] 烧录验证 ✅

---

## 阶段 2: 硬件驱动层开发 🔄 进行中

### 2.1 UART 通信框架 ✅
**文件**: `Drivers/Src/uart_comm.c/.h`

- [x] printf 重定向 (MicroLIB) ✅
- [x] 环形缓冲区接收 ✅
- [x] 二进制帧协议 + CRC ✅
- [x] 文本命令解析 (led/mpu/state/help) ✅
- [x] HAL_UART_RxCpltCallback ✅

### 2.2 ILI9341 LCD 驱动 ⏳
**文件**: `Drivers/Src/ili9341_fsmc.c/.h`

- [x] FSMC 8080 接口底层 ✅
- [x] 位图显示函数 ✅
- [ ] 待表情素材集成后测试

### 2.3 RGB LED 驱动 ✅
**文件**: `Drivers/Src/rgb_led.c/.h`

- [x] TIM3 PWM CH2/CH3/CH4, 共阳LED, OCPolarity=LOW ✅
- [x] RGB_SetColor / RGB_Breathe / RGB_Off ✅
- [x] 串口命令 `led R G B` 控制正常 ✅

### 2.4 MPU6050 驱动 ✅
**文件**: `Drivers/Src/mpu6050_hal.c/.h` + `Drivers/Src/soft_i2c.c/.h`

- [x] 软件 I2C (PA11=SCL, PA12=SDA) ✅
- [x] 初始化: ±2g, ±250°/s, 200Hz ✅
- [x] SHAKE + FALL 检测 ✅
- [x] 串口命令 `mpu` ✅
- [x] FSMC与I2C1冲突已确认并解决 ✅

### 2.5 MFRC-522 NFC 驱动 ⏳
**文件**: `Drivers/Src/rc522_spi.c/.h`

- [x] 驱动代码已写完
- [ ] 待接线测试

### 2.6 TTP223 触摸驱动 ✅
**文件**: `Drivers/Src/touch_sensor.c/.h`

- [x] EXTI 中断链路 ✅
- [x] 消抖 50ms ✅
- [x] TAP/HOLD/DOUBLE 识别 ✅
- [x] TAP 正常, HOLD 阈值待优化, DOUBLE 待改造

---

## 阶段 3: 应用层开发 ⏳

### 3.1 表情引擎
- [x] 表情枚举 + 动画框架 ✅
- [ ] 表情素材集成 (待另一个AI交付)

### 3.2 状态机框架
- [x] IDLE→ACTIVE→INTERACT→SLEEP 非阻塞 FSM ✅
- [x] 触摸/姿态事件驱动状态切换 ✅

---

## 阶段 4-5: PC工具 + 集成测试 ⏳ 待开始

---

## 已知硬件问题

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| 1 | HSE 晶振未起振 | 只能用 HSI 64MHz | 待排查 |
| 2 | FSMC NADV(PB7) 与 I2C1_SDA 冲突 | 不能用硬件 I2C1 | 已用软I2C解决 |
| 3 | CH340 DTR/RTS 触发自动下载 | 需用 SSCOM | 已解决 |
