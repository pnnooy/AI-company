#ifndef EXPRESSION_TYPES_H
#define EXPRESSION_TYPES_H

#include <stdint.h>

typedef enum {
    EMO_NORMAL = 0,
    EMO_HAPPY,
    EMO_FOCUS,
    EMO_ANGRY,
    EMO_SLEEP,
    EMO_SURPRISE,
    EMO_SAD,
    EMO_LOVE,
    EMO_COUNT
} Expression;

typedef struct {
    const uint16_t *frames[4];    /* up to 4 frames per expression */
    uint8_t frame_count;          /* actual number of frames */
    uint16_t frame_interval_ms;   /* ms between frames (0 = static) */
    uint8_t width;                /* image width (pixels) */
    uint8_t height;               /* image height (pixels) */
} ExpressionDef;

/* declared in expression_assets.c (auto-generated or hand-written) */
extern const ExpressionDef expression_table[EMO_COUNT];

#endif
