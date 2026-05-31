#include "bsp_led.h"

void LED_GPIO_Config(void) {
    GPIO_InitTypeDef GPIO_InitStructure;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1 | GPIO_Pin_5;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOB, &GPIO_InitStructure);
    LED_R_OFF; LED_G_OFF; LED_B_OFF; // ????
}

void LED_SetColor(uint8_t color) {
    LED_R_OFF; LED_G_OFF; LED_B_OFF;
    switch(color) {
        case 1: LED_R_ON; break; // ?
        case 2: LED_G_ON; break; // ?
        case 3: LED_B_ON; break; // ?
        case 4: LED_R_ON; LED_G_ON; break; // ?
        case 5: LED_R_ON; LED_G_ON; LED_B_ON; break; // ?
    }
}
