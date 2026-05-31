#include "ili9341_fsmc.h"
#include "stm32f1xx_hal.h"

/*
 * ILI9341 LCD driver via FSMC 8080 parallel interface.
 *
 * Hardware mapping (board-specific):
 *   FSMC Bank1 NOR/PSRAM, sub-bank 4 (NE4)
 *   Command register:  *(volatile uint16_t *)0x6C000000  (RS=0)
 *   Data register:     *(volatile uint16_t *)0x6C000002  (RS=1)
 *
 * Must match CubeMX FSMC configuration: 16-bit data width,
 * Address/Data multiplexed disabled, SRAM/NOR timing.
 */

/* FSMC base addresses for LCD command/data registers.
 * NE1 → Bank1 subbank1 → base 0x60000000.
 * RS signal wired to A16 → HADDR[17] in 16-bit mode.
 * CMD: 0x60000000  DATA: 0x60020000 (per 野火例程). */
#define LCD_BASE        ((uint32_t)0x60000000)
#define LCD_CMD_ADDR    (LCD_BASE | 0x00000000)  /* A16=0 → RS=0 (command) */
#define LCD_DATA_ADDR   (LCD_BASE | 0x00020000)  /* A16=1 → RS=1 (data) */

#define LCD_CMD  (*(volatile uint16_t *)LCD_CMD_ADDR)
#define LCD_DATA (*(volatile uint16_t *)LCD_DATA_ADDR)

/* ILI9341 command set */
#define ILI9341_CMD_SWRESET   0x01
#define ILI9341_CMD_SLEEPOUT  0x11
#define ILI9341_CMD_DISPLAYON 0x29
#define ILI9341_CMD_CASET     0x2A  /* column address set */
#define ILI9341_CMD_RASET     0x2B  /* row address set */
#define ILI9341_CMD_RAMWR     0x2C  /* memory write */
#define ILI9341_CMD_MADCTL    0x36  /* memory access control */
#define ILI9341_CMD_PIXFMT    0x3A  /* pixel format */

static void ILI9341_WriteCmd(uint8_t cmd) {
    LCD_CMD = cmd;
}

static void ILI9341_WriteData(uint16_t data) {
    LCD_DATA = data;
}

static void ILI9341_WriteCmdData(uint8_t cmd, uint16_t data) {
    LCD_CMD = cmd;
    LCD_DATA = data;
}

void ILI9341_Init(void) {
    /* FSMC peripheral must be initialized by CubeMX before calling this. */

    /* Backlight: PD12 (HIGH = ON) */
    __HAL_RCC_GPIOD_CLK_ENABLE();
    GPIO_InitTypeDef g = {0};
    g.Pin = GPIO_PIN_12;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOD, &g);
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_RESET);  /* LOW = backlight ON */

    /* Hardware reset: PE1 (LOW → 10ms → HIGH → 120ms) */
    __HAL_RCC_GPIOE_CLK_ENABLE();
    g.Pin = GPIO_PIN_1;
    HAL_GPIO_Init(GPIOE, &g);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, GPIO_PIN_RESET);
    HAL_Delay(10);
    HAL_GPIO_WritePin(GPIOE, GPIO_PIN_1, GPIO_PIN_SET);
    HAL_Delay(120);

    /* Software reset */
    ILI9341_WriteCmd(0x01);
    HAL_Delay(5);

    /* Power control B */
    ILI9341_WriteCmd(0xCF);
    ILI9341_WriteData(0x00); ILI9341_WriteData(0x81); ILI9341_WriteData(0x30);

    /* Power on sequence */
    ILI9341_WriteCmd(0xED);
    ILI9341_WriteData(0x64); ILI9341_WriteData(0x03); ILI9341_WriteData(0x12);
    ILI9341_WriteData(0x81);

    /* Driver timing control A */
    ILI9341_WriteCmd(0xE8);
    ILI9341_WriteData(0x85); ILI9341_WriteData(0x10); ILI9341_WriteData(0x78);

    /* Power control A */
    ILI9341_WriteCmd(0xCB);
    ILI9341_WriteData(0x39); ILI9341_WriteData(0x2C); ILI9341_WriteData(0x00);
    ILI9341_WriteData(0x34); ILI9341_WriteData(0x06);

    /* Pump ratio */
    ILI9341_WriteCmd(0xF7); ILI9341_WriteData(0x20);

    /* Driver timing B */
    ILI9341_WriteCmd(0xEA);
    ILI9341_WriteData(0x00); ILI9341_WriteData(0x00);

    /* Frame rate */
    ILI9341_WriteCmd(0xB1);
    ILI9341_WriteData(0x00); ILI9341_WriteData(0x1B);

    /* Display function */
    ILI9341_WriteCmd(0xB6);
    ILI9341_WriteData(0x0A); ILI9341_WriteData(0xA2);

    /* Power control 1 & 2 */
    ILI9341_WriteCmd(0xC0); ILI9341_WriteData(0x35);
    ILI9341_WriteCmd(0xC1); ILI9341_WriteData(0x11);

    /* VCOM control */
    ILI9341_WriteCmd(0xC5);
    ILI9341_WriteData(0x45); ILI9341_WriteData(0x45);
    ILI9341_WriteCmd(0xC7); ILI9341_WriteData(0xA2);

    /* Enable 3G */
    ILI9341_WriteCmd(0xF2); ILI9341_WriteData(0x00);

    /* Gamma set */
    ILI9341_WriteCmd(0x26); ILI9341_WriteData(0x01);

    /* Positive gamma */
    ILI9341_WriteCmd(0xE0);
    ILI9341_WriteData(0x0F); ILI9341_WriteData(0x26); ILI9341_WriteData(0x24);
    ILI9341_WriteData(0x0B); ILI9341_WriteData(0x0E); ILI9341_WriteData(0x09);
    ILI9341_WriteData(0x54); ILI9341_WriteData(0xA8); ILI9341_WriteData(0x46);
    ILI9341_WriteData(0x0C); ILI9341_WriteData(0x17); ILI9341_WriteData(0x09);
    ILI9341_WriteData(0x0F); ILI9341_WriteData(0x07); ILI9341_WriteData(0x00);

    /* Negative gamma */
    ILI9341_WriteCmd(0xE1);
    ILI9341_WriteData(0x00); ILI9341_WriteData(0x19); ILI9341_WriteData(0x1B);
    ILI9341_WriteData(0x04); ILI9341_WriteData(0x10); ILI9341_WriteData(0x07);
    ILI9341_WriteData(0x2A); ILI9341_WriteData(0x47); ILI9341_WriteData(0x39);
    ILI9341_WriteData(0x03); ILI9341_WriteData(0x06); ILI9341_WriteData(0x06);
    ILI9341_WriteData(0x30); ILI9341_WriteData(0x38); ILI9341_WriteData(0x0F);

    /* Memory access control */
    ILI9341_WriteCmd(0x36); ILI9341_WriteData(0xC8);

    /* Pixel format: RGB565 */
    ILI9341_WriteCmd(0x3A); ILI9341_WriteData(0x55);

    /* Exit sleep */
    ILI9341_WriteCmd(0x11);
    HAL_Delay(120);

    /* Display ON */
    ILI9341_WriteCmd(0x29);

    /* MADCTL: landscape 320x240 (X-Y swap), top-left origin, RGB order */
    ILI9341_WriteCmd(0x36);
    ILI9341_WriteData(0x28);

    ILI9341_FillScreen(COLOR_BLACK);
}

void ILI9341_SetWindow(uint16_t x, uint16_t y, uint16_t w, uint16_t h) {
    uint16_t xe = x + w - 1;
    uint16_t ye = y + h - 1;

    ILI9341_WriteCmd(ILI9341_CMD_CASET);
    ILI9341_WriteData(x >> 8);
    ILI9341_WriteData(x & 0xFF);
    ILI9341_WriteData(xe >> 8);
    ILI9341_WriteData(xe & 0xFF);

    ILI9341_WriteCmd(ILI9341_CMD_RASET);
    ILI9341_WriteData(y >> 8);
    ILI9341_WriteData(y & 0xFF);
    ILI9341_WriteData(ye >> 8);
    ILI9341_WriteData(ye & 0xFF);
}

void ILI9341_DrawBitmap(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                        const uint16_t *data) {
    ILI9341_DrawBitmapScaled(x, y, w, h, data, 1);
}

void ILI9341_DrawBitmapScaled(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                              const uint16_t *data, uint8_t scale) {
    uint16_t ow = w * scale;
    uint16_t oh = h * scale;
    ILI9341_SetWindow(x, y, ow, oh);
    ILI9341_WriteCmd(ILI9341_CMD_RAMWR);

    /* Rotate 90° CW + nearest-neighbor scale */
    for (int col = (int)w - 1; col >= 0; col--) {
        for (int s = 0; s < scale; s++) {
            for (int row = 0; row < (int)h; row++) {
                uint16_t c = data[row * w + col];
                for (int r = 0; r < scale; r++) {
                    LCD_DATA = c;
                }
            }
        }
    }
}

void ILI9341_FillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                      uint16_t color) {
    ILI9341_SetWindow(x, y, w, h);
    ILI9341_WriteCmd(ILI9341_CMD_RAMWR);

    uint32_t count = (uint32_t)w * h;
    for (uint32_t i = 0; i < count; i++) {
        LCD_DATA = color;
    }
}

void ILI9341_FillScreen(uint16_t color) {
    ILI9341_FillRect(0, 0, ILI9341_WIDTH, ILI9341_HEIGHT, color);
}

void ILI9341_DrawPixel(uint16_t x, uint16_t y, uint16_t color) {
    ILI9341_SetWindow(x, y, 1, 1);
    ILI9341_WriteCmd(ILI9341_CMD_RAMWR);
    LCD_DATA = color;
}
