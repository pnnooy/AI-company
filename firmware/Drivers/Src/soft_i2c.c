#include "soft_i2c.h"
#include "stm32f1xx_hal.h"

/*
 * Software I2C on PA11(SCL) / PA12(SDA).
 * Used because FSMC NADV conflicts with I2C1 hardware on PB7.
 * Per 野火指南者 MPU6050 chapter recommendation.
 */

#define SCL_PORT  GPIOA
#define SCL_PIN   GPIO_PIN_11
#define SDA_PORT  GPIOA
#define SDA_PIN   GPIO_PIN_12

#define SCL_H()   HAL_GPIO_WritePin(SCL_PORT, SCL_PIN, GPIO_PIN_SET)
#define SCL_L()   HAL_GPIO_WritePin(SCL_PORT, SCL_PIN, GPIO_PIN_RESET)
#define SDA_H()   HAL_GPIO_WritePin(SDA_PORT, SDA_PIN, GPIO_PIN_SET)
#define SDA_L()   HAL_GPIO_WritePin(SDA_PORT, SDA_PIN, GPIO_PIN_RESET)
#define SDA_RD()  HAL_GPIO_ReadPin(SDA_PORT, SDA_PIN)

static void delay_us(uint32_t us) {
    /* ~72 cycles per us at 64MHz, adjusted for overhead */
    uint32_t cnt = us * 8;
    while (cnt--) { __NOP(); }
}

void SoftI2C_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin = SCL_PIN | SDA_PIN;
    g.Mode = GPIO_MODE_OUTPUT_OD;
    g.Pull = GPIO_PULLUP;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);

    SCL_H();
    SDA_H();
}

static void i2c_start(void) {
    SDA_H(); delay_us(5);
    SCL_H(); delay_us(5);
    SDA_L(); delay_us(5);
    SCL_L(); delay_us(5);
}

static void i2c_stop(void) {
    SDA_L(); delay_us(5);
    SCL_H(); delay_us(5);
    SDA_H(); delay_us(5);
}

static uint8_t i2c_wait_ack(void) {
    SDA_H();
    SCL_H();
    delay_us(5);
    uint8_t ack = SDA_RD();
    SCL_L();
    delay_us(5);
    return (ack == 0);  /* 0 = ACK, 1 = NACK */
}

static void i2c_send_byte(uint8_t data) {
    for (int i = 0; i < 8; i++) {
        if (data & 0x80) SDA_H(); else SDA_L();
        data <<= 1;
        delay_us(2);
        SCL_H();
        delay_us(4);
        SCL_L();
        delay_us(2);
    }
}

static uint8_t i2c_read_byte(uint8_t ack) {
    uint8_t data = 0;
    SDA_H();  /* release SDA for slave */
    for (int i = 0; i < 8; i++) {
        data <<= 1;
        SCL_H();
        delay_us(4);
        if (SDA_RD()) data |= 1;
        SCL_L();
        delay_us(2);
    }
    /* send ACK/NACK */
    if (ack) SDA_L(); else SDA_H();
    delay_us(2);
    SCL_H();
    delay_us(4);
    SCL_L();
    delay_us(2);
    SDA_H();
    return data;
}

uint8_t SoftI2C_WriteReg(uint8_t dev_addr, uint8_t reg, uint8_t val) {
    i2c_start();
    i2c_send_byte(dev_addr << 1);       /* write */
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    i2c_send_byte(reg);
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    i2c_send_byte(val);
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    i2c_stop();
    return 1;
}

uint8_t SoftI2C_ReadReg(uint8_t dev_addr, uint8_t reg, uint8_t *data, uint8_t len) {
    i2c_start();
    i2c_send_byte(dev_addr << 1);       /* write for register address */
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    i2c_send_byte(reg);
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    i2c_stop();

    /* Repeated start for read */
    i2c_start();
    i2c_send_byte((dev_addr << 1) | 1); /* read */
    if (!i2c_wait_ack()) { i2c_stop(); return 0; }
    for (uint8_t i = 0; i < len; i++) {
        data[i] = i2c_read_byte(i < len - 1);  /* ACK all but last */
    }
    i2c_stop();
    return 1;
}
