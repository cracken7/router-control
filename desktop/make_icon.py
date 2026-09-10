# -*- coding: utf-8 -*-
"""Premium icon for RouterControl v2 — aurora gradient orb + signal waves on
a glassy dark rounded square. Multi-size .ico + preview png."""
import math

from PIL import Image, ImageDraw, ImageFilter


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make(size):
    SS = size * 4  # supersample
    img = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = SS / 64.0

    # ── glassy rounded square with vertical gradient
    grad = Image.new("RGBA", (SS, SS))
    gd = ImageDraw.Draw(grad)
    top, bot = (16, 26, 46), (7, 11, 20)
    for y in range(SS):
        gd.line([(0, y), (SS, y)], fill=lerp(top, bot, y / SS) + (255,))
    mask = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([2*s, 2*s, SS-2*s, SS-2*s], radius=15*s, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # ── aurora glows inside the tile
    glow = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    gdr = ImageDraw.Draw(glow)
    gdr.ellipse([30*s, -6*s, 70*s, 34*s], fill=(76, 201, 240, 110))   # cyan top-left-ish
    gdr.ellipse([-8*s, 34*s, 32*s, 74*s], fill=(157, 78, 221, 120))   # purple bottom
    glow = glow.filter(ImageFilter.GaussianBlur(7*s))
    img.paste(Image.alpha_composite(img, glow), (0, 0), mask)
    d = ImageDraw.Draw(img)

    # ── border + top sheen
    d.rounded_rectangle([2*s, 2*s, SS-2*s, SS-2*s], radius=15*s,
                        outline=(120, 190, 235, 130), width=max(1, int(1.6*s)))
    d.rounded_rectangle([3.4*s, 3.4*s, SS-3.4*s, 26*s], radius=13*s,
                        fill=(255, 255, 255, 14))

    # ── router body (rounded bar at bottom) with LED dots
    d.rounded_rectangle([16*s, 44*s, 48*s, 52*s], radius=3.4*s,
                        fill=(232, 240, 250, 235))
    d.ellipse([19*s, 46.5*s, 22*s, 49.5*s], fill=(255, 93, 115, 255))
    d.ellipse([24*s, 46.5*s, 27*s, 49.5*s], fill=(255, 200, 87, 255))
    d.ellipse([29*s, 46.5*s, 32*s, 49.5*s], fill=(46, 230, 168, 255))

    # ── antenna mast + glowing signal arcs
    cx, cy = 32*s, 44*s
    d.line([cx, cy, cx, 30*s], fill=(210, 225, 245, 255), width=max(2, int(2.6*s)))
    orb = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    od.ellipse([cx-3.4*s, 30*s-3.4*s, cx+3.4*s, 30*s+3.4*s], fill=(150, 240, 255, 255))
    orb = orb.filter(ImageFilter.GaussianBlur(1.6*s))
    img = Image.alpha_composite(img, orb)
    d = ImageDraw.Draw(img)
    d.ellipse([cx-2.2*s, 30*s-2.2*s, cx+2.2*s, 30*s+2.2*s], fill=(235, 250, 255, 255))

    # arcs (cyan → purple) opening upward around the mast tip
    for i, (rr, col) in enumerate([
        (8.5, (120, 220, 250)),
        (14.5, (90, 200, 240)),
        (20.5, (150, 130, 240)),
        (26.5, (190, 110, 245)),
    ]):
        w = max(2, int((3.0 - i*0.5)*s))
        bbox = [cx-rr*s, 30*s-rr*s, cx+rr*s, 30*s+rr*s]
        d.arc(bbox, start=212, end=328, fill=col + (255 - i*28,), width=w)

    img = img.resize((size, size), Image.LANCZOS)
    return img


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = make(256)
    base.save("icon.ico", sizes=[(n, n) for n in sizes])
    make(512).save("icon_preview.png")
    print("new icon written:", sizes)
