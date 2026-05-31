#ifndef SOFT_I2C_H
#define SOFT_I2C_H

#include <stdint.h>

#define MPU6050_ADDR  0x68  /* AD0 = floating → 0x68 */

void SoftI2C_Init(void);
uint8_t SoftI2C_WriteReg(uint8_t dev_addr, uint8_t reg, uint8_t val);
uint8_t SoftI2C_ReadReg(uint8_t dev_addr, uint8_t reg, uint8_t *data, uint8_t len);

#endif
