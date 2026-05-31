#ifndef __BSP_LED_H
#define __BSP_LED_H
#include "stm32f10x.h"

#define LED_R_ON   GPIO_ResetBits(GPIOB, GPIO_Pin_5)
#define LED_R_OFF  GPIO_SetBits(GPIOB, GPIO_Pin_5)
#define LED_G_ON   GPIO_ResetBits(GPIOB, GPIO_Pin_0)
#define LED_G_OFF  GPIO_SetBits(GPIOB, GPIO_Pin_0)
#define LED_B_ON   GPIO_ResetBits(GPIOB, GPIO_Pin_1)
#define LED_B_OFF  GPIO_SetBits(GPIOB, GPIO_Pin_1)

void LED_GPIO_Config(void);
void LED_SetColor(uint8_t color); // 0:?, 1:?, 2:?, 3:?, 4:?, 5:?
#endif
