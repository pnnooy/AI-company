#ifndef ILI9341_FSMC_H
#define ILI9341_FSMC_H

#include <stdint.h>

/* ILI9341 display dimensions */
#define ILI9341_WIDTH   320
#define ILI9341_HEIGHT  240

/* Color definitions (RGB565) */
#define COLOR_BLACK      0x0000
#define COLOR_WHITE      0xFFFF
#define COLOR_RED        0xF800
#define COLOR_GREEN      0x07E0
#define COLOR_BLUE       0x001F
#define COLOR_YELLOW     0xFFE0
#define COLOR_CYAN       0x07FF
#define COLOR_MAGENTA    0xF81F

void ILI9341_Init(void);
void ILI9341_SetWindow(uint16_t x, uint16_t y, uint16_t w, uint16_t h);
void ILI9341_FillScreen(uint16_t color);
void ILI9341_FillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color);
void ILI9341_DrawBitmap(uint16_t x, uint16_t y, uint16_t w, uint16_t h, const uint16_t *data);
void ILI9341_DrawBitmapScaled(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                              const uint16_t *data, uint8_t scale);
void ILI9341_DrawPixel(uint16_t x, uint16_t y, uint16_t color);
void ILI9341_DrawTestPattern(void);

#endif
