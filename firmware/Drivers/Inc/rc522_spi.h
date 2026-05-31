#ifndef RC522_SPI_H
#define RC522_SPI_H

#include <stdint.h>

uint8_t RC522_Init(void);
uint8_t RC522_CheckCard(void);                  /* returns 1 if card present */
uint8_t RC522_GetCardUID(uint8_t *uid_buf);     /* returns UID length (0 = fail) */
void RC522_HaltCard(void);

#endif
