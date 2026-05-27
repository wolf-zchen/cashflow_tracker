"""Generate a cashflow tracker app icon at all required sizes."""
from PIL import Image, ImageDraw, ImageFont
import math, os

def draw_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded rect background (dark green)
    r = size // 6
    bg = [(0, 0), (size, size)]
    d.rounded_rectangle(bg, radius=r, fill=(30, 110, 60))

    # Inner lighter rounded rect for depth
    pad = size * 0.06
    d.rounded_rectangle(
        [(pad, pad), (size - pad, size - pad)],
        radius=r - pad//2,
        fill=(35, 130, 70)
    )

    # Draw upward trending line (chart)
    margin = size * 0.18
    chart_left   = margin
    chart_right  = size - margin
    chart_bottom = size * 0.72
    chart_top    = size * 0.32

    # 5 points of an upward trend
    pts = [
        (chart_left,                     chart_bottom),
        (chart_left + (chart_right - chart_left) * 0.25, chart_bottom - (chart_bottom - chart_top) * 0.3),
        (chart_left + (chart_right - chart_left) * 0.5,  chart_bottom - (chart_bottom - chart_top) * 0.55),
        (chart_left + (chart_right - chart_left) * 0.75, chart_bottom - (chart_bottom - chart_top) * 0.7),
        (chart_right,                    chart_top),
    ]

    lw = max(2, size // 28)
    # Shadow line
    shadow_pts = [(x + lw*0.5, y + lw*0.5) for x, y in pts]
    d.line(shadow_pts, fill=(0, 80, 30, 120), width=lw)
    # Main line
    d.line(pts, fill=(255, 255, 255), width=lw)

    # Dot at the end of the line
    dot_r = lw * 1.8
    ex, ey = pts[-1]
    d.ellipse([(ex - dot_r, ey - dot_r), (ex + dot_r, ey + dot_r)], fill=(255, 255, 255))

    # Dollar sign below the chart
    font_size = max(12, int(size * 0.22))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "$"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (size - tw) / 2
    ty = size * 0.72
    d.text((tx, ty), text, fill=(200, 255, 210), font=font)

    # "ZC" watermark in the bottom-right corner
    zc_size = max(8, int(size * 0.16))
    try:
        zc_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", zc_size)
    except Exception:
        zc_font = font
    zc_text = "ZC"
    zc_bbox = d.textbbox((0, 0), zc_text, font=zc_font)
    zc_w = zc_bbox[2] - zc_bbox[0]
    zc_h = zc_bbox[3] - zc_bbox[1]
    margin = size * 0.06
    zc_x = size - zc_w - margin
    zc_y = size - zc_h - margin
    d.text((zc_x, zc_y), zc_text, fill=(255, 255, 255, 180), font=zc_font)

    return img

# Build iconset
iconset = "/Volumes/Extreme/cashflow_tracker_clean/CashflowTracker.iconset"
os.makedirs(iconset, exist_ok=True)

specs = [
    ("icon_16x16.png",       16),
    ("icon_16x16@2x.png",    32),
    ("icon_32x32.png",       32),
    ("icon_32x32@2x.png",    64),
    ("icon_128x128.png",     128),
    ("icon_128x128@2x.png",  256),
    ("icon_256x256.png",     256),
    ("icon_256x256@2x.png",  512),
    ("icon_512x512.png",     512),
    ("icon_512x512@2x.png",  1024),
]

for fname, sz in specs:
    draw_icon(sz).save(f"{iconset}/{fname}")
    print(f"  {fname}")

print("Done.")
