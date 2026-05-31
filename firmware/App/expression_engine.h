#ifndef EXPRESSION_ENGINE_H
#define EXPRESSION_ENGINE_H

#include "expression_types.h"

void Expression_Init(void);
void Expression_Set(Expression emo);
Expression Expression_Get(void);
void Expression_Tick(void);       /* call from main loop, handles animation */
void Expression_ForceRedraw(void);

#endif
