# -*- coding: utf-8 -*-
"""Generate cover images for showcase page sections."""
from PIL import Image, ImageDraw, ImageFont
import os
import sys

# Force UTF-8 outputs
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT_DIR = "showcase/covers"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Card definitions: (filename, emoji, title, subtitle)
COVERS_LARGE = [
    # Section 5 - Chat
    ("cover-chat.png",          "\U0001f4ac", "与皮皮对话", "多轮 AI 对话 · 拟人化交流"),
    # Section 6 - Touch
    ("cover-touch-demo.png",    "\U0001f446", "触摸传感器操作", "TTP223 电容触摸 · 左/右侧感应"),
    ("cover-touch-effect.png",  "\U0001f3ad", "触摸响应效果", "LCD 表情 + RGB 灯光联动"),
    # Section 7 - Accelerometer
    ("cover-accel-demo.png",    "\U0001f3c3", "摇晃 & 倾倒操作", "MPU6050 · SHAKE + TILT 检测"),
    ("cover-accel-effect.png",  "\U0001f632", "姿态响应效果", "摇晃→surprise · 倾倒→alert"),
    # Section 8 - Camera
    ("cover-camera-demo.png",   "\U0001f4f7", "摄像头情绪识别", "人脸检测 + 表情分析实时显示"),
    ("cover-camera-effect.png", "\U0001f60a", "皮皮情绪回应", "用户笑→皮皮开心 · 皱眉→关心"),
    # Section 9 - NFC
    ("cover-nfc-demo.png",      "\U0001f4b3", "NFC 卡片投喂操作", "MFRC-522 · 刷卡触发互动"),
    ("cover-nfc-effect.png",    "\U0001f354", "喂食响应效果", "LCD 表情 + AI 对话联动"),
]

W, H = 800, 500  # 16:10

# Colors - teal theme
BG_TOP = (15, 23, 42)
BG_BOT = (30, 41, 59)
ACCENT = (13, 148, 136)
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (148, 163, 184)
TEXT_BADGE = (100, 116, 139)

def load_font(size, emoji=False):
    if emoji:
        for name in ["seguiemj.ttf", "Segoe UI Emoji", "symbola.ttf"]:
            try:
                return ImageFont.truetype(name, size)
            except (IOError, OSError):
                continue
    for name in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "msyh.ttf",
                 "arial.ttf", "helvetica.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()

font_emoji = load_font(120, emoji=True)
font_title = load_font(36)
font_sub = load_font(20)
font_badge = load_font(16)

def make_cover(filename, emoji_char, title, subtitle):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    cx, cy = W // 2, H // 2 - 20

    # Accent glow
    for radius in range(180, 10, -1):
        alpha = int(30 * (radius / 180) * 0.3)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(*ACCENT, alpha)
        )

    # Top accent line
    draw.rectangle([0, 0, W, 3], fill=ACCENT)

    # Emoji
    bbox = draw.textbbox((0, 0), emoji_char, font=font_emoji)
    em_w = bbox[2] - bbox[0]
    em_h = bbox[3] - bbox[1]
    em_x = cx - em_w // 2
    em_y = (H - em_h) // 2 - 35
    draw.text((em_x, em_y), emoji_char, font=font_emoji, fill=TEXT_MAIN, embedded_color=True)

    # Title
    tw = draw.textlength(title, font=font_title)
    draw.text((cx - tw // 2, em_y + em_h + 12), title, font=font_title, fill=TEXT_MAIN)

    # Subtitle
    sw = draw.textlength(subtitle, font=font_sub)
    draw.text((cx - sw // 2, em_y + em_h + 58), subtitle, font=font_sub, fill=TEXT_SUB)

    # Badge
    badge = "Demo Cover"
    bw = draw.textlength(badge, font=font_badge)
    draw.text((W - bw - 18, H - 30), badge, font=font_badge, fill=TEXT_BADGE)

    filepath = os.path.join(OUTPUT_DIR, filename)
    img.save(filepath, "PNG")
    print("  OK " + filename + " (" + str(W) + "x" + str(H) + ")")

print("Generating cover images...")
for filename, emoji, title, subtitle in COVERS_LARGE:
    make_cover(filename, emoji, title, subtitle)

print("\nDone! " + str(len(COVERS_LARGE)) + " covers saved to " + OUTPUT_DIR + "/")
