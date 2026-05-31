#ifndef TOUCH_SENSOR_H
#define TOUCH_SENSOR_H

#include <stdint.h>

typedef enum {
    TOUCH_LEFT  = 0,
    TOUCH_RIGHT = 1
} TouchSide;

typedef enum {
    TOUCH_NONE   = 0,
    TOUCH_TAP,        /* single short press */
    TOUCH_DOUBLE,     /* double tap (both sides simultaneously) */
    TOUCH_HOLD        /* long press (>1s) */
} TouchEvent;

typedef struct {
    TouchSide side;
    TouchEvent event;
} TouchResult;

void Touch_Init(void);
uint8_t Touch_Poll(TouchResult *result);  /* returns 1 if event available */
void Touch_IRQ_Left(void);   /* called from EXTI callback for PC4 */
void Touch_IRQ_Right(void);  /* called from EXTI callback for PC5 */

#endif
