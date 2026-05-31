#ifndef RGB_LED_H
#define RGB_LED_H

#include <stdint.h>

typedef struct {
    uint8_t r, g, b;
} RGB_Color;

void RGB_Init(void);
void RGB_SetColor(uint8_t r, uint8_t g, uint8_t b);
void RGB_SetColorStruct(const RGB_Color *c);
void RGB_Off(void);

/* breathing effect: smoothly fade a color in/out over period_ms */
void RGB_Breathe(uint8_t r, uint8_t g, uint8_t b, uint16_t period_ms);
void RGB_StopEffect(void);
void RGB_Tick(void);  /* call from main loop for effect updates */

#endif
