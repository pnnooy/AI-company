# 表情素材开发任务书

## 交付物
8 组表情的 PNG 源文件 + 对应的 RGB565 C 数组文件

---

## 技术规格

| 参数 | 值 |
|------|-----|
| 单帧尺寸 | **80 × 80 像素** |
| 颜色格式 | **RGB565** (16-bit: R=5bit, G=6bit, B=5bit) |
| 背景色 | **纯黑 #000000** (RGB565=0x0000) |
| 输出格式 | C 语言数组 `const uint16_t name[]` |
| 文件命名 | `emo_{表情名}_f{帧号}.c` 和 `.h` |

---

## 需要交付的表情清单 (共 8 组, 14 帧)

### 1. 普通/默认 `emo_normal`
- 帧数: **1 帧** (静态)
- 视觉效果: 圆形眼睛, 平直或微弯嘴巴, 中性表情
- 文件名: `emo_normal_f0`

### 2. 开心 `emo_happy`
- 帧数: **3 帧** (眨眼动画: 睁眼→半闭→睁眼)
- 视觉效果: ^_^ 弯曲笑眼, 微笑/张嘴笑弧线
- 文件名: `emo_happy_f0`, `emo_happy_f1`, `emo_happy_f2`
- 动画节奏: 每 200ms 一帧, 循环播放

### 3. 专注 `emo_focus`
- 帧数: **2 帧** (眼镜高光微动)
- 视觉效果: 眼睛略微眯起, 可加眼镜框或专注符号, 嘴巴紧闭或直线
- 文件名: `emo_focus_f0`, `emo_focus_f1`
- 动画节奏: 每 500ms 交替

### 4. 生气 `emo_angry`
- 帧数: **1 帧** (静态)
- 视觉效果: 倒八字眉, 三角眼或锐利眼神, 下弯嘴
- 文件名: `emo_angry_f0`

### 5. 困倦/休眠 `emo_sleep`
- 帧数: **2 帧** (闭眼→微睁)
- 视觉效果: 闭眼线(-_-), 嘴巴小圈或打呼符号
- 文件名: `emo_sleep_f0`, `emo_sleep_f1`
- 动画节奏: 每 1000ms 交替 (慢速呼吸感)

### 6. 惊讶 `emo_surprise`
- 帧数: **1 帧** (静态)
- 视觉效果: 大圆眼睛, 小瞳孔, 张开的大嘴(O形)
- 文件名: `emo_surprise_f0`

### 7. 难过 `emo_sad`
- 帧数: **2 帧** (眼泪闪烁)
- 视觉效果: 下垂眼, 八字眉, 下弯嘴, 可加泪滴
- 文件名: `emo_sad_f0`, `emo_sad_f1`
- 动画节奏: 每 400ms 交替 (泪滴闪烁)

### 8. 爱心 `emo_love`
- 帧数: **2 帧** (爱心大小变化)
- 视觉效果: 爱心形眼睛(♥), 微笑嘴, 可选腮红
- 文件名: `emo_love_f0`, `emo_love_f1`
- 动画节奏: 每 300ms 交替 (心跳感)

---

## 输出 C 数组格式要求

每个 `.h` 文件格式:
```c
#ifndef EMO_NORMAL_F0_H
#define EMO_NORMAL_F0_H

#include <stdint.h>

#define EMO_WIDTH  80
#define EMO_HEIGHT 80

extern const uint16_t emo_normal_f0[EMO_WIDTH * EMO_HEIGHT];

#endif
```

每个 `.c` 文件格式:
```c
#include "emo_normal_f0.h"

const uint16_t emo_normal_f0[EMO_WIDTH * EMO_HEIGHT] = {
    0x0000, 0x0000, 0x0000, ...  // 共 6400 个 uint16_t 值
};
```

数组值直接为 RGB565 格式: `(R>>3)<<11 | (G>>2)<<5 | (B>>3)` 或 `0xRRGGBB` → `0bRRRRRGGGGGGBBBBB`

---

## 设计风格参考

- 风格: **简约圆润可爱风** (类似 Line Friends / 聊天表情)
- 线条: 白色或浅色描边 (~2px)
- 填充: 亮色块 (黄/橙/粉肤色)
- 细节: 眼睛约 8-12px 直径, 嘴巴线条 2-3px 粗
- 屏幕实际显示尺寸: 3.2寸 320×240 LCD, 80×80 占屏幕约 1/4 面积居中显示

---

## 验证方式

生成后可用 Python 脚本验证:
```bash
python tools/png2rgb565.py --check emo_normal_f0.c
# 应输出: 80x80, 6400 pixels, format RGB565, all values in range 0x0000-0xFFFF
```
