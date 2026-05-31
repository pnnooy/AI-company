#ifndef __EMOTION_H
#define __EMOTION_H
#include "stm32f10x.h"

/* ????????? */
#define ACTUAL_CENTER_X  142 

/* ?????? */
typedef enum {
    EMO_HAPPY = 0,
    EMO_SLEEPY,
    EMO_FOCUS,
    EMO_ANGRY
} Robot_Emotion;

/* ?????? */
void Emotion_Render(Robot_Emotion emo, uint32_t frame);
void Clear_Face(void);

#endif
