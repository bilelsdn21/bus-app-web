"""Generate the PWA app icons (bus logo) into frontend/public/.
Run:  python gen_icons.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public"
NAVY = (26, 58, 92, 255)
AMBER = (245, 158, 11, 255)
SKY = (186, 230, 253, 255)
WHITE = (255, 255, 255, 255)


def draw_bus(size: int) -> Image.Image:
    S = size * 4  # supersample for smooth edges
    u = S / 24.0  # scale from the 24-unit logo viewBox
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S, S], radius=int(5 * u), fill=NAVY)                       # background
    d.rounded_rectangle([4.3 * u, 5.8 * u, 19.7 * u, 15.8 * u], radius=int(2.2 * u), fill=AMBER)  # body
    d.rounded_rectangle([5.7 * u, 7.5 * u, 18.3 * u, 10.5 * u], radius=int(0.9 * u), fill=SKY)    # windows
    w = max(1, int(1 * u))
    d.line([9.6 * u, 7.5 * u, 9.6 * u, 10.5 * u], fill=AMBER, width=w)
    d.line([13.7 * u, 7.5 * u, 13.7 * u, 10.5 * u], fill=AMBER, width=w)
    for cx in (8.4, 15.6):
        r, cy = 1.9 * u, 16.2 * u
        d.ellipse([cx * u - r, cy - r, cx * u + r, cy + r], fill=WHITE)
        r2 = 0.75 * u
        d.ellipse([cx * u - r2, cy - r2, cx * u + r2, cy + r2], fill=NAVY)
    return img.resize((size, size), Image.LANCZOS)


for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")]:
    draw_bus(size).save(OUT / name)
    print("wrote", OUT / name)
