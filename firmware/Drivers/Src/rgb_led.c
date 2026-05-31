#include "rgb_led.h"
#include "stm32f1xx_hal.h"
#include "tim.h"
#include <math.h>

/*
 * Onboard RGB LED: PB5(R-TIM3_CH2), PB0(G-TIM3_CH3), PB1(B-TIM3_CH4)
 * Requires TIM3 partial remap: __HAL_AFIO_REMAP_TIM3_PARTIAL()
 */

static uint8_t  breathe_r, breathe_g, breathe_b;
static uint16_t breathe_period;
static uint32_t breathe_start_tick;
static uint8_t  breathe_active;

void RGB_Init(void) {
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_2);  /* Red   - PB5 */
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_3);  /* Green - PB0 */
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_4);  /* Blue  - PB1 */
    RGB_Off();
    breathe_active = 0;
}

void RGB_SetColor(uint8_t r, uint8_t g, uint8_t b) {
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, r);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_3, g);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, b);
}

void RGB_SetColorStruct(const RGB_Color *c) {
    if (c) RGB_SetColor(c->r, c->g, c->b);
}

void RGB_Off(void) {
    RGB_SetColor(0, 0, 0);
}

void RGB_Breathe(uint8_t r, uint8_t g, uint8_t b, uint16_t period_ms) {
    breathe_r = r; breathe_g = g; breathe_b = b;
    breathe_period = period_ms;
    breathe_start_tick = HAL_GetTick();
    breathe_active = 1;
}

void RGB_StopEffect(void) {
    breathe_active = 0;
}

void RGB_Tick(void) {
    if (!breathe_active) return;

    uint32_t elapsed = HAL_GetTick() - breathe_start_tick;
    float phase = (float)(elapsed % breathe_period) / breathe_period;

    float factor;
    if (phase < 0.5f) {
        factor = phase * 2.0f;
    } else {
        factor = (1.0f - phase) * 2.0f;
    }

    uint8_t r = (uint8_t)(breathe_r * factor);
    uint8_t g = (uint8_t)(breathe_g * factor);
    uint8_t b = (uint8_t)(breathe_b * factor);

    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, r);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_3, g);
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, b);
}
