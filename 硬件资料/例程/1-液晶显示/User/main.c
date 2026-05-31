#include "stm32f10x.h"
#include "./lcd/bsp_ili9341_lcd.h"
#include "bsp_led.h"
#include "emotion.h"

int main(void) {
    uint32_t frame_count = 0;
    uint8_t emotion_select = 0;
    
    ILI9341_Init();
    LED_GPIO_Config();
    ILI9341_GramScan(6);

    while(1) {
        // 1. ??200??????? (? 6-10 ?)
        if(frame_count % 200 == 0) {
            emotion_select = (emotion_select + 1) % 4;
            // ????
            if(emotion_select == 0) LED_SetColor(2); // ? (Happy)
            if(emotion_select == 1) LED_SetColor(3); // ? (Sleepy)
            if(emotion_select == 2) LED_SetColor(5); // ? (Focus)
            if(emotion_select == 3) LED_SetColor(1); // ? (Angry)
        }

        // 2. ?????
        Emotion_Render((Robot_Emotion)emotion_select, frame_count);

        // 3. ???? (????,?????,??????)
        for(uint32_t d = 0; d < 0x1FFFFF; d++); 

        frame_count++;
    }
}
