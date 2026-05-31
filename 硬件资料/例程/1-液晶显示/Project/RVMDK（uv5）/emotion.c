#include "emotion.h"
#include "./lcd/bsp_ili9341_lcd.h"

/* ---------------- ???? ---------------- */
#define EYE_GAP     100
#define EYE_Y_BASE  100

/* ????:???? */
static void Draw_FullCircle(uint16_t x, uint16_t y, uint16_t r, uint16_t color) {
    int i;
    LCD_SetTextColor(color);
    for (i = 0; i <= r; i++) ILI9341_DrawCircle(x, y, i, 0);
}

/* ????:????? */
static void Draw_ThickLine(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2, uint16_t color) {
    LCD_SetTextColor(color);
    ILI9341_DrawLine(x1, y1, x2, y2);
    ILI9341_DrawLine(x1, y1 + 1, x2, y2 + 1);
    ILI9341_DrawLine(x1 + 1, y1, x2 + 1, y2);
}

void Clear_Face(void) {
    LCD_SetBackColor(BLACK);
    ILI9341_Clear(0, 0, LCD_X_LENGTH, LCD_Y_LENGTH);
}

/* ---------------- ?????? ---------------- */
void Emotion_Render(Robot_Emotion emo, uint32_t frame) {
    // 1. ?????? (? -4 ? +4 ??????)
    int8_t breathe = (frame % 20 < 10) ? (frame % 10 - 5) : (5 - frame % 10);
    
    // 2. ????
    uint16_t cx = ACTUAL_CENTER_X;
    uint16_t cy = EYE_Y_BASE + breathe; // ??????
    uint16_t lx = cx - (EYE_GAP / 2);
    uint16_t rx = cx + (EYE_GAP / 2);

    // 3. ???? (?100??,95-98???????)
    uint8_t is_blinking = (frame % 80 > 76);

    Clear_Face();

    switch(emo) {
        case EMO_HAPPY:
            // ??
            Draw_FullCircle(cx - 100, cy + 45, 12, 0xFC10);
            Draw_FullCircle(cx + 100, cy + 45, 12, 0xFC10);
            if(is_blinking) { // ???
                Draw_ThickLine(lx-20, cy, lx+20, cy, WHITE);
                Draw_ThickLine(rx-20, cy, rx+20, cy, WHITE);
            } else { // ??+??
                Draw_FullCircle(lx, cy, 25, WHITE);
                Draw_FullCircle(lx, cy, 18, BLACK);
                Draw_FullCircle(lx+10, cy-10, 6, WHITE);
                Draw_FullCircle(rx, cy, 25, WHITE);
                Draw_FullCircle(rx, cy, 18, BLACK);
                Draw_FullCircle(rx+10, cy-10, 6, WHITE);
            }
            // ?? (?????)
            LCD_SetTextColor(YELLOW);
            ILI9341_DrawCircle(cx, cy + 60, 40, 0); 
            ILI9341_DrawCircle(cx, cy + 61, 40, 0); 
            break;

        case EMO_SLEEPY:
            // ?? (????)
            LCD_SetTextColor(BLUE);
            ILI9341_DrawCircle(lx, cy, 20, 0); ILI9341_DrawCircle(rx, cy, 20, 0);
            ILI9341_Clear(lx-25, cy, 50, 25); ILI9341_Clear(rx-25, cy, 50, 25);
            // ?? (??)
            ILI9341_DrawCircle(cx, cy + 80, 10, 1);
            // Zzz ?? (???????)
            LCD_SetTextColor(WHITE);
            ILI9341_DispString_EN(cx+80, 50 - (frame%30), "Z");
            break;

        case EMO_FOCUS:
            // ??
            Draw_ThickLine(lx-30, cy-40, lx+30, cy-35, WHITE);
            Draw_ThickLine(rx+30, cy-40, rx-30, cy-35, WHITE);
            // ????????
            int8_t scan = (frame % 40 < 20) ? (frame%20 - 10) : (10 - frame%20);
            Draw_FullCircle(lx, cy, 28, RED);
            Draw_FullCircle(lx + scan, cy, 12, BLACK);
            Draw_FullCircle(rx, cy, 28, RED);
            uint16_t r_scan_x = rx + scan; // ???????
            Draw_FullCircle(r_scan_x, cy, 12, BLACK);
            break;

        case EMO_ANGRY:
            // ???? (Angry ????)
            cx += (frame % 2 == 0) ? 2 : -2;
            // ????
            Draw_ThickLine(lx-35, cy-40, lx+35, cy-10, RED);
            Draw_ThickLine(rx+35, cy-40, rx-35, cy-10, RED);
            // ????
            LCD_SetTextColor(RED);
            ILI9341_DrawLine(lx-20, cy+10, lx+20, cy+10);
            ILI9341_DrawLine(rx-20, cy+10, rx+20, cy+10);
            // ??
            for(int j=0; j<3; j++) ILI9341_DrawCircle(cx, cy+110+j, 30, 0);
            ILI9341_Clear(cx-40, cy+110, 80, 30);
            break;
    }
}
