#ifndef MAIN_FSM_H
#define MAIN_FSM_H

#include <stdint.h>

typedef enum {
    SYS_IDLE = 0,
    SYS_ACTIVE,
    SYS_INTERACT,
    SYS_SLEEP,
    SYS_ALERT
} SystemState;

void FSM_Init(void);
void FSM_Tick(void);
SystemState FSM_GetState(void);
const char* FSM_StateString(SystemState s);
void FSM_SetPoseEnable(uint8_t en);
void FSM_SetNfcEnable(uint8_t en);

#endif
