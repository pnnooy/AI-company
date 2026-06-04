# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop Academic Assistant Robot for university students, based on STM32F103VET6 (WildFire Guide development board). A dual-system architecture with firmware on STM32 and AI decision engine on PC, communicating via UART.

**Key interactions**: LCD expressions, RGB ambient lighting, capacitive touch sensors, 6-axis IMU (MPU6050), NFC card reader (MFRC-522).

**Current status**: Hardware drivers complete, main FSM operational, LCD color calibration done, expression animations working. NFC reader SPI stable but card reading under debugging (REQA fails). PC backend structure exists but modules not yet integrated.

## System Architecture

### Two-Part System
1. **Firmware (STM32)**: Handles hardware I/O, expression rendering, sensor polling, state machine
2. **PC Backend (Python)**: AI decision engine, facial recognition (optional), web UI, serial communication

Communication: USART1 at 115200 bps, binary protocol with CRC (defined in `firmware/Drivers/Src/uart_comm.c` and `pc_backend/comm/protocol.py`)

### Key Hardware Constraints
- **CRITICAL**: FSMC NADV shares PB7 with I2C1_SDA. **Never use hardware I2C1**. MPU6050 uses software I2C on PA11/PA12.
- **LCD Color Mapping**: PCB has crossed data lines D[15:11] ↔ D[10:6]. All pixel writes must use `PIXEL()` macro in `ili9341_fsmc.c` to compensate.
- **Clock**: Currently HSI 64MHz (HSE 8MHz crystal not oscillating, pending investigation). Target is 72MHz after HSE fix.

## Building & Flashing Firmware

### Requirements
- Keil MDK-ARM V5 (V5.06 update 6+)
- STM32CubeMX (for regenerating HAL init code)
- Fire-Debugger (CMSIS-DAP compatible)
- SSCOM v5.13.1 for serial debugging (located in `串口调试工具SSCOM/` directory)

### Build Commands
```bash
# Open Keil project
# Windows: double-click firmware/desktop_assistant/MDK-ARM/desktop_assistant.uvprojx

# In Keil:
F7              # Build (should be 0 Error 0 Warning)
F8              # Download to board via Fire-Debugger
```

### Serial Testing
1. Open `串口调试工具SSCOM/sscom.5.13.1.exe`
2. Set COM6, 115200-8-N-1
3. **Important**: Disable DTR and RTS (prevents auto-reset on connect)
4. Reset board → should see "Desktop Assistant Ready"

### Test Commands
```
led 255 0 0          # Set RGB LED to red
emo happy            # Switch to happy expression
mpu                  # Read MPU6050 data
nfc                  # Attempt card read
calib                # LCD color calibration test
state                # Show FSM state
help                 # List all commands
```

Available expressions: `normal`, `happy`, `focus`, `angry`, `sleep`, `surprise`, `sad`, `love`

## PC Backend

### Setup
```bash
cd pc_backend
pip install -r requirements.txt

# Run (when implemented)
python main.py --port COM6 --baud 115200
```

### Current Structure
- `comm/uart_link.py` - Serial communication layer (skeleton exists)
- `comm/protocol.py` - Binary protocol definitions (skeleton exists)
- `ai_engine/state_machine.py` - AI decision logic (not yet implemented)
- `ai_engine/rules.py` - Behavior rules (not yet implemented)
- `camera/face_detect.py` - Optional facial recognition (not yet implemented)

## Development Workflows

### Adding New Expression
1. Create 80×80 PNG with black background, name as `emo_{name}_f{frame}.png`
2. Place in `firmware/Assets/`
3. Update `EXPRESSIONS` dict in `tools/make_assets.py` with frame count and interval
4. Run `python tools/make_assets.py --size 80`
5. Add enum to `firmware/App/expression_types.h`
6. Rebuild firmware in Keil (F7, F8)

### Modifying Hardware Driver
1. Edit files in `firmware/Drivers/Src/` or `firmware/Drivers/Inc/`
2. Follow naming: `ModuleName_FunctionName()` (e.g., `ILI9341_DrawPixel`, `RGB_SetColor`)
3. Never use `HAL_Delay()` - use `HAL_GetTick()` for non-blocking timing
4. Test via serial commands before integrating into FSM
5. Build & flash (F7, F8 in Keil)

### CubeMX Regeneration (Dangerous)
CubeMX GENERATE CODE will overwrite these - manual fixes required after:
1. `Core/Src/tim.c`: Restore Period=255, OCPolarity=LOW
2. `Core/Src/main.c`: SystemClock_Config must use HSI (not HSE until crystal fixed)
3. `Core/Src/gpio.c`: PA3(RST), PA4(CS) speed must be GPIO_SPEED_FREQ_HIGH
4. `Core/Src/spi.c`: Baud rate prescaler /8 → /32 (2MHz for MFRC522 stability)
   - Fix in `RC522_Init()`: `CLEAR_BIT(SPI1->CR1, SPI_CR1_BR); SET_BIT(SPI1->CR1, SPI_BAUDRATEPRESCALER_32);`
5. MDK-ARM `.uvprojx`: Re-add include paths for `firmware/Drivers/Inc` and `firmware/App`
6. Verify USER CODE sections in `main.c` preserved

**Best practice**: Avoid CubeMX regeneration unless adding new peripherals. Make peripheral config changes directly in code when possible.

### Debugging NFC Issues
Current blocker: `RC522_GetCardUID()` REQA command returns len=0, but `RC522_CheckCard()` detects card presence.

Debug commands:
```
nfcdbg           # Dump all MFRC522 registers
nfcreset         # Soft reset RC522
nfc              # Attempt card read with diagnostics
```

Check:
- SPI waveform on PA5 (SCK) - should be 2MHz
- PA3 (RST) held high after init
- PA4 (CS) toggling during transactions
- 3.3V power stable, antenna not damaged
- Card type is ISO14443A-compatible (S50/S70)

See `开发文档/Team_Tasks/A_NFC_Firmware_Protocol.md` for detailed debugging guide.

## Code Standards

### Naming Conventions
- Files: `snake_case` (e.g., `ili9341_fsmc.c`, `mpu6050_hal.c`)
- Functions: `ModulePrefix_PascalCase` (e.g., `ILI9341_DrawPixel`, `MPU6050_ReadData`)
- Macros/Constants: `UPPER_SNAKE_CASE` (e.g., `EMO_NORMAL`, `COLOR_RED`)
- Peripheral handles: Use CubeMX-generated names (`hspi1`, `htim3`, `huart1`)

### File Organization
- Each hardware driver = 1 `.c` + 1 `.h` in `firmware/Drivers/`
- Application logic in `firmware/App/`
- Header guards required: `#ifndef MODULE_H` / `#define MODULE_H` / `#endif`

### Firmware Constraints
- **No blocking delays**: Use `HAL_GetTick()` instead of `HAL_Delay()`
- **No `printf` in ISR**: Only set flags in interrupt handlers
- **PIXEL macro required**: All LCD writes must use `PIXEL(color)` to compensate for PCB wiring
- **MicroLIB enabled**: printf redirected to UART via `uart_comm.c`

## Key Reference Documents

- `开发文档/Project_Brief.md` - Detailed V2.1 specification
- `开发文档/CubeMX_Config_Guide.md` - Peripheral configuration reference
- `开发文档/Expression_Task_Brief.md` - Expression asset creation guide
- `开发文档/Team_Tasks/` - 5-person collaboration task breakdown (A/B/C/D/E)
- `硬件资料/【野火】零死角玩转STM32—F103指南者.pdf` - Board reference (Chapter 47 for FSMC/I2C conflict)

## Git Workflow

- Main branch: `main`
- Feature branches: `feature/<description>` → PR to main
- Collaboration: 5 contributors, main contact: pnnooy (hanyufei24@sjtu.edu.cn)

```bash
git checkout -b feature/my-feature
# ... develop ...
git add <files>
git commit -m "descriptive message"
git push origin feature/my-feature
# Create PR on GitHub
```

## Known Issues & Workarounds

| Issue | Severity | Workaround |
|-------|----------|------------|
| HSE crystal not oscillating | Medium | Using HSI 64MHz (11% perf loss) |
| NFC REQA fails | High | Under investigation, SPI link verified stable |
| Pink expressions look cyan | Low | Use `--invert` flag with `make_assets.py` or update PNG source |
| CH340 auto-resets on serial connect | Low | Disable DTR/RTS in SSCOM |
| Touch HOLD threshold too high | Low | 1000ms, consider reducing to 700ms |
| Touch DOUBLE rarely triggers | Low | Requires simultaneous touch, impractical |

## Testing

### Firmware
- Manual testing via SSCOM serial commands
- LCD color calibration: `calib` command → verify 8/8 color bars correct
- Expression animation: `emo <name>` → verify smooth rendering at 2x scale (160×160)
- Touch sensors: Physical tap → should print event and trigger expression
- MPU6050: `mpu` → verify accel/gyro readings, shake device → SHAKE event
- No automated test framework currently

### PC Backend
- Unit tests in `pc_backend/tests/` (not yet implemented)
- When implemented: `pytest pc_backend/tests/`

## Memory System

Project-specific memory stored in `C:\Users\lenovo\.claude\projects\D--exp-all-AI-company\memory\`.

Key memories include LCD color debugging solution, hardware conflicts (FSMC/I2C), team member context.
