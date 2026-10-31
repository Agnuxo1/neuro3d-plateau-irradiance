"""Create a 1280 x 720 video poster using a real computed district visual.

No generated or synthetic scientific pixels: the base image is the existing
rasterisation of the numerical irradiance output.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return an available font; never rely on a font being installed."""
    names = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(source: Path, output: Path) -> None:
    """Compose typography over an actual measured irradiance map."""
    base = Image.open(source).convert("RGB")
    image = ImageOps.fit(base, (1280, 720), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = overlay.load()
    for y in range(720):
        opacity = min(238, int(60 + y * 0.26))
        for x in range(1280):
            pixels[x, y] = (5, 12, 23, opacity if y > 320 else 80)
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((62, 42, 380, 94), radius=18, fill=(8, 29, 48, 236))
    draw.text((84, 55), "NEURO3D × PLATEAU", font=font(23, bold=True), fill="#60D5FF")
    draw.text((70, 430), "CITY-SCALE SOLAR", font=font(58, bold=True), fill="white")
    draw.text((70, 505), "IRRADIANCE", font=font(72, bold=True), fill="white")
    draw.text((74, 615), "44,902 computed faces  ·  Verified CPU workflow", font=font(27), fill="#E7F5FF")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, optimize=True, quality=95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
    print("Created", args.output)
