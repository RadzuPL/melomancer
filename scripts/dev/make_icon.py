"""Builds app/static/icon.png (the panel's favicon and the tray icon) from the white gear in scripts/dev/assets.

The gear is white with a transparent note, made to sit on a colour: on a light taskbar or a light browser tab it would
vanish. So it is placed on the blue rounded square of the panel. Run it again only when the gear changes:

    python3 scripts/dev/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("assets") / "melomancer-gear.png"
TARGET = ROOT / "app" / "static" / "icon.png"
SIZE, BLUE = 256, (22, 104, 220, 255)   # the blue of the panel's accent


def main() -> None:
    gear = Image.open(SOURCE).convert("RGBA")
    gear = gear.crop(gear.split()[3].getbbox())
    side = max(gear.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(gear, ((side - gear.width) // 2, (side - gear.height) // 2))
    big = SIZE * 4   # drawn four times larger and scaled down: smooth edges
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((big // 32, big // 32, big - big // 32, big - big // 32), radius=big * 14 // 64, fill=BLUE)
    inner = int(big * 0.74)
    square = square.resize((inner, inner), Image.LANCZOS)
    tile.alpha_composite(square, ((big - inner) // 2, (big - inner) // 2))
    tile.resize((SIZE, SIZE), Image.LANCZOS).save(TARGET, optimize=True)
    print(f"{TARGET.relative_to(ROOT)}: {TARGET.stat().st_size} bytes")


if __name__ == "__main__":
    main()
