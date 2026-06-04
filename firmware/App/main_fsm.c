#include "main_fsm.h"
#include "expression_engine.h"
#include "rgb_led.h"
#include "touch_sensor.h"
#include "rc522_spi.h"
#include "mpu6050_hal.h"
#include "uart_comm.h"
#include "stm32f1xx_hal.h"
#include <stdio.h>

/*
 * Non-blocking main state machine.
 * States: IDLE → ACTIVE → INTERACT → IDLE → SLEEP
 *         Any → ALERT (on pose/motion event)
 */

#define IDLE_SLEEP_TIMEOUT_MS   300000   /* 5 min idle → sleep */
#define ACTIVE_TIMEOUT_MS       30000    /* 30s no interaction → idle */
#define INTERACT_TIMEOUT_MS     10000    /* 10s no input → active */

#define TOUCH_POLL_MS     10
#define NFC_POLL_MS       50
#define MPU_POLL_MS       20
#define EXPR_TICK_MS      50
#define DISPLAY_UPDATE_MS 16      /* ~60fps for animation smoothness */

static SystemState current_state;
static uint8_t     pose_enabled = 1;    /* MPU6050 polling on by default */
static uint8_t     nfc_enabled = 1;     /* NFC polling on by default */
static uint32_t    last_touch_tick;
static uint32_t    last_nfc_tick;
static uint32_t    last_mpu_tick;
static uint32_t    last_expr_tick;
static uint32_t    last_interact_tick;  /* last user interaction time */

void FSM_Init(void) {
    current_state      = SYS_IDLE;
    last_touch_tick    = 0;
    last_nfc_tick      = 0;
    last_mpu_tick      = 0;
    last_expr_tick     = 0;
    last_interact_tick = HAL_GetTick();

    Expression_Init();
    Expression_Set(EMO_NORMAL);
}

static const char* state_names[] = {"IDLE","ACTIVE","INTERACT","SLEEP","ALERT"};
static const char* touch_evt_names[] = {"NONE","TAP","DOUBLE","HOLD"};
static const char* side_names[] = {"LEFT","RIGHT"};

static void FSM_ChangeState(SystemState new_state) {
    if (new_state == current_state) return;
    UART_Printf("[FSM] %s -> %s\r\n", state_names[current_state], state_names[new_state]);
    current_state    = new_state;

    switch (new_state) {
    case SYS_IDLE:
        Expression_Set(EMO_NORMAL);
        RGB_Off();
        break;
    case SYS_ACTIVE:
        Expression_Set(EMO_NORMAL);
        RGB_SetColor(0, 0, 64);   /* dim blue */
        break;
    case SYS_INTERACT:
        /* expression set by interaction handler */
        break;
    case SYS_SLEEP:
        RGB_Off();
        /* Sleep expression handled by expression engine */
        break;
    case SYS_ALERT:
        RGB_SetColor(255, 0, 0);  /* red alert */
        Expression_Set(EMO_ANGRY);
        break;
    }
}

void FSM_Tick(void) {
    uint32_t now = HAL_GetTick();
    TouchResult touch;
    MPU6050_Data mpu_data;
    uint8_t card_uid[10];

    /* --- Scheduled tasks --- */

    /* Touch polling */
    if (now - last_touch_tick >= TOUCH_POLL_MS) {
        last_touch_tick = now;
        if (Touch_Poll(&touch)) {
            last_interact_tick = now;

            if (current_state == SYS_SLEEP) {
                FSM_ChangeState(SYS_IDLE);
            } else if (current_state == SYS_IDLE) {
                FSM_ChangeState(SYS_ACTIVE);
            } else if (current_state == SYS_ACTIVE) {
                FSM_ChangeState(SYS_INTERACT);
                Expression_Set(EMO_HAPPY);
                RGB_Breathe(255, 128, 0, 2000);  /* warm orange breathing */
            }

            /* Send touch event to PC (binary protocol) */
            uint8_t touch_payload[2] = { touch.side, touch.event };
            UART_SendPacket(UART_EVT_TOUCH, touch_payload, 2);

            /* Debug log (optional, can be removed in production) */
            UART_Printf("[TOUCH] %s %s\r\n",
                        side_names[touch.side], touch_evt_names[touch.event]);
        }
    }

    /* NFC polling - Simplified feeding mode (any card = food, duration = amount) */
    if (nfc_enabled && now - last_nfc_tick >= NFC_POLL_MS) {
        last_nfc_tick = now;
        static uint8_t  card_present_last = 0;
        static uint32_t feeding_start_time = 0;
        uint8_t card_present = RC522_CheckCard();

        /* Card just placed (edge detection) */
        if (card_present && !card_present_last) {
            feeding_start_time = now;
            last_interact_tick = now;

            if (current_state == SYS_SLEEP) {
                FSM_ChangeState(SYS_IDLE);
            } else {
                FSM_ChangeState(SYS_INTERACT);
            }

            Expression_Set(EMO_FOCUS);
            RGB_Breathe(0, 128, 255, 2000);  /* cyan breathing - feeding mode */
            UART_Printf("[NFC] Feeding started...\r\n");
        }

        /* Card removed (edge detection) */
        if (!card_present && card_present_last) {
            uint32_t feeding_duration_ms = now - feeding_start_time;
            uint32_t feeding_seconds = feeding_duration_ms / 1000;

            /* Determine feeding level */
            uint8_t level;
            const char* level_name;

            if (feeding_seconds < 3) {
                level = NFC_LEVEL_TAP;
                level_name = "tap";
                Expression_Set(EMO_NORMAL);
                RGB_SetColor(0, 255, 255);  /* cyan flash */
            } else if (feeding_seconds < 10) {
                level = NFC_LEVEL_SNACK;
                level_name = "snack";
                Expression_Set(EMO_HAPPY);
                RGB_Breathe(255, 200, 0, 2000);  /* warm yellow */
            } else if (feeding_seconds < 30) {
                level = NFC_LEVEL_MEAL;
                level_name = "meal";
                Expression_Set(EMO_LOVE);
                RGB_Breathe(255, 100, 200, 2000);  /* pink */
            } else {
                level = NFC_LEVEL_FEAST;
                level_name = "feast";
                Expression_Set(EMO_SURPRISE);
                RGB_SetColor(255, 0, 255);  /* magenta flash */
            }

            /* Send NFC feeding event to PC (new protocol) */
            uint8_t nfc_payload[3];
            nfc_payload[0] = feeding_seconds & 0xFF;        /* duration low byte */
            nfc_payload[1] = (feeding_seconds >> 8) & 0xFF; /* duration high byte */
            nfc_payload[2] = level;
            UART_SendPacket(UART_EVT_NFC, nfc_payload, 3);

            /* Debug log */
            UART_Printf("[NFC] Feeding: %lus - %s (level=%d)\r\n", feeding_seconds, level_name, level);
        }

        card_present_last = card_present;
    }

    /* MPU6050 polling */
    if (pose_enabled && now - last_mpu_tick >= MPU_POLL_MS) {
        last_mpu_tick = now;
        if (MPU6050_ReadData(&mpu_data)) {
            PoseState pose = MPU6050_DetectPose(&mpu_data);
            if (pose == POSE_FALL) {
                FSM_ChangeState(SYS_ALERT);

                /* Send pose event to PC (binary protocol) */
                uint8_t pose_payload[1] = { 0x01 };  /* 0x01 = FALL */
                UART_SendPacket(UART_EVT_POSE, pose_payload, 1);

                /* Debug log */
                UART_Printf("[POSE] FALL\r\n");
            } else if (pose == POSE_SHAKE) {
                last_interact_tick = now;
                if (current_state == SYS_SLEEP) FSM_ChangeState(SYS_IDLE);

                /* Send pose event to PC (binary protocol) */
                uint8_t pose_payload[1] = { 0x02 };  /* 0x02 = SHAKE */
                UART_SendPacket(UART_EVT_POSE, pose_payload, 1);

                /* Debug log */
                UART_Printf("[POSE] SHAKE\r\n");
            }
        }
    }

    /* Expression tick (animation) */
    if (now - last_expr_tick >= EXPR_TICK_MS) {
        last_expr_tick = now;
        Expression_Tick();
    }

    /* RGB LED effect update */
    RGB_Tick();

    /* UART frame parsing */
    UART_ParseFrames();

    /* --- State timeout transitions --- */
    uint32_t idle_time = now - last_interact_tick;

    switch (current_state) {
    case SYS_ACTIVE:
        if (idle_time >= ACTIVE_TIMEOUT_MS) {
            FSM_ChangeState(SYS_IDLE);
        }
        break;
    case SYS_INTERACT:
        if (idle_time >= INTERACT_TIMEOUT_MS) {
            FSM_ChangeState(SYS_ACTIVE);
        }
        break;
    case SYS_IDLE:
        if (idle_time >= IDLE_SLEEP_TIMEOUT_MS) {
            FSM_ChangeState(SYS_SLEEP);
            Expression_Set(EMO_SLEEP);
        }
        break;
    case SYS_SLEEP:
    case SYS_ALERT:
        /* Remain in these states until explicit event */
        break;
    }
}

SystemState FSM_GetState(void) {
    return current_state;
}

const char* FSM_StateString(SystemState s) {
    switch (s) {
        case SYS_IDLE:     return "IDLE";
        case SYS_ACTIVE:   return "ACTIVE";
        case SYS_INTERACT: return "INTERACT";
        case SYS_SLEEP:    return "SLEEP";
        case SYS_ALERT:    return "ALERT";
        default:           return "???";
    }
}

void FSM_SetPoseEnable(uint8_t en) {
    pose_enabled = en;
}

void FSM_SetNfcEnable(uint8_t en) {
    nfc_enabled = en;
}
