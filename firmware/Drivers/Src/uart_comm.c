#include "uart_comm.h"
#include "stm32f1xx_hal.h"
#include "usart.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

static uint8_t rx_buf[UART_RX_BUF_SIZE];
static uint8_t rx_head, rx_tail;
static uint8_t rx_byte;  /* 1-byte buffer for interrupt receive */
static UART_CmdCallback cmd_callback;
static UART_TextCallback text_callback;

/* ---- line buffer for text commands ---- */
static char line_buf[64];
static uint8_t line_idx;

void UART_Printf(const char *fmt, ...) {
    char buf[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    HAL_UART_Transmit(&huart1, (uint8_t *)buf, strlen(buf), 100);
}

/* ---- ring buffer ---- */
static void ring_put(uint8_t b) {
    uint8_t next = (rx_head + 1) % UART_RX_BUF_SIZE;
    if (next != rx_tail) {
        rx_buf[rx_head] = b;
        rx_head = next;
    }
}

static int ring_get(uint8_t *b) {
    if (rx_head == rx_tail) return 0;
    *b = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1) % UART_RX_BUF_SIZE;
    return 1;
}

/* ---- CRC ---- */
static uint8_t calc_crc(uint8_t cmd, uint8_t len, const uint8_t *payload) {
    uint8_t crc = cmd ^ len;
    for (uint8_t i = 0; i < len; i++) crc ^= payload[i];
    return crc;
}

/* ---- public API ---- */
void UART_Init(void) {
    rx_head = rx_tail = 0;
    line_idx = 0;
    cmd_callback = 0;
    text_callback = 0;
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    UART_Printf("UART Comm Ready\r\n");
}

void UART_RegisterCallback(UART_CmdCallback cb) {
    cmd_callback = cb;
}

void UART_RegisterTextCallback(UART_TextCallback cb) {
    text_callback = cb;
}

void UART_ProcessByte(uint8_t byte) {
    ring_put(byte);

    /* Also feed text line buffer */
    if (byte == '\r' || byte == '\n') {
        if (line_idx > 0) {
            line_buf[line_idx] = '\0';
            if (text_callback) text_callback(line_buf);
            line_idx = 0;
        }
    } else if (line_idx < sizeof(line_buf) - 1) {
        line_buf[line_idx++] = (char)byte;
    }
}

void UART_SendPacket(uint8_t cmd, const uint8_t *payload, uint8_t len) {
    uint8_t buf[36];
    buf[0] = UART_SYNC_BYTE;
    buf[1] = cmd;
    buf[2] = len;
    if (len > 0 && payload) memcpy(buf + 3, payload, len);
    buf[3 + len] = calc_crc(cmd, len, payload);
    HAL_UART_Transmit(&huart1, buf, 4 + len, 100);
}

void UART_SendEvent(uint8_t event_id, const uint8_t *payload, uint8_t len) {
    UART_SendPacket(event_id, payload, len);
}

void UART_ParseFrames(void) {
    static enum { WAIT_SYNC, GET_CMD, GET_LEN, GET_DATA, GET_CRC } state = WAIT_SYNC;
    static uint8_t pkt_cmd, pkt_len, pkt_idx;
    static uint8_t pkt_payload[UART_MAX_PAYLOAD];

    uint8_t b;
    while (ring_get(&b)) {
        switch (state) {
        case WAIT_SYNC:
            if (b == UART_SYNC_BYTE) state = GET_CMD;
            break;
        case GET_CMD:
            pkt_cmd = b;
            state = GET_LEN;
            break;
        case GET_LEN:
            pkt_len = (b > UART_MAX_PAYLOAD) ? 0 : b;
            pkt_idx = 0;
            state = (pkt_len > 0) ? GET_DATA : GET_CRC;
            break;
        case GET_DATA:
            pkt_payload[pkt_idx++] = b;
            if (pkt_idx >= pkt_len) state = GET_CRC;
            break;
        case GET_CRC:
            if (b == calc_crc(pkt_cmd, pkt_len, pkt_payload)) {
                if (cmd_callback) cmd_callback(pkt_cmd, pkt_payload, pkt_len);
            }
            state = WAIT_SYNC;
            break;
        }
    }
}

/* ---- HAL UART RX Complete Callback ---- */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart == &huart1) {
        UART_ProcessByte(rx_byte);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}
