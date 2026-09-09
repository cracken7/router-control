# -*- coding: utf-8 -*-
"""Generate a multi-size icon.ico for RouterControl (signal/antenna glyph)."""
from PIL import Image, ImageDraw


def make(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64.0
    # rounded dark-navy square
    d.rounded_rectangle([2*s, 2*s, 62*s, 62*s], radius=14*s, fill=(13, 20, 38, 255),
                        outline=(76, 201, 240, 255), width=max(2, int(3*s)))
    cx, cy = 32*s, 40*s
    # antenna dot
    r = 5*s
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(46, 230, 168, 255))
    # waves (arcs) — draw as decreasing-width circles outlines
    for i, rr in enumerate([14*s, 22*s, 30*s]):
        w = max(2, int((4 - i) * s))
        bbox = [cx-rr, cy-rr, cx+rr, cy+rr]
        d.arc(bbox, start=215, end=325, fill=(76, 201, 240, 255), width=w)
    # mast
    d.line([cx, cy+r, cx, 52*s], fill=(157, 78, 221, 255), width=max(2, int(3.5*s)))
    d.line([cx-8*s, 52*s, cx+8*s, 52*s], fill=(157, 78, 221, 255), width=max(2, int(3.5*s)))
    return img


sizes = [16, 24, 32, 48, 64, 128, 256]
base = make(256)
base.save("icon.ico", sizes=[(s, s) for s in sizes])
base.save("icon_preview.png")
print("icon.ico written:", sizes)
