#ifndef EXPRESSION_ASSETS_H
#define EXPRESSION_ASSETS_H

#include <stdint.h>
#include "expression_types.h"

#define EMO_FRAME_SIZE  40
#define EMO_PIXEL_COUNT 1600
#define EMO_MAX_FRAMES  3

extern const uint16_t emo_normal_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_happy_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_happy_f1[EMO_PIXEL_COUNT];
extern const uint16_t emo_happy_f2[EMO_PIXEL_COUNT];
extern const uint16_t emo_focus_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_focus_f1[EMO_PIXEL_COUNT];
extern const uint16_t emo_angry_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_sleep_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_sleep_f1[EMO_PIXEL_COUNT];
extern const uint16_t emo_surprise_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_sad_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_sad_f1[EMO_PIXEL_COUNT];
extern const uint16_t emo_love_f0[EMO_PIXEL_COUNT];
extern const uint16_t emo_love_f1[EMO_PIXEL_COUNT];

/* Frame table (defined in expression_assets.c) */
extern const uint8_t  emo_frame_count[];
extern const uint16_t emo_anim_ms[];
extern const uint16_t* const* emo_frames[];

#endif
