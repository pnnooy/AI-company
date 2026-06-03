#ifndef RC522_SPI_H
#define RC522_SPI_H

#include <stdint.h>

uint8_t RC522_Init(void);
uint8_t RC522_GetVersion(void);                 /* VersionReg: 0x92=genuine, 0x88=clone, 0x00/0xFF=SPI fail */
uint8_t RC522_CheckCard(void);                  /* returns 1 if card present */
uint8_t RC522_GetCardUID(uint8_t *uid_buf);     /* returns UID length (0 = fail) */
void RC522_HaltCard(void);
uint8_t RC522_ReadReg(uint8_t reg);             /* for debug: read any register */
void RC522_WriteReg(uint8_t reg, uint8_t val);  /* for debug: write any register */
void RC522_Wakeup(void);                         /* SPI warm-up before register dumps */

#endif
