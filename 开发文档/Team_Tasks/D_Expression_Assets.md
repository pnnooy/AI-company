# 角色 D：表情素材设计

> **负责人**: D
> **工期**: 预计 2-3 天
> **前置条件**: 任意绘画软件（PS/Procreate/Aseprite/Krita），Python 3.8+ + Pillow 库

---

## 一、任务总览

为机器人设计 8 种表情共 14 帧的像素/板绘画稿，转成固件可直接使用的 C 数组文件。

**这是纯独立任务**，不依赖任何人，其他人也不阻塞你。你只需要按规格画完导出即可。

---

## 二、你在整个系统中的位置

```
你的 PNG 文件
    ↓ python tools/png2rgb565.py (自动转换)
C 数组文件 (.c/.h)
    ↓ Keil 编译
STM32 固件
    ↓ LCD 显示
机器人的脸
    ↓ 
用户看到 + 团队其他成员使用
```

你画的脸 = 机器人实际显示的脸。你是这个项目**视觉呈现的核心**。

---

## 三、技术硬约束

| 参数 | 值 | 原因 |
|------|-----|------|
| 画布 | **80 × 80 像素** | LCD 上 2× 缩放后显示为 160×160 |
| 背景 | **纯黑 #000000** | 黑 = 透明，只显示脸部 |
| 导出格式 | **PNG-24** (RGB, 无透明通道) | 转换脚本只读 R/G/B |
| 文件名 | **严格按下表** | 脚本靠文件名自动识别 |

### ⚠️ 最重要的三条

1. **背景必须是纯黑 `#000000`** —— 不是深灰、不是透明、不是 `#111111`。有任何非黑像素都会在 LCD 上显示成杂点。
2. **画布必须是 80×80** —— 不是 79、不是 81。MCU 按 `80*80=6400` 像素读取。
3. **导出 PNG-24 不带透明通道** —— PS 里选"另存为 → PNG-24"，不要选"快速导出为 PNG"（可能带透明）。

---

## 四、交付清单：8 种表情 × 14 帧

| # | 表情名 | 帧数 | 文件名 | 触发场景 |
|---|--------|------|--------|----------|
| 0 | 普通 NORMAL | 1 | `emo_normal_f0.png` | 开机默认、待机 |
| 1 | 开心 HAPPY | 3 | `emo_happy_f0~f2.png` | 用户触摸、交互反馈 |
| 2 | 专注 FOCUS | 2 | `emo_focus_f0~f1.png` | NFC 学习卡、学术问答 |
| 3 | 生气 ANGRY | 1 | `emo_angry_f0.png` | 倾倒告警、异常状态 |
| 4 | 休眠 SLEEP | 2 | `emo_sleep_f0~f1.png` | 长时间无交互 |
| 5 | 惊讶 SURPRISE | 1 | `emo_surprise_f0.png` | 摇晃触发、意外事件 |
| 6 | 难过 SAD | 2 | `emo_sad_f0~f1.png` | 情绪低落、无人理睬 |
| 7 | 爱心 LOVE | 2 | `emo_love_f0~f1.png` | 双击触摸、特别互动 |

**总计**：14 个 PNG 文件 + 源文件（PSD/Procreate 等保留图层）

---

## 五、每种表情的设计要求

> 详细版见 `开发文档/Expression_Design_Spec.md`，这里是精简版。

### 通用构图基准

```
80×80 画布:
- 脸部圆形：圆心 (40,40)，半径 ~35px
- 左眼圆心：~(28, 32)，右眼圆心：~(52, 32)
- 眼睛直径：正常 10-12px
- 嘴巴中心：y≈52-55
- 脸四周留 2-5px 黑边
```

### #0 NORMAL — 1 帧
- 圆脸 + 暖黄填充 + 白描边
- 黑色圆眼 ~10px + 白色高光点
- 嘴巴：平直线 2px

### #1 HAPPY — 3 帧
- f0: 弯眼 `^ ^` + 大笑弧线嘴
- f1: 半闭眨眼（眼睛变扁弧线）
- f2: 同 f0（或省略）
- 动画：200ms/帧，f0→f1→f0 循环

### #2 FOCUS — 2 帧
- 眯眼（宽椭圆）+ 紧嘴直线
- 可选蓝色眼镜框
- 动画：500ms 交替，高光微移

### #3 ANGRY — 1 帧
- **倒八字眉** `\ /`（核心特征）
- 锐利三角眼 + 下弯嘴
- 肤色偏红

### #4 SLEEP — 2 帧
- f0: 闭眼横线 `— —` + 打呼小圆嘴
- f1: 微睁眼（下半开）
- 动画：慢速 1000ms 交替

### #5 SURPRISE — 1 帧
- **大圆眼** ~14px（核心特征）
- O 型大嘴 + 小瞳孔

### #6 SAD — 2 帧
- 八字眉 + 下垂眼 + 下弯嘴
- f0: 有蓝色泪滴
- f1: 泪滴消失
- 动画：400ms 交替

### #7 LOVE — 2 帧
- **爱心眼睛 ♥**（核心特征）
- 微笑嘴 + 腮红
- 动画：300ms 交替，爱心大小微变

---

## 六、工作流程

### Step 1: 安装工具

```bash
pip install Pillow
```

### Step 2: 开始画

**推荐顺序**：NORMAL → HAPPY → SAD → ANGRY → SURPRISE → FOCUS → SLEEP → LOVE

1. 先画 `emo_normal_f0.png`（其他表情都在这张基础上改）
2. 先画静态帧（f0），再画动画帧（f1, f2）
3. 每画完一张就导出 PNG 到 `firmware/Assets/` 目录

### Step 3: 转换 + 验证

```bash
# 单张转换测试
python tools/png2rgb565.py firmware/Assets/emo_normal_f0.png
# 应输出: OK: emo_normal_f0.png → emo_normal_f0.c + emo_normal_f0.h  (80×80, 12.5 KB)

# 批量转换
python tools/png2rgb565.py firmware/Assets/emo_*.png

# 验证生成的 C 数组
python tools/png2rgb565.py --check firmware/App/emo_normal_f0.c
# 应输出: OK: ... 80×80, 6400 pixels, range [0x0000, 0xXXXX]
```

### Step 4: 生成固件用的整合文件

```bash
python tools/make_assets.py --size 80
# 会在 firmware/App/ 下生成 expression_assets.c 和 expression_assets.h
```

### Step 5: 烧录验证

1. 在 Keil 中打开工程，F7 编译
2. F8 烧录到板子
3. 板子启动后 LCD 显示 NORMAL 表情
4. 用 SSCOM 发命令切换表情验证效果

---

## 七、颜色调色板建议

```
皮肤:   #FFD89B (暖黄基色)    #FFE0B2 (浅暖黄)    #FFCC80 (橘调)
腮红:   #FF9E9E (粉色)        #FFAB91 (橘粉)
眼球:   #1A1A2E (深蓝黑)      #000000 (纯黑)
白色:   #FFFFFF (描边/高光)
深灰:   #4A4A4A (嘴线)
红色:   #FF5252 (生气/爱心)
蓝色:   #448AFF (专注/泪滴)
```

---

## 八、常见问题

| Q | A |
|---|---|
| 画 160×160 再缩小可以吗？ | 可以，但缩小用**最近邻插值**，别用双线性（会糊） |
| 能加渐变/半透明吗？ | 不能。RGB565 不支持透明和渐变 |
| 板子上颜色不对？ | 已知 LCD 颜色字节序问题，告诉 B 调整，不需要改图 |
| 需要把脸画满 80×80 吗？ | 不需要，脸部直径 ~70px，周围留黑边 |
| 能测试看效果吗？ | 先用 `make_assets.py --size 80` 生成，再 Keil 编译烧录 |

---

## 九、接口规范

### 与 A (固件) — 不需要直接沟通
PNG 转 C 数组由脚本自动完成，A 编译固件时会自动包含。

### 与 B (PC 后端)
| 项目 | 约定 |
|------|------|
| 表情 ID | 0=NORMAL, 1=HAPPY, 2=FOCUS, 3=ANGRY, 4=SLEEP, 5=SURPRISE, 6=SAD, 7=LOVE |
| 新增表情 | 需同步更新 `protocol.py` 和 `expression_types.h` 的枚举 |

### 与 E (文档/演示)
| 项目 | 约定 |
|------|------|
| 设计过程截图 | 画图过程中截几张屏，发给 E |
| 全表情预览图 | 8 种表情并排放在一张图上，发给 E |
| 风格灵感参考 | 找几个参考图发给 E，帮助 E 理解设计风格 |

---

## 十、完成标准

- [ ] 14 个 PNG 文件全部完成，存于 `firmware/Assets/`
- [ ] 所有 PNG 尺寸为 80×80，背景纯黑 #000000
- [ ] 命名严格：`emo_{name}_f{frame}.png`
- [ ] `png2rgb565.py` 全部转换成功
- [ ] `png2rgb565.py --check` 全部通过
- [ ] `make_assets.py --size 80` 完成，生成 expression_assets.c/.h
- [ ] 源文件保留（PSD/Procreate 等），可后续修改
- [ ] 全表情预览图发给团队群 review
- [ ] 至少 NORMAL 和 HAPPY 两种表情在板子上烧录验证过

---

## 十一、参考文件

| 文件 | 用途 |
|------|------|
| `开发文档/Expression_Design_Spec.md` | **完整设计规格书，画之前先读** |
| `tools/png2rgb565.py` | PNG→C 数组转换工具 |
| `tools/make_assets.py` | 整合生成 expression_assets.c/.h |
| `firmware/Assets/faceset1/` | 上一版 AI 生成的表情（质量一般，仅作参考风格） |
| `firmware/App/expression_assets.h` | 当前固件引用的帧表（生成后会被覆盖） |
