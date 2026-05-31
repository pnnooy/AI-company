#include "rc522_spi.h"
#include "stm32f1xx_hal.h"
#include "spi.h"

#define RC522_CS_PORT   GPIOA
#define RC522_CS_PIN    GPIO_PIN_4
#define RC522_RST_PORT  GPIOA
#define RC522_RST_PIN   GPIO_PIN_3

#define RC522_CS_LOW()   HAL_GPIO_WritePin(RC522_CS_PORT, RC522_CS_PIN, GPIO_PIN_RESET)
#define RC522_CS_HIGH()  HAL_GPIO_WritePin(RC522_CS_PORT, RC522_CS_PIN, GPIO_PIN_SET)
#define RC522_RST_LOW()  HAL_GPIO_WritePin(RC522_RST_PORT, RC522_RST_PIN, GPIO_PIN_RESET)
#define RC522_RST_HIGH() HAL_GPIO_WritePin(RC522_RST_PORT, RC522_RST_PIN, GPIO_PIN_SET)

/* RC522 register map (partial) */
#define RC522_REG_COMMAND    0x01
#define RC522_REG_COM_IRQ    0x04
#define RC522_REG_FIFO_DATA  0x09
#define RC522_REG_FIFO_LEVEL 0x0A
#define RC522_REG_TX_CONTROL 0x14
#define RC522_REG_TX_AUTO    0x15
#define RC522_REG_MODE       0x11
#define RC522_REG_T_MODE     0x2A
#define RC522_REG_T_PRESCAL  0x2B
#define RC522_REG_T_RELOAD   0x2C

/* RC522 commands */
#define RC522_CMD_IDLE       0x00
#define RC522_CMD_TRANSCEIVE 0x0C
#define RC522_CMD_SOFTRESET  0x0F

/* PCD → PICC commands */
#define PICC_CMD_REQA    0x26
#define PICC_CMD_WUPA    0x52
#define PICC_CMD_ANTICOLL 0x93
#define PICC_CMD_SEL_CL1  0x93
#define PICC_CMD_HALT     0x50

static uint8_t RC522_ReadReg(uint8_t reg) {
    uint8_t val;
    RC522_CS_LOW();
    /* Address byte: MSB=0 for read, then address << 1 */
    uint8_t addr = ((reg << 1) & 0x7E);
    HAL_SPI_TransmitReceive(&hspi1, &addr, &val, 1, 100);
    /* Read data: send dummy, receive real value */
    HAL_SPI_TransmitReceive(&hspi1, (uint8_t[]){0x00}, &val, 1, 100);
    RC522_CS_HIGH();
    return val;
}

static void RC522_WriteReg(uint8_t reg, uint8_t val) {
    RC522_CS_LOW();
    uint8_t addr = ((reg << 1) & 0x7E);
    HAL_SPI_Transmit(&hspi1, &addr, 1, 100);
    HAL_SPI_Transmit(&hspi1, &val, 1, 100);
    RC522_CS_HIGH();
}

static void RC522_ClearBitmask(uint8_t reg, uint8_t mask) {
    RC522_WriteReg(reg, RC522_ReadReg(reg) & ~mask);
}

static void RC522_SetBitmask(uint8_t reg, uint8_t mask) {
    RC522_WriteReg(reg, RC522_ReadReg(reg) | mask);
}

static void RC522_Reset(void) {
    RC522_RST_HIGH();
    HAL_Delay(10);
    RC522_RST_LOW();
    HAL_Delay(10);
    RC522_RST_HIGH();
    HAL_Delay(50);

    /* Soft reset */
    RC522_WriteReg(RC522_REG_COMMAND, RC522_CMD_SOFTRESET);
    HAL_Delay(100);

    /* Timer: TPrescaler * TModeReg, ~25us */
    RC522_WriteReg(RC522_REG_T_MODE, 0x80);
    RC522_WriteReg(RC522_REG_T_PRESCAL, 0xA9);
    RC522_WriteReg(RC522_REG_T_RELOAD, 0x03);
    RC522_WriteReg(RC522_REG_TX_AUTO, 0x40);
    RC522_WriteReg(RC522_REG_MODE, 0x3D);

    /* Clear internal CRC */
    RC522_ClearBitmask(0x05, 0x04);  /* clear CRC enabled bit */
}

static uint8_t RC522_ToCard(uint8_t cmd, uint8_t *send_data, uint8_t send_len,
                             uint8_t *back_data, uint8_t *back_len) {
    uint8_t irq_en  = 0x77;
    uint8_t wait_irq = 0x30;
    uint8_t n;

    if (cmd == PICC_CMD_REQA || cmd == PICC_CMD_WUPA) {
        irq_en  = 0x77;
        wait_irq = 0x30;
    } else if (cmd == PICC_CMD_ANTICOLL || cmd == PICC_CMD_SEL_CL1) {
        irq_en  = 0x77;
        wait_irq = 0x30;
    } else {
        irq_en  = 0x77;
        wait_irq = 0x30;
    }

    RC522_WriteReg(0x0D, irq_en);   /* CommIEnReg - enable interrupts */
    RC522_ClearBitmask(0x06, 0x80); /* CommIrqReg - clear all bits */
    RC522_ClearBitmask(0x0E, 0x80); /* DivIrqReg */
    RC522_SetBitmask(0x0A, 0x80);   /* FIFOLevelReg - flush FIFO */
    RC522_WriteReg(RC522_REG_COMMAND, RC522_CMD_IDLE);

    /* Write send data to FIFO */
    for (uint8_t i = 0; i < send_len; i++) {
        RC522_WriteReg(RC522_REG_FIFO_DATA, send_data[i]);
    }

    /* Execute command */
    RC522_WriteReg(RC522_REG_COMMAND, cmd);
    if (cmd == PICC_CMD_ANTICOLL || cmd == PICC_CMD_SEL_CL1) {
        RC522_SetBitmask(RC522_REG_TX_CONTROL, 0x03);
    }

    /* Wait for completion */
    uint32_t timeout = HAL_GetTick() + 50;
    do {
        n = RC522_ReadReg(RC522_REG_COM_IRQ);
        if (HAL_GetTick() > timeout) return 0;
    } while (!(n & 0x01) && !(n & wait_irq));

    RC522_ClearBitmask(0x06, 0x80);  /* clear timer interrupt */

    if (n & wait_irq) return 0;  /* error */

    /* Read back data */
    n = RC522_ReadReg(RC522_REG_FIFO_LEVEL);
    uint8_t last_bits = RC522_ReadReg(0x05) & 0x07;
    if (last_bits) *back_len = (n - 1) * 8 + last_bits;
    else           *back_len = n * 8;

    if (n == 0) n = 1;
    if (n > 16) n = 16;

    for (uint8_t i = 0; i < n; i++) {
        back_data[i] = RC522_ReadReg(RC522_REG_FIFO_DATA);
    }

    return 1;
}

uint8_t RC522_Init(void) {
    /* CS and RST GPIO init done by CubeMX */
    RC522_CS_HIGH();
    RC522_Reset();
    return 1;
}

uint8_t RC522_CheckCard(void) {
    uint8_t back_len = 0;
    uint8_t back_data[16];
    uint8_t send_data = PICC_CMD_REQA;
    return RC522_ToCard(PICC_CMD_REQA, &send_data, 1, back_data, &back_len);
}

uint8_t RC522_GetCardUID(uint8_t *uid_buf) {
    uint8_t back_len = 0;
    uint8_t back_data[16];

    /* REQA / WUPA */
    uint8_t cmd_reqa = PICC_CMD_REQA;
    if (!RC522_ToCard(PICC_CMD_REQA, &cmd_reqa, 1, back_data, &back_len)) {
        return 0;
    }

    /* Anticollision */
    uint8_t anticoll_cmd[2] = {PICC_CMD_ANTICOLL, 0x20};
    if (!RC522_ToCard(PICC_CMD_ANTICOLL, anticoll_cmd, 2, back_data, &back_len)) {
        return 0;
    }

    /* back_data[0..3] = UID, back_data[4] = BCC check */
    uint8_t uid_len = 4;
    for (uint8_t i = 0; i < uid_len && i < 16; i++) {
        uid_buf[i] = back_data[i];
    }

    /* Select card */
    uint8_t sel_cmd[7] = {PICC_CMD_SEL_CL1, 0x70};
    for (uint8_t i = 0; i < uid_len; i++) sel_cmd[i + 2] = uid_buf[i];
    /* CRC is auto-calculated by RC522 */
    uint8_t dummy_len = 0;
    uint8_t dummy[16];
    RC522_ToCard(PICC_CMD_SEL_CL1, sel_cmd, 7, dummy, &dummy_len);

    return uid_len;
}

void RC522_HaltCard(void) {
    uint8_t back_len = 0;
    uint8_t back_data[16];
    uint8_t halt_cmd[4] = {PICC_CMD_HALT, 0x00, 0x00, 0x00};
    RC522_ToCard(PICC_CMD_HALT, halt_cmd, 4, back_data, &back_len);
}
