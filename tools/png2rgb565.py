#!/usr/bin/env python3
"""PNG to RGB565 C array converter for ILI9341 expression system.

Usage:
    python png2rgb565.py emo_happy_f0.png              # generates emo_happy_f0.c + .h
    python png2rgb565.py *.png                          # batch convert all PNGs
    python png2rgb565.py --check emo_happy_f0.c         # validate a generated C array
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. Install: pip install Pillow")
    sys.exit(1)


def rgb888_to_rgb565(r, g, b):
    """Convert 8-bit RGB to 16-bit RGB565."""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def png_to_c_array(png_path, output_dir=None):
    """Convert a PNG file to RGB565 C source + header files."""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size

    if w != h:
        print(f"WARNING: {png_path} is {w}x{h}, expected square. Continuing anyway.")

    name = Path(png_path).stem
    pixels = list(img.getdata())

    if output_dir is None:
        output_dir = Path(png_path).parent

    # Generate header file
    h_path = os.path.join(output_dir, f"{name}.h")
    with open(h_path, "w", encoding="utf-8") as f:
        f.write(f"#ifndef {name.upper()}_H\n")
        f.write(f"#define {name.upper()}_H\n\n")
        f.write("#include <stdint.h>\n\n")
        f.write(f"#define {name.upper()}_W  {w}\n")
        f.write(f"#define {name.upper()}_H  {h}\n\n")
        f.write(f"extern const uint16_t {name}[{w * h}];\n\n")
        f.write(f"#endif\n")

    # Generate source file
    c_path = os.path.join(output_dir, f"{name}.c")
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(f'#include "{name}.h"\n\n')
        f.write(f"const uint16_t {name}[{w} * {h}] = {{\n    ")

        values = []
        for r, g, b in pixels:
            values.append(f"0x{rgb888_to_rgb565(r, g, b):04X}")

        # Format with 16 values per line
        for i in range(0, len(values), 16):
            line = ", ".join(values[i:i+16])
            if i + 16 < len(values):
                f.write(f"{line},\n    ")
            else:
                f.write(f"{line}\n")

        f.write("};\n")

    size_kb = (w * h * 2) / 1024
    print(f"OK: {png_path} → {name}.c + {name}.h  ({w}×{h}, {size_kb:.1f} KB)")

    return c_path, h_path


def check_c_array(c_path):
    """Validate a generated C array file."""
    with open(c_path, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(r"0x([0-9A-Fa-f]{4})", content)
    if not matches:
        print(f"ERROR: No RGB565 values found in {c_path}")
        return False

    max_val = max(int(m, 16) for m in matches)
    min_val = min(int(m, 16) for m in matches)
    count = len(matches)

    # RGB565 max is 0xFFFF
    if max_val > 0xFFFF or min_val < 0:
        print(f"ERROR: Values out of range [0x0000, 0xFFFF]")
        return False

    # Check if count is a perfect square (square image)
    import math
    side = int(math.sqrt(count))
    if side * side == count:
        print(f"OK: {c_path} — {side}×{side}, {count} pixels, "
              f"range [0x{min_val:04X}, 0x{max_val:04X}]")
        return True
    else:
        print(f"OK: {c_path} — {count} pixels (non-square), "
              f"range [0x{min_val:04X}, 0x{max_val:04X}]")
        return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    for arg in sys.argv[1:]:
        if arg == "--check":
            continue
        if sys.argv[1] == "--check":
            for f in sys.argv[2:]:
                check_c_array(f)
            return
        if arg.endswith(".png"):
            try:
                png_to_c_array(arg)
            except Exception as e:
                print(f"ERROR: {arg}: {e}")
        else:
            print(f"SKIP: {arg} (not a .png file)")


if __name__ == "__main__":
    main()
