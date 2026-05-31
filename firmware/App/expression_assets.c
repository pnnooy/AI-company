/*
 * EXPRESSION ASSETS - PLACEHOLDER FILE
 *
 * This file must be populated with actual expression image data.
 * For each expression, include the generated .h and add an entry to the table.
 *
 * Generate image data with:
 *   python tools/png2rgb565.py emo_*.png
 *
 * Template:
 *   #include "emo_normal_f0.h"
 *   #include "emo_happy_f0.h"
 *   #include "emo_happy_f1.h"
 *   #include "emo_happy_f2.h"
 *   ...
 */

#include "expression_types.h"

/*
 * TODO: Replace with actual includes and table entries when images are ready.
 *
 * Example entry:
 * {
 *   .frames           = { emo_normal_f0 },
 *   .frame_count      = 1,
 *   .frame_interval_ms = 0,        // static
 *   .width            = 80,
 *   .height           = 80,
 * },
 */

const ExpressionDef expression_table[EMO_COUNT] = {
    [EMO_NORMAL]   = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 0, .width = 80, .height = 80 },
    [EMO_HAPPY]    = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 200, .width = 80, .height = 80 },
    [EMO_FOCUS]    = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 500, .width = 80, .height = 80 },
    [EMO_ANGRY]    = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 0, .width = 80, .height = 80 },
    [EMO_SLEEP]    = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 1000, .width = 80, .height = 80 },
    [EMO_SURPRISE] = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 0, .width = 80, .height = 80 },
    [EMO_SAD]      = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 400, .width = 80, .height = 80 },
    [EMO_LOVE]     = { .frames = {0}, .frame_count = 0, .frame_interval_ms = 300, .width = 80, .height = 80 },
};
