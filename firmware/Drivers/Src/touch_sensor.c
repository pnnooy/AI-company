#include "touch_sensor.h"
#include "stm32f1xx_hal.h"

/*
 * TTP223 touch sensors on PC4 (left) and PC5 (right).
 * Config: rising edge EXTI interrupt, 50ms software debounce.
 */

#define TOUCH_DEBOUNCE_MS  50
#define TOUCH_HOLD_MS      1000

typedef struct {
    uint8_t  state;          /* 0=idle, 1=debouncing, 2=pressed, 3=released */
    uint32_t press_tick;     /* tick when first press detected */
    uint8_t  event_ready;    /* event ready to be consumed */
    TouchEvent pending_event;
} TouchChannel;

static TouchChannel ch_left;
static TouchChannel ch_right;

static void Touch_ChannelIRQ(TouchChannel *ch, TouchSide side) {
    uint32_t now = HAL_GetTick();

    switch (ch->state) {
    case 0: /* idle → debounce */
        ch->state = 1;
        ch->press_tick = now;
        break;
    case 1: /* debouncing */
        if ((now - ch->press_tick) >= TOUCH_DEBOUNCE_MS) {
            ch->state = 2; /* confirmed press */
            ch->press_tick = now;
        }
        break;
    case 2: /* already pressed */
    case 3: /* release detected */
        break;
    }
}

void Touch_IRQ_Left(void)  { Touch_ChannelIRQ(&ch_left, TOUCH_LEFT); }
void Touch_IRQ_Right(void) { Touch_ChannelIRQ(&ch_right, TOUCH_RIGHT); }

void Touch_Init(void) {
    ch_left.state   = 0; ch_left.event_ready = 0;
    ch_right.state  = 0; ch_right.event_ready = 0;
}

uint8_t Touch_Poll(TouchResult *result) {
    uint32_t now = HAL_GetTick();

    /* Check left channel */
    if (ch_left.event_ready) {
        ch_left.event_ready = 0;
        if (result) { result->side = TOUCH_LEFT; result->event = ch_left.pending_event; }
        return 1;
    }
    /* Check right channel */
    if (ch_right.event_ready) {
        ch_right.event_ready = 0;
        if (result) { result->side = TOUCH_RIGHT; result->event = ch_right.pending_event; }
        return 1;
    }

    /* Detect double-touch (both pressed simultaneously) */
    if (ch_left.state == 2 && ch_right.state == 2) {
        ch_left.state  = 3; ch_left.pending_event  = TOUCH_DOUBLE; ch_left.event_ready  = 1;
        ch_right.state = 3; ch_right.pending_event = TOUCH_DOUBLE; ch_right.event_ready = 1;
    }

    /* Check hold on each channel */
    TouchChannel *channels[2] = {&ch_left, &ch_right};
    for (int i = 0; i < 2; i++) {
        TouchChannel *ch = channels[i];
        if (ch->state == 2 && (now - ch->press_tick) >= TOUCH_HOLD_MS) {
            ch->state = 3;
            ch->pending_event = TOUCH_HOLD;
            ch->event_ready = 1;
        }
    }

    /* Check release (GPIO low) for tap detection */
    /* GPIO_PIN_RESET means the touch sensor output went LOW (released) */
    if (ch_left.state == 2 &&
        HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_4) == GPIO_PIN_RESET) {
        if ((now - ch_left.press_tick) >= TOUCH_DEBOUNCE_MS &&
            (now - ch_left.press_tick) < TOUCH_HOLD_MS) {
            ch_left.pending_event = TOUCH_TAP;
            ch_left.event_ready = 1;
        }
        ch_left.state = 3;
    }
    if (ch_right.state == 2 &&
        HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_5) == GPIO_PIN_RESET) {
        if ((now - ch_right.press_tick) >= TOUCH_DEBOUNCE_MS &&
            (now - ch_right.press_tick) < TOUCH_HOLD_MS) {
            ch_right.pending_event = TOUCH_TAP;
            ch_right.event_ready = 1;
        }
        ch_right.state = 3;
    }

    /* Reset released channels back to idle after processing */
    if (ch_left.state == 3 && ch_left.event_ready == 0)  ch_left.state = 0;
    if (ch_right.state == 3 && ch_right.event_ready == 0) ch_right.state = 0;

    return 0;
}
