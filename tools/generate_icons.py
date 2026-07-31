# -*- coding: utf-8 -*-
"""Generate the application icons.

Icons are produced from this script rather than committed as opaque binaries,
so the mark can be regenerated at any size and its provenance is clear.

    python tools/generate_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "frontend" / "assets" / "icons"

TEAL = (27, 129, 125)
WHITE = (255, 255, 255)


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), TEAL + (255,))
    draw = ImageDraw.Draw(image)

    if not maskable:
        # Rounded square for platforms that do not apply their own mask.
        radius = int(size * 0.22)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=radius, fill=255
        )
        image.putalpha(mask)
        draw = ImageDraw.Draw(image)

    # A medical cross, inset far enough to survive a maskable safe-zone crop.
    inset = 0.30 if maskable else 0.24
    arm = size * (0.5 - inset)
    thickness = size * 0.13
    centre = size / 2

    draw.rounded_rectangle(
        [centre - thickness / 2, centre - arm, centre + thickness / 2, centre + arm],
        radius=thickness / 3,
        fill=WHITE,
    )
    draw.rounded_rectangle(
        [centre - arm, centre - thickness / 2, centre + arm, centre + thickness / 2],
        radius=thickness / 3,
        fill=WHITE,
    )
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192).save(OUT / "icon-192.png")
    draw_icon(512).save(OUT / "icon-512.png")
    draw_icon(512, maskable=True).save(OUT / "icon-maskable-512.png")
    draw_icon(180).save(OUT / "apple-touch-icon.png")
    draw_icon(32).save(OUT / "favicon-32.png")
    print(f"icons written to {OUT}")


if __name__ == "__main__":
    main()
