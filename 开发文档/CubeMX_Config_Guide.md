# CubeMX 配置指南 — STM32F103VET6 桌面助手

**最后更新**: 2026-05-21

---

## 1. 新建工程
- 启动 STM32CubeMX → New Project
- 搜索并选择 **STM32F103VET6** (LQFP100)
- 保存工程到 `d:\AI_company\firmware\desktop_assistant\` (命名 `desktop_assistant.ioc`)

## 2. Pinout & Configuration

### 2.1 System Core → SYS
- Debug: **Serial Wire**
- Timebase Source: **SysTick**

### 2.2 System Core → RCC
- High Speed Clock (HSE): **Crystal/Ceramic Resonator**
- Low Speed Clock (LSE): **Disable**

> ⚠️ 当前 HSE 晶振未起振, 生成后需在 main.c 中手动改为 HSI 64MHz (见下方修复步骤)。

### 2.3 Clock Configuration

CubeMX 中按 HSE 72MHz 配置 (默认):
```
HSE 8MHz → PLL (/1) ×9 = 72MHz → SYSCLK = 72MHz
                                 → AHB /1 = 72MHz (HCLK)
                                 → APB1 /2 = 36MHz
                                 → APB2 /1 = 72MHz
```

生成后在 `SystemClock_Config()` 里手动改为 HSI 64MHz:
```c
RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
RCC_OscInitStruct.HSIState = RCC_HSI_ON;
RCC_OscInitStruct.HSEState = RCC_HSE_OFF;
RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI_DIV2;
RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL16;  // HSI/2 * 16 = 64MHz
```
FLASH_LATENCY_2 保持不变。

HSE 修复后切回 CubeMX 默认配置 (HSE ×9 = 72MHz) 即可。

### 2.4 Connectivity → USART1
- Mode: **Asynchronous**
- Baud Rate: **115200**
- Word Length: **8 Bits**, Parity: **None**, Stop Bits: **1**
- Pins: PA9=TX, PA10=RX (自动)

> 板载 CH340 USB 转串口。串口工具必须用 SSCOM (关 DTR/RTS), 否则会触发自动下载电路导致 MCU 复位。

### 2.5 Connectivity → I2C1
- Mode: **Disable**

> FSMC NADV 与 I2C1_SDA 共用 PB7, **不可使用硬件 I2C1**。MPU6050 改用软件 I2C (PA11=SCL, PA12=SDA), 由 `soft_i2c.c` 驱动。

### 2.6 Connectivity → SPI1
- Mode: **Full-Duplex Master**
- Prescaler: **8** (72MHz/8 = 9MHz)
- CPOL: **Low**, CPHA: **1 Edge**
- NSS: **Disable** (软件 CS)
- Pins: PA5=SCK, PA6=MISO, PA7=MOSI (自动)

### 2.7 Timers → TIM3
- Clock Source: **Internal Clock**
- Channel 2: **PWM Generation CH2** → PB5
- Channel 3: **PWM Generation CH3** → PB0
- Channel 4: **PWM Generation CH4** → PB1
- Prescaler: **1999**
- Counter Period: **255** ⚠️ 生成后检查, 默认可能是 65535
- Auto-reload preload: **Enable**

> PB5 需要 TIM3 Partial Remap。代码中已添加 `__HAL_AFIO_REMAP_TIM3_PARTIAL()`。

### 2.8 Connectivity → FSMC
- 选择 **NOR/PSRAM** → 勾选 **NE1**
- Memory type: **LCD Interface**
- LCD Register Select: **A23** (Enable)
- Data: **16 bits**
- 其余项保持 Disable

FSMC NOR/PSRAM Timing:
- Address setup: **15** HCLK cycles
- Data setup: **15** HCLK cycles
- Bus turnaround: **15** cycles
- Access mode: **A**

### 2.9 System Core → GPIO (手动搜索配置)

在 Pinout View 中按 **Ctrl+F** 搜索引脚号, 右键选择对应模式:

| Pin | 设置 | 注意 |
|-----|------|------|
| PA3 | GPIO_Output | RC522 RST |
| PA4 | GPIO_Output | RC522 CS (默认显示SPI1_NSS, 需手动改为GPIO_Output) |
| PC4 | GPIO_EXTI4 | Rising edge, Pull-down |
| PC5 | GPIO_EXTI5 | Rising edge, Pull-down |

### 2.10 System Core → NVIC
- Priority Group: **4 bits for preemption priority**
- ☑ EXTI line4 interrupt (PC4): Preemption Priority **5**
- ☑ EXTI line[9:5] interrupts (PC5): Preemption Priority **5**
- ☑ USART1 global interrupt: Preemption Priority **3**
- SysTick: 保持默认 Priority **0** (最高)

> PC4=EXTI4, PC5=EXTI5, 两个在不同的中断组, 需要分别启用！

## 3. Project Manager → Project
- Project Name: **desktop_assistant**
- Toolchain: **MDK-ARM V5**
- Min Version: **V5.27**
- ☑ Generate Under Root
- ☐ Do not generate the main() (不勾! 需要生成 main.c)

## 4. Project Manager → Code Generator
- ☑ Copy only the necessary library files
- ☑ Generate peripheral initialization as a pair of '.c/.h' files
- ☑ Set all free pins as analog (省电)
- ☐ Delete previously generated files (取消勾选)

## 5. GENERATE CODE
- 点击 **GENERATE CODE**
- 确认路径: `d:\AI_company\firmware\desktop_assistant\`

## 6. 生成后必须修复的项目

CubeMX 重生成会覆盖以下配置:

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `Core/Src/tim.c` | Period: 65535→**255** |
| 2 | `Core/Src/tim.c` | OCPolarity: HIGH→**LOW** (共阳LED) |
| 3 | `Core/Src/main.c` | SystemClock_Config: HSE→**HSI** (64MHz) |
| 4 | `Core/Src/main.c` | USER CODE 区域需从备份恢复 |
| 5 | `MDK-ARM/*.uvprojx` | 重新添加 Drivers/App 文件组 + Include 路径 |

> 建议: 生成后用 git diff 检查变更, 只保留外设新增部分, 其他手动修复。

## 7. Keil 工程补充配置

CubeMX 生成的工程还需要手动添加:

### Include 路径 (Project → Options → C/C++ → Include Paths)
```
..\..\Drivers\Inc
..\..\App
```

### 源文件组
- **Drivers 组**: `Drivers/Src/*.c` (7个)
- **App 组**: `App/*.c` (3个)

### Target (Project → Options → Target)
- ☑ **Use MicroLIB** (printf 支持)
