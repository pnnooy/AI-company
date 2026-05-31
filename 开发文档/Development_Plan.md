# 桌面学术助手机器人 - 开发计划 V1.0

## 项目时间线: 2026-05-21 启动

---

## 阶段 0: 环境搭建 (预计 1-2 天)

### 0.1 开发工具安装
- [ ] 安装 Keil MDK-ARM V5 (MDK5.15+)
- [ ] 安装 STM32F1 芯片包 (Keil Pack Installer)
- [ ] 安装 STM32CubeMX (最新版)
- [ ] 安装 ST-Link/DAP 调试器驱动
- [ ] 安装 CH340 USB-TTL 驱动

### 0.2 硬件连接验证
- [ ] 连接 ST-Link/DAP 到开发板 SWD 接口
- [ ] 连接 CH340 USB-TTL 到 USART1
- [ ] 确认板载 LED 可通过测试程序点亮 (验证烧录链路)

**关键验证**: 能编译、能烧录、能串口打印 "Hello World"

---

## 阶段 1: CubeMX 基础工程生成 (预计 0.5 天)

### 1.1 CubeMX 配置
- [ ] MCU 选型: STM32F103VET6 (LQFP100)
- [ ] **RCC**: HSE 外部晶振 → PLL → SYSCLK=72MHz, APB1=36MHz, APB2=72MHz
- [ ] **SYS**: Debug = Serial Wire (SWD)
- [ ] **USART1**: Mode=Asynchronous, Baud=115200, 8-N-1 (PA9-TX, PA10-RX)
- [ ] **I2C1**: Mode=I2C, Speed=400kHz (PB6-SCL, PB7-SDA)
- [ ] **SPI1**: Mode=Full-Duplex Master, Prescaler 合适分频 (PA5-SCK, PA6-MISO, PA7-MOSI)
- [ ] **TIM3**: CH1=PB5, CH2=PB0, CH3=PB1 → PWM Generation
- [ ] **FSMC**: NOR/PSRAM模式, 配置为 8080 并口驱动 ILI9341
- [ ] **GPIO**: PA4 (RC522 CS 推挽输出), PA3 (RC522 RST 推挽输出)
- [ ] **GPIO**: PC4, PC5 → EXTI 上升沿中断 (NVIC 优先级低于 SysTick)
- [ ] **NVIC**: 中断优先级分组 4, EXTI 优先级 > SysTick 数值(即更低的优先级)

### 1.2 生成代码
- [ ] 生成 Keil MDK-ARM V5 工程
- [ ] 验证编译零错误零警告
- [ ] 烧录验证: main() 中添加 LED 闪烁和串口 printf

---

## 阶段 2: 硬件驱动层开发 (预计 5-7 天)

### 2.1 UART 通信框架 (优先级: 最高)
**文件**: `drivers/uart_comm.c/.h`

- [ ] 实现 `printf` 重定向到 USART1 (使用 MicroLIB 或 DMA)
- [ ] 设计 PC ↔ MCU 通信协议:
  ```
  协议格式: [CMD:2B][LEN:1B][PAYLOAD:N][CRC:1B]
  命令类型:
    - 0x01: 表情控制 (EMO_ID + 参数)
    - 0x02: RGB 灯光控制 (R + G + B + 亮度)
    - 0x03: 传感器数据上报 (触摸/姿态/刷卡)
    - 0x04: 心跳/状态查询
  ```
- [ ] 实现环形缓冲区接收 (DMA + IDLE 中断)
- [ ] 实现命令解析器 `CmdParser_Parse()`

### 2.2 ILI9341 LCD 驱动 (优先级: 最高)
**文件**: `drivers/ili9341_fsmc.c/.h`

- [ ] 基于 FSMC 8080 接口实现底层写命令/写数据函数
- [ ] 实现基础绘图: 画点、画线、矩形填充、颜色填充
- [ ] 实现 ASCII 字符显示 (取模或字库)
- [ ] 验证: 屏幕刷单色 → 显示字符 → 显示简单图形

### 2.3 RGB LED 驱动 (优先级: 中)
**文件**: `drivers/rgb_led.c/.h`

- [ ] 使用 TIM3 CH1/CH2/CH3 PWM 输出
- [ ] 封装 `RGB_SetColor(uint8_t r, uint8_t g, uint8_t b)`
- [ ] 封装呼吸效果 `RGB_Breathe(enum color, uint16_t period_ms)`
- [ ] 验证: 红→绿→蓝→白→呼吸效果

### 2.4 MPU6050 驱动 (优先级: 中)
**文件**: `drivers/mpu6050_hal.c/.h`

- [ ] 基于 I2C1 硬件实现读写 MPU6050 寄存器
- [ ] 初始化: 唤醒、配置量程(±2g, ±250°/s)、采样率
- [ ] 实现 `MPU6050_ReadAccel(float *ax, *ay, *az)`
- [ ] 实现 `MPU6050_ReadGyro(float *gx, *gy, *gz)`
- [ ] 姿态事件检测:
  - `EVENT_FALL` (倾倒): 加速度矢量偏离重力方向 > 45°
  - `EVENT_SHAKE` (摇晃): 加速度变化率 > 阈值
  - `EVENT_STABLE` (平稳): 持续 N ms 无明显变化
- [ ] 验证: 串口输出加速度和角速度原始值

### 2.5 MFRC-522 NFC 驱动 (优先级: 中)
**文件**: `drivers/rc522_spi.c/.h`

- [ ] 基于 SPI1 硬件实现读写 RC522 寄存器
- [ ] 初始化 RC522、自动寻卡
- [ ] 实现 `RC522_GetCardUID(uint8_t *uid)` 获取 S50 白卡 UID
- [ ] 实现防冲突、选卡流程
- [ ] 验证: 刷卡时串口打印 UID

### 2.6 TTP223 触摸驱动 (优先级: 中)
**文件**: `drivers/touch_sensor.c/.h`

- [ ] 配置 PC4/PC5 为 EXTI 上升沿中断
- [ ] 中断回调中设置触摸标志位
- [ ] 实现消抖 (软件去抖 50ms)
- [ ] 识别触摸事件类型: 单击、双击、长按(>1s)、双触(同时)
- [ ] 验证: 触摸 LED 亮灭 / 串口输出事件类型

---

## 阶段 3: 应用层开发 (预计 4-6 天)

### 3.1 表情视觉引擎
**文件**: `app/expression_engine.c/.h`

- [ ] 定义表情枚举 (EMO_NORMAL, EMO_HAPPY, EMO_FOCUS, EMO_ANGRY, EMO_SLEEP, EMO_SURPRISE, EMO_SAD, EMO_LOVE)
- [ ] 用简单几何图形构建表情:
  - 眼睛: 椭圆/圆形 + 高光点
  - 嘴巴: 弧线/直线 (不同表情不同形状)
  - 腮红: 半透明粉色圆 (可选)
- [ ] 实现表情切换过渡动画 (如: 200ms 渐变)
- [ ] 实现 `Expression_Set(enum EmoType)` 接口

### 3.2 主循环状态机框架
**文件**: `app/main_fsm.c/.h`

- [ ] 使用 `HAL_GetTick()` 实现非阻塞调度
- [ ] 定义系统状态: `IDLE`, `ACTIVE`, `INTERACT`, `SLEEP`, `ALERT`
- [ ] 状态转换逻辑:
  ```
  IDLE → ACTIVE (触摸/刷卡触发)
  ACTIVE → INTERACT (持续交互)
  INTERACT → IDLE (超时 N 秒无操作)
  IDLE → SLEEP (超时 M 分钟无操作)
  SLEEP → IDLE (触摸唤醒)
  ANY → ALERT (倾倒检测)
  ```
- [ ] 任务调度表 (每个主循环周期的任务):
  ```
  1. 轮询触摸标志 (10ms 间隔)
  2. 轮询 NFC 刷卡 (50ms 间隔)  
  3. 轮询 MPU6050 姿态 (20ms 间隔)
  4. 处理 UART 命令队列
  5. 刷新表情 (100ms 间隔, 只在脏标志置位时)
  6. 更新 RGB 灯光效果
  ```

### 3.3 交互模式实现
**文件**: `app/interaction.c/.h`

- [ ] **专注模式** (刷卡触发): LCD 显示专注表情 + 蓝光氛围灯
- [ ] **鼓励模式** (左触摸): LCD 显示开心表情 + 暖光呼吸
- [ ] **休息提醒**: 定时器触发 → 变色提醒
- [ ] **倾倒警报**: MPU6050 检测倾倒 → 红色闪烁 + 警报表情

---

## 阶段 4: PC 端工具开发 (预计 2-3 天)

### 4.1 Python 串口桥接
**文件**: `tools/serial_bridge.py`

- [ ] 使用 `pyserial` 连接 COM 口 (115200 bps)
- [ ] 实现协议组包/解包
- [ ] 命令行交互模式:
  ```
  > emotion happy    # 发送表情切换
  > led 255 128 0    # 设置 RGB 颜色
  > status           # 查询状态
  ```
- [ ] 接收并显示传感器事件 (触摸、刷卡、姿态)

---

## 阶段 5: 集成测试与优化 (预计 2-3 天)

- [ ] 全模块联调
- [ ] 非阻塞性能验证 (主循环周期 < 5ms)
- [ ] 内存/Flash 占用分析
- [ ] Bug 修复与边缘情况处理

---

## 技术风险 & 开放问题 (需讨论)

| # | 问题 | 选项 | 建议 |
|---|------|------|------|
| 1 | LCD 驱动: 自己写 vs 移植官方/开源库? | A) 手写精简版 B) 移植 uGFX/LVGL | 先手写基础版, 后期可迁移到 LVGL |
| 2 | 表情系统: 几何图形 vs 预存位图? | A) 代码画几何 B) SD卡位图 C) Flash 位图 | 几何图形(省存储, 灵活) |
| 3 | 通信协议: 文本 vs 二进制? | A) JSON 文本 B) 二进制帧 | 二进制帧(高效, 适合MCU) |
| 4 | RTOS vs 裸机状态机? | A) FreeRTOS B) 裸机状态机 | 先裸机状态机, 后期按需引入RTOS |
| 5 | TOF 传感器 / 蓝牙模块: 当前集成 vs 后期扩展? | A) 一期集成 B) 预留接口 | 一期聚焦核心, TOF/蓝牙二期 |
| 6 | 触摸行为: 软件去抖时间? | 30ms / 50ms / 100ms | 50ms (平衡响应和去抖) |
