#!/usr/bin/env python3
"""
Expression Asset Generator

Takes PNG images, resizes to target size, generates combined C arrays
for the expression engine.

Setup:  pip install Pillow

Usage:
    # Resize & convert images in Assets/ to firmware/App/
    python tools/make_assets.py

    # With custom size (default 40)
    python tools/make_assets.py --size 48

    # Dry run: just see what would be generated
    python tools/make_assets.py --dry

Naming convention for PNG files in firmware/Assets/:
    emo_normal_f0.png   → EMO_NORMAL frame 0
    emo_happy_f0.png    → EMO_HAPPY frame 0
    emo_happy_f1.png    → EMO_HAPPY frame 1 (animation)
    emo_happy_f2.png    → EMO_HAPPY frame 2
    ... and so on for all 8 expressions.

If no PNGs found, generates simple test faces.
"""

import sys, os, math
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: pip install Pillow"); sys.exit(1)

PROJECT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT / "firmware" / "Assets"
OUTPUT_DIR = PROJECT / "firmware" / "App"
DEFAULT_SIZE = 40

EXPRESSIONS = {
    "normal":    {"name": "EMO_NORMAL",    "frames": 0, "anim_ms": 0},
    "happy":     {"name": "EMO_HAPPY",     "frames": 0, "anim_ms": 200},
    "focus":     {"name": "EMO_FOCUS",     "frames": 0, "anim_ms": 500},
    "angry":     {"name": "EMO_ANGRY",     "frames": 0, "anim_ms": 0},
    "sleep":     {"name": "EMO_SLEEP",     "frames": 0, "anim_ms": 1000},
    "surprise":  {"name": "EMO_SURPRISE",  "frames": 0, "anim_ms": 0},
    "sad":       {"name": "EMO_SAD",       "frames": 0, "anim_ms": 400},
    "love":      {"name": "EMO_LOVE",      "frames": 0, "anim_ms": 300},
}


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def resize_pixel_art(img, size):
    """Resize preserving pixel-art look (NEAREST)."""
    return img.resize((size, size), Image.NEAREST)


def img_to_rgb565(img):
    """Convert PIL RGB image to list of RGB565 uint16 values."""
    data = []
    pixels = img.getdata()
    for r, g, b in pixels:
        data.append(rgb565(r, g, b))
    return data


def generate_test_faces(size):
    """Generate simple test pixel-art faces for expressions."""
    import os
    assets_dir = ASSETS_DIR
    assets_dir.mkdir(parents=True, exist_ok=True)

    skin = (255, 220, 180)
    white = (255, 255, 255)
    black = (0, 0, 0)
    red = (255, 60, 60)
    pink = (255, 150, 180)

    cx, cy = size // 2, size // 2
    r_face = size // 2 - 2
    r_eye = max(2, size // 12)
    eye_y = cy - size // 8
    eye_lx = cx - size // 6
    eye_rx = cx + size // 6

    def draw_face(img, eye_state, mouth_color, mouth_func, blush=False):
        """Base face: circle + eyes + mouth."""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Face circle
        draw.ellipse([cx-r_face, cy-r_face, cx+r_face, cy+r_face],
                     fill=skin, outline=black)
        if blush:
            draw.ellipse([eye_lx-5, eye_y+5, eye_lx+7, eye_y+13], fill=pink)
            draw.ellipse([eye_rx-5, eye_y+5, eye_rx+7, eye_y+13], fill=pink)
        # Eyes
        if eye_state == "open":
            draw.ellipse([eye_lx-r_eye, eye_y-r_eye, eye_lx+r_eye, eye_y+r_eye], fill=black)
            draw.point([eye_lx, eye_y], fill=white)  # highlight
            draw.ellipse([eye_rx-r_eye, eye_y-r_eye, eye_rx+r_eye, eye_y+r_eye], fill=black)
            draw.point([eye_rx, eye_y], fill=white)
        elif eye_state == "half":
            draw.ellipse([eye_lx-r_eye, eye_y-r_eye//2, eye_lx+r_eye, eye_y+r_eye], fill=black)
            draw.ellipse([eye_rx-r_eye, eye_y-r_eye//2, eye_rx+r_eye, eye_y+r_eye], fill=black)
        elif eye_state == "closed":
            y = eye_y
            draw.line([eye_lx-r_eye, y, eye_lx+r_eye, y], fill=black, width=2)
            draw.line([eye_rx-r_eye, y, eye_rx+r_eye, y], fill=black, width=2)
        elif eye_state == "heart":
            # Simple heart: two dots + triangle
            hx, hy = eye_lx, eye_y
            draw.ellipse([hx-2, hy-2, hx, hy], fill=red)
            draw.ellipse([hx, hy-2, hx+2, hy], fill=red)
            hx, hy = eye_rx, eye_y
            draw.ellipse([hx-2, hy-2, hx, hy], fill=red)
            draw.ellipse([hx, hy-2, hx+2, hy], fill=red)

        # Mouth
        mouth_y = cy + size // 5
        mouth_func(draw, cy, mouth_y, r_face//2, black)

    def mouth_smile(draw, cy, my, mw, color):
        draw.arc([cx-mw//2, my-4, cx+mw//2, my+mw//2], 0, 180, fill=color, width=2)

    def mouth_flat(draw, cy, my, mw, color):
        draw.line([cx-mw//3, my, cx+mw//3, my], fill=color, width=2)

    def mouth_open(draw, cy, my, mw, color):
        draw.ellipse([cx-mw//3, my, cx+mw//3, my+mw//2], fill=color)

    def mouth_frown(draw, cy, my, mw, color):
        draw.arc([cx-mw//2, my+mw//2, cx+mw//2, my+mw], 180, 360, fill=color, width=2)

    def mouth_zzz(draw, cy, my, mw, color):
        draw.ellipse([cx-mw//4, my+2, cx+mw//4, my+mw//3], fill=color)

    specs = {
        "emo_normal_f0":   ("open",  black, mouth_flat),
        "emo_happy_f0":    ("open",  black, mouth_smile),
        "emo_happy_f1":    ("half",  black, mouth_smile),
        "emo_happy_f2":    ("open",  black, mouth_smile),
        "emo_focus_f0":    ("half",  black, mouth_flat),
        "emo_focus_f1":    ("half",  black, mouth_flat),
        "emo_angry_f0":    ("open",  red,   mouth_frown),
        "emo_sleep_f0":    ("closed",black, mouth_zzz),
        "emo_sleep_f1":    ("half",  black, mouth_zzz),
        "emo_surprise_f0": ("open",  black, mouth_open),
        "emo_sad_f0":      ("open",  black, mouth_frown),
        "emo_sad_f1":      ("closed",black, mouth_frown),
        "emo_love_f0":     ("heart", pink,  mouth_smile),
        "emo_love_f1":     ("heart", pink,  mouth_smile),
    }

    files = []
    for fname, (eyes, color, mouth_fn) in specs.items():
        img = Image.new("RGB", (size, size), (0, 0, 0))
        draw_face(img, eyes, color, mouth_fn)
        path = assets_dir / f"{fname}.png"
        img.save(path)
        files.append(fname)
        print(f"  Generated {fname}.png ({size}×{size})")

    return files


def scan_assets(size):
    """Scan Assets/ for PNG files matching expression naming."""
    assets_dir = ASSETS_DIR
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True, exist_ok=True)

    pngs = sorted(assets_dir.glob("emo_*.png"))

    if not pngs:
        print("No PNGs found, generating test faces...")
        generate_test_faces(size)
        pngs = sorted(assets_dir.glob("emo_*.png"))

    return pngs


def parse_name(png_path):
    """Parse emo_{name}_f{frame}.png → (name, frame)"""
    stem = png_path.stem
    parts = stem.split("_")
    if len(parts) >= 3 and parts[0] == "emo" and parts[2].startswith("f"):
        name = parts[1]
        try:
            frame = int(parts[2][1:])
        except ValueError:
            frame = 0
        return name, frame
    return stem, 0


def generate_assets(png_files, size):
    """Convert all PNGs to RGB565 and generate combined expression_assets.c/.h"""

    # Group by expression name
    frames = {}
    for png in png_files:
        name, fnum = parse_name(png)
        if name not in frames:
            frames[name] = {}
        img = Image.open(png).convert("RGB")
        if img.size != (size, size):
            img = resize_pixel_art(img, size)
        data = img_to_rgb565(img)
        frames[name][fnum] = data
        print(f"  {png.name}: {size}×{size} → {len(data)} pixels")

    # Map expression names to enum order
    expr_order = ["normal", "happy", "focus", "angry", "sleep", "surprise", "sad", "love"]

    # Find max frames per expression
    max_frames = 1
    for name in frames:
        nf = max(frames[name].keys()) + 1
        if nf > max_frames:
            max_frames = nf

    # Generate .h file
    h_path = OUTPUT_DIR / "expression_assets.h"
    with open(h_path, "w", encoding="utf-8") as f:
        f.write("#ifndef EXPRESSION_ASSETS_H\n")
        f.write("#define EXPRESSION_ASSETS_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write(f"#define EMO_FRAME_SIZE  {size}\n")
        f.write(f"#define EMO_PIXEL_COUNT {size * size}\n")
        f.write(f"#define EMO_MAX_FRAMES  {max_frames}\n")
        f.write(f"#define EMO_COUNT       8\n\n")

        # Forward declare each frame array
        for name in expr_order:
            if name in frames:
                for fn in sorted(frames[name].keys()):
                    f.write(f"extern const uint16_t emo_{name}_f{fn}[EMO_PIXEL_COUNT];\n")

        f.write("\n/* Frame table (defined in expression_assets.c) */\n")
        f.write("extern const uint8_t  emo_frame_count[];\n")
        f.write("extern const uint16_t emo_anim_ms[];\n")
        f.write("extern const uint16_t* const* emo_frames[];\n")

        f.write("\n#endif\n")

    # Generate .c file
    c_path = OUTPUT_DIR / "expression_assets.c"
    with open(c_path, "w", encoding="utf-8") as f:
        f.write('#include "expression_assets.h"\n')
        f.write('#include "expression_types.h"\n\n')

        # Write each frame data
        for name in expr_order:
            if name in frames:
                for fn in sorted(frames[name].keys()):
                    data = frames[name][fn]
                    f.write(f"const uint16_t emo_{name}_f{fn}[EMO_PIXEL_COUNT] = {{\n    ")
                    for i in range(0, len(data), 16):
                        vals = ", ".join(f"0x{v:04X}" for v in data[i:i+16])
                        if i + 16 < len(data):
                            f.write(f"{vals},\n    ")
                        else:
                            f.write(f"{vals}\n")
                    f.write("};\n\n")

        # Build frame pointer arrays per expression
        # (frame0, frame1, frame2, ...) for each expressions
        f.write("/* Frame arrays per expressions */\n")
        max_found = 1
        for name in expr_order:
            if name in frames:
                nf = max(frames[name].keys()) + 1
                if nf > max_found: max_found = nf

        for name in expr_order:
            if name in frames:
                nf = max(frames[name].keys()) + 1
                f.write(f"static const uint16_t* emo_{name}_frames[{max_found}] = {{")
                for fn in range(max_found):
                    if fn in frames[name]:
                        f.write(f"emo_{name}_f{fn}")
                    else:
                        f.write(f"emo_{name}_f0")  # fallback to frame0
                    if fn < max_found - 1:
                        f.write(", ")
                f.write("};\n")
            else:
                f.write(f"static const uint16_t* emo_{name}_frames[{max_found}] = {{0}};\n")

        # Build EmoDef table
        f.write(f"\n/* Expression definitions */\n")
        f.write(f"const uint8_t emo_frame_count[EMO_COUNT] = {{\n    ")
        for name in expr_order:
            if name in frames:
                nf = max(frames[name].keys()) + 1
            else:
                nf = 1
            f.write(f"{nf}, ")
        f.write("\n};\n\n")

        f.write(f"const uint16_t emo_anim_ms[EMO_COUNT] = {{\n    ")
        for name in expr_order:
            info = EXPRESSIONS.get(name, {"anim_ms": 0})
            f.write(f"{info['anim_ms']}, ")
        f.write("\n};\n\n")

        # The main frame table: const uint16_t** emo_frames[EMO_COUNT]
        f.write(f"const uint16_t* const* emo_frames[EMO_COUNT] = {{\n    ")
        for name in expr_order:
            f.write(f"emo_{name}_frames, ")
        f.write("\n};\n")

    total_kb = sum(len(frames[n][f]) * 2 for n in frames for f in frames[n]) / 1024
    print(f"\nDone: {c_path.name} + {h_path.name}")
    print(f"  Expressions: {len(frames)}")
    print(f"  Total frames: {sum(len(fs) for fs in frames.values())}")
    print(f"  Size: {size}×{size} per frame")
    print(f"  Flash used: {total_kb:.1f} KB")


def main():
    size = DEFAULT_SIZE
    dry = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--size" and i + 1 < len(args):
            size = int(args[i+1]); i += 2
        elif args[i] == "--dry":
            dry = True; i += 1
        else:
            print(f"Unknown: {args[i]}"); i += 1

    print(f"Expression Asset Generator (size={size})\n")

    png_files = scan_assets(size)

    if dry:
        for p in png_files:
            print(f"  Would process: {p.name}")
        print(f"\n  {len(png_files)} files total (dry run)")
        return

    generate_assets(png_files, size)


if __name__ == "__main__":
    main()
