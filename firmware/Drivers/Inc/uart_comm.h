#ifndef UART_COMM_H
#define UART_COMM_H

#include <stdint.h>

/* Protocol frame format: [SYNC:1B][CMD:1B][LEN:1B][PAYLOAD:0-32B][CRC:1B]
 * SYNC byte: 0xA5
 * CRC: XOR of CMD + LEN + PAYLOAD bytes
 */

#define UART_SYNC_BYTE   0xA5
#define UART_MAX_PAYLOAD 32
#define UART_RX_BUF_SIZE 128

/* Command IDs */
#define UART_CMD_EMOTION    0x01   /* payload: [emo_id:1B] */
#define UART_CMD_RGB        0x02   /* payload: [R:1B][G:1B][B:1B] */
#define UART_CMD_SENSOR_REQ 0x03   /* request sensor status, no payload */
#define UART_CMD_HEARTBEAT  0x04   /* heartbeat/ping, no payload */
#define UART_CMD_ACK        0x05   /* ACK, payload: [ack_cmd:1B] */

/* Event IDs (MCU → PC) */
#define UART_EVT_TOUCH      0x10   /* payload: [side:1B][type:1B] */
#define UART_EVT_CARD       0x11   /* payload: [uid_len:1B][uid:N] */
#define UART_EVT_POSE       0x12   /* payload: [state:1B] */
#define UART_EVT_HEARTBEAT  0x13   /* response to heartbeat */

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
void UART_ParseText(void);

#endif
