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

/* ---- Error statistics ---- */
static UART_ErrorStats uart_err_stats = {0, 0, 0, 0};

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

/* ---- CRC-8 (polynomial 0x07) ---- */
static uint8_t calc_crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80)
                crc = (crc << 1) ^ 0x07;
            else
                crc <<= 1;
        }
    }
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
    /* New format: [A5][5A][LEN][CMD][PAYLOAD...][CRC8][EE] */
    uint8_t buf[38];  /* max: 2(sync) + 1(len) + 1(cmd) + 32(data) + 1(crc) + 1(end) = 38 */
    uint8_t body_buf[34];  /* CMD + PAYLOAD for CRC calculation */

    buf[0] = UART_SYNC0_BYTE;   /* 0xA5 */
    buf[1] = UART_SYNC1_BYTE;   /* 0x5A */
    buf[2] = 1 + len + 1;        /* LEN = CMD(1) + payload(len) + CRC(1) */

    /* Build body for CRC */
    body_buf[0] = cmd;
    if (len > 0 && payload) {
        memcpy(body_buf + 1, payload, len);
    }

    /* Copy body to frame */
    memcpy(buf + 3, body_buf, 1 + len);

    /* Calculate CRC-8 over body */
    buf[3 + 1 + len] = calc_crc8(body_buf, 1 + len);

    /* End byte */
    buf[4 + 1 + len] = UART_END_BYTE;  /* 0xEE */

    HAL_UART_Transmit(&huart1, buf, 6 + len, 100);
}

void UART_SendEvent(uint8_t event_id, const uint8_t *payload, uint8_t len) {
    UART_SendPacket(event_id, payload, len);
}

UART_ErrorStats* UART_GetErrorStats(void) {
    return &uart_err_stats;
}

void UART_ParseFrames(void) {
    static enum { WAIT_SYNC0, WAIT_SYNC1, GET_LEN, GET_BODY, GET_END } state = WAIT_SYNC0;
    static uint8_t pkt_len, pkt_idx;
    static uint8_t pkt_buf[34];  /* CMD(1) + DATA(32) + CRC(1) = 34 max */
    static uint32_t last_byte_tick = 0;

    uint32_t now = HAL_GetTick();

    /* Timeout detection (except WAIT_SYNC0) */
    if (state != WAIT_SYNC0 && (now - last_byte_tick) > UART_FRAME_TIMEOUT_MS) {
        state = WAIT_SYNC0;
        uart_err_stats.timeout++;
    }

    uint8_t b;
    while (ring_get(&b)) {
        last_byte_tick = now;

        switch (state) {
        case WAIT_SYNC0:
            if (b == UART_SYNC0_BYTE) state = WAIT_SYNC1;
            break;

        case WAIT_SYNC1:
            if (b == UART_SYNC1_BYTE) {
                state = GET_LEN;
            } else if (b == UART_SYNC0_BYTE) {
                /* Consecutive 0xA5, stay in WAIT_SYNC1 */
                state = WAIT_SYNC1;
            } else {
                state = WAIT_SYNC0;
            }
            break;

        case GET_LEN:
            /* LEN must be in range [2, 34] (including CRC) */
            if (b < 2 || b > 34) {
                uart_err_stats.invalid_len++;
                state = WAIT_SYNC0;
                break;
            }
            pkt_len = b;
            pkt_idx = 0;
            state = GET_BODY;
            break;

        case GET_BODY:
            pkt_buf[pkt_idx++] = b;
            if (pkt_idx >= pkt_len) state = GET_END;
            break;

        case GET_END:
            if (b == UART_END_BYTE) {
                /* pkt_buf = [CMD][DATA...][CRC] */
                uint8_t data_len = pkt_len - 1;  /* exclude CRC */
                uint8_t crc_received = pkt_buf[data_len];
                uint8_t crc_expected = calc_crc8(pkt_buf, data_len);

                if (crc_received == crc_expected) {
                    uint8_t cmd = pkt_buf[0];
                    /* Command direction filter: only accept PC→MCU (0x01~0x04) */
                    if (cmd >= 0x01 && cmd <= 0x04) {
                        if (cmd_callback) {
                            cmd_callback(cmd, pkt_buf + 1, data_len - 1);
                        }
                    }
                } else {
                    uart_err_stats.crc_fail++;
                }
            } else {
                uart_err_stats.end_byte_err++;
            }
            state = WAIT_SYNC0;
            break;

        default:
            state = WAIT_SYNC0;
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
