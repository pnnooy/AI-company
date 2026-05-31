# CubeMX 配置指南 - STM32F103VET6 桌面助手

## 1. 新建工程
- 启动 STM32CubeMX → New Project
- 搜索并选择 **STM32F103VET6** (LQFP100)
- 保存工程到 `d:\AI_company\firmware\` (命名 `desktop_assistant.ioc`)

## 2. Pinout & Configuration

### 2.1 System Core → SYS
- Debug: **Serial Wire**
- Timebase Source: **SysTick**

### 2.2 System Core → RCC
- High Speed Clock (HSE): **Crystal/Ceramic Resonator**
- Low Speed Clock (LSE): **Disable**

### 2.3 Clock Configuration
```
HSE 8MHz → PLL (/1) ×9 = 72MHz → SYSCLK = 72MHz
                                 → AHB Prescaler /1 = 72MHz (HCLK)
                                 → APB1 Prescaler /2 = 36MHz
                                 → APB2 Prescaler /1 = 72MHz
```

### 2.4 Connectivity → USART1
- Mode: **Asynchronous**
- Baud Rate: **115200**
- Word Length: **8 Bits**
- Parity: **None**
- Stop Bits: **1**
- Pins: PA9=TX, PA10=RX (自动分配)

### 2.5 Connectivity → I2C1
- Mode: **I2C**
- Speed: **Fast Mode (400kHz)**
- Pins: PB6=SCL, PB7=SDA (自动分配)

### 2.6 Connectivity → SPI1
- Mode: **Full-Duplex Master**
- Prescaler: **8** (72MHz/8 = 9MHz, 在RC522范围内)
- CPOL: **Low**, CPHA: **1 Edge**
- NSS: **Disable** (软件CS)
- Pins: PA5=SCK, PA6=MISO, PA7=MOSI (自动分配)

### 2.7 Timers → TIM2
- Clock Source: **Internal Clock**
- Channel 1: **PWM Generation CH1** → PA0
- Channel 2: **PWM Generation CH2** → PA1
- Channel 3: **PWM Generation CH3** → PA2
- Prescaler: **0** (72MHz/1 = 72MHz timer clock)
- Counter Period: **255** (8-bit PWM resolution)
- Auto-reload preload: **Enable**

### 2.8 Connectivity → FSMC
- 选择 **NOR/PSRAM** (bank1) → 勾选 NE1
- Memory type: **LCD Interface**
- Chip Select: **NE1**
- LCD Register Select: **A23** (Enable)
- Data: **16 bits**
- 其余项保持 Disable

FSMC NOR/PSRAM Timing:
- Address setup: **15** HCLK cycles
- Data setup: **15** HCLK cycles
- Bus turnaround: **15** cycles
- Access mode: **A**

### 2.9 System Core → GPIO (手动搜索配置)

**操作方法**: 在 Pinout View 中按 **Ctrl+F** 搜索引脚号, 右键 → 选择对应模式.

| Pin | 搜索 | 右键设置 | 注意 |
|-----|------|----------|------|
| PA3 | 输入 `PA3` | GPIO_Output | 别选 USART2_RX |
| PA4 | 输入 `PA4` | GPIO_Output | 默认可能显示 SPI1_NSS, 需要手动改 |
| PC4 | 输入 `PC4` | GPIO_EXTI4 | 选 Rising edge, Pull-down |
| PC5 | 输入 `PC5` | GPIO_EXTI5 | 选 Rising edge, Pull-down |

> **找不到 PA4?** SPI1 启用后 PA4 会被自动标为 SPI1_NSS。虽然 SPI1 的 NSS 设为了 Disable, CubeMX 可能仍占用着。在 Pinout View 左键点 PA4 引脚, 弹出的菜单里选 **GPIO_Output** 即可。

### 2.10 System Core → NVIC
- Priority Group: **4 bits for preemption priority**
- EXTI line4 interrupt (PC4): ☑ Enabled, Preemption Priority **5**, Sub Priority **0**
- EXTI line[9:5] interrupts (PC5): ☑ Enabled, Preemption Priority **5**, Sub Priority **0**
- USART1 global interrupt: ☑ Enabled, Preemption Priority **3**, Sub Priority **0**
- SysTick: Preemption Priority **0** (最高优先级, 默认)

## 3. Project Manager → Project
- Project Name: **desktop_assistant**
- Toolchain: **MDK-ARM V5**
- Min Version: **V5.27**
- ☑ Generate Under Root

## 4. Project Manager → Code Generator
- ☑ Copy only the necessary library files
- ☑ Generate peripheral initialization as a pair of '.c/.h' files
- ☑ Set all free pins as analog (省电)
- ☐ Delete previously generated files (取消勾选, 避免覆盖手动添加的文件)

## 5. 生成代码
- 点击 **GENERATE CODE**
- 确认生成路径: `d:\AI_company\firmware\`

## 6. 生成后检查
- [ ] 编译 `desktop_assistant.uvprojx` 无错误
- [ ] `main.c` 中包含 `MX_USART1_UART_Init()`, `MX_I2C1_Init()`, `MX_SPI1_Init()`, `MX_TIM2_Init()`, `MX_FSMC_Init()`
- [ ] `stm32f1xx_it.c` 中包含 EXTI9_5_IRQHandler
