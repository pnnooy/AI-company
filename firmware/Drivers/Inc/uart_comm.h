#ifndef UART_COMM_H
#define UART_COMM_H

#include <stdint.h>

/* Protocol frame format (NEW):
 * ┌──────┬──────┬──────┬──────────────┬──────┬──────┐
 * │ SYNC │ SYNC │ LEN  │   PAYLOAD    │ CRC  │ END  │
 * │ 0xA5 │ 0x5A │  1B  │ CMD(1B)+Data │ CRC-8│ 0xEE │
 * └──────┴──────┴──────┴──────────────┴──────┴──────┘
 *
 * LEN: Total payload including CRC, range [2, 34]
 * CRC-8: Polynomial 0x07, covers PAYLOAD only
 * Timeout: 100ms frame receive timeout
 */

#define UART_SYNC0_BYTE  0xA5
#define UART_SYNC1_BYTE  0x5A
#define UART_END_BYTE    0xEE
#define UART_MAX_PAYLOAD 32
#define UART_RX_BUF_SIZE 128
#define UART_FRAME_TIMEOUT_MS 100

/* Command IDs (PC → MCU, 0x01~0x04) */
#define UART_CMD_SET_EXPR  0x01   /* payload: [emo_id:1B] */
#define UART_CMD_SET_RGB   0x02   /* payload: [R:1B][G:1B][B:1B] */
#define UART_CMD_QUERY     0x03   /* query status, no payload */
#define UART_CMD_HEARTBEAT 0x04   /* heartbeat/ping, payload: [seq:1B] */

/* Event IDs (MCU → PC, 0x05, 0x10~0x12) */
#define UART_EVT_ACK       0x05   /* payload: [ack_cmd:1B][status:1B] */
#define UART_EVT_TOUCH     0x10   /* payload: [side:1B][type:1B] */
#define UART_EVT_NFC       0x11   /* payload: [duration_low:1B][duration_high:1B][level:1B] */
#define UART_EVT_POSE      0x12   /* payload: [state:1B] */

/* NFC feeding level definitions */
#define NFC_LEVEL_TAP   0  /* < 3 seconds */
#define NFC_LEVEL_SNACK 1  /* 3-10 seconds */
#define NFC_LEVEL_MEAL  2  /* 10-30 seconds */
#define NFC_LEVEL_FEAST 3  /* > 30 seconds */

/* Error statistics (for debugging) */
typedef struct {
    uint32_t invalid_len;
    uint32_t crc_fail;
    uint32_t end_byte_err;
    uint32_t timeout;
} UART_ErrorStats;

typedef void (*UART_CmdCallback)(uint8_t cmd, const uint8_t *payload, uint8_t len);
typedef void (*UART_TextCallback)(const char *line);

void UART_Init(void);
void UART_RegisterCallback(UART_CmdCallback cb);
void UART_RegisterTextCallback(UART_TextCallback cb);
void UART_SendPacket(uint8_t cmd, const uint8_t *payload, uint8_t len);
void UART_SendEvent(uint8_t event_id, const uint8_t *payload, uint8_t len);
void UART_ProcessByte(uint8_t byte);
void UART_Printf(const char *fmt, ...);
void UART_ParseFrames(void);
UART_ErrorStats* UART_GetErrorStats(void);

#endif
