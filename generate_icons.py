#!/usr/bin/env python3
"""
Generate PNG icons for PWA.
Uses Pillow to draw a simple printer icon.
"""

import os
from PIL import Image, ImageDraw

ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(SCRIPT_DIR, 'static', 'icons')

# Colors
BLUE = (13, 110, 253, 255)  # Bootstrap primary
WHITE = (255, 255, 255, 255)
LIGHT_GRAY = (233, 236, 239, 255)
DARK_GRAY = (52, 58, 64, 255)
GREEN = (40, 167, 69, 255)


def draw_icon(size: int) -> Image.Image:
    """Draw a printer icon at the specified size."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Scale factor
    s = size / 512
    
    # Background with rounded corners
    corner_radius = int(64 * s)
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=corner_radius,
        fill=BLUE
    )
    
    # Printer body
    body_left = int(96 * s)
    body_top = int(192 * s)
    body_right = int(416 * s)
    body_bottom = int(352 * s)
    body_radius = int(16 * s)
    draw.rounded_rectangle(
        [(body_left, body_top), (body_right, body_bottom)],
        radius=body_radius,
        fill=WHITE
    )
    
    # Paper input (top section)
    paper_in_left = int(128 * s)
    paper_in_top = int(96 * s)
    paper_in_right = int(384 * s)
    paper_in_bottom = int(208 * s)
    draw.rounded_rectangle(
        [(paper_in_left, paper_in_top), (paper_in_right, paper_in_bottom)],
        radius=int(8 * s),
        fill=LIGHT_GRAY
    )
    
    # Inner paper
    inner_left = int(144 * s)
    inner_top = int(112 * s)
    inner_right = int(368 * s)
    inner_bottom = int(192 * s)
    draw.rounded_rectangle(
        [(inner_left, inner_top), (inner_right, inner_bottom)],
        radius=int(4 * s),
        fill=WHITE
    )
    
    # Receipt output
    receipt_left = int(160 * s)
    receipt_top = int(336 * s)
    receipt_right = int(352 * s)
    receipt_bottom = int(464 * s)
    draw.rounded_rectangle(
        [(receipt_left, receipt_top), (receipt_right, receipt_bottom)],
        radius=int(4 * s),
        fill=WHITE
    )
    
    # Receipt lines
    line_left = int(176 * s)
    line_widths = [96, 160, 140, 120, 80]
    line_tops = [360, 380, 396, 412, 428]
    line_heights = [8, 6, 6, 6, 6]
    line_colors = [BLUE, LIGHT_GRAY, LIGHT_GRAY, LIGHT_GRAY, LIGHT_GRAY]
    
    for width, top, height, color in zip(line_widths, line_tops, line_heights, line_colors):
        draw.rounded_rectangle(
            [(int(line_left), int(top * s)), 
             (int(line_left + width * s), int((top + height) * s))],
            radius=int(2 * s),
            fill=color
        )
    
    # Status light
    light_cx = int(384 * s)
    light_cy = int(240 * s)
    light_r = int(12 * s)
    draw.ellipse(
        [(light_cx - light_r, light_cy - light_r),
         (light_cx + light_r, light_cy + light_r)],
        fill=GREEN
    )
    
    # Paper slot (dark ellipse)
    slot_cx = int(256 * s)
    slot_cy = int(280 * s)
    slot_rx = int(48 * s)
    slot_ry = int(16 * s)
    draw.ellipse(
        [(slot_cx - slot_rx, slot_cy - slot_ry),
         (slot_cx + slot_rx, slot_cy + slot_ry)],
        fill=DARK_GRAY
    )
    
    return img


def generate_icons():
    """Generate PNG icons at various sizes."""
    os.makedirs(ICONS_DIR, exist_ok=True)
    
    for size in ICON_SIZES:
        output_path = os.path.join(ICONS_DIR, f'icon-{size}.png')
        img = draw_icon(size)
        img.save(output_path, 'PNG', optimize=True)
        print(f"Generated: icon-{size}.png")
    
    print(f"\nAll icons generated in {ICONS_DIR}")


if __name__ == '__main__':
    generate_icons()
