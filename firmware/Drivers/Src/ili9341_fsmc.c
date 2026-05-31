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
 * RS signal wired to A23 → bit 24 of AHB address.
 * In 16-bit mode HADDR[25:1] → FSMC_A[24:0]. */
#define LCD_BASE        ((uint32_t)0x60000000)
#define LCD_CMD_ADDR    (LCD_BASE | 0x00000000)  /* A23=0 → RS=0 (command) */
#define LCD_DATA_ADDR   (LCD_BASE | 0x01000002)  /* A23=1 → RS=1 (data) */

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
    /* FSMC peripheral must be initialized by CubeMX before calling this.
       Basic ILI9341 init sequence for 320x240, RGB565, portrait mode. */

    ILI9341_WriteCmd(ILI9341_CMD_SWRESET);
    HAL_Delay(120);

    /* Memory access control: BGR order, vertical refresh direction */
    ILI9341_WriteCmdData(ILI9341_CMD_MADCTL, 0x48);

    /* Pixel format: 16-bit RGB565 */
    ILI9341_WriteCmdData(ILI9341_CMD_PIXFMT, 0x55);

    /* Exit sleep */
    ILI9341_WriteCmd(ILI9341_CMD_SLEEPOUT);
    HAL_Delay(10);

    /* Display on */
    ILI9341_WriteCmd(ILI9341_CMD_DISPLAYON);

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
    ILI9341_SetWindow(x, y, w, h);
    ILI9341_WriteCmd(ILI9341_CMD_RAMWR);

    uint32_t count = (uint32_t)w * h;
    for (uint32_t i = 0; i < count; i++) {
        LCD_DATA = data[i];
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
