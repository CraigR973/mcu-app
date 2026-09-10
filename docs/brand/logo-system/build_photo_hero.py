"""Build the source-faithful photographic hero assets.

The five-image edition is the primary promotional hero. The older thirteen-image
edition remains a collector's alternate and is intentionally not overwritten.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/brand/source-images/photo-logo-five-v1"
OUTPUT = ROOT / "docs/brand/logo-system"

WIDTH = 2000
HEIGHT = 950
TITLE_Y = 0

FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"
AVENIR_CONDENSED = "/System/Library/Fonts/Avenir Next Condensed.ttc"

GOLD = (212, 175, 127)
INK = (8, 8, 10)
OFF_WHITE = (250, 248, 244)


def build_background(height: int) -> Image.Image:
    """Return the restrained crimson field, vignette and film-like texture."""

    yy, xx = np.mgrid[0:height, 0:WIDTH]
    nx = (xx - WIDTH / 2) / (WIDTH / 2)
    ny = (yy - height * 0.42) / (height / 2)
    radius = np.sqrt(nx * nx + ny * ny)

    centre = np.array([181, 55, 82], dtype=np.float32)
    edge = np.array([73, 7, 27], dtype=np.float32)
    blend = np.clip((radius - 0.08) / 1.12, 0, 1)[..., None]
    pixels = centre * (1 - blend) + edge * blend

    rng = np.random.default_rng(1935)
    grain = rng.normal(0, 2.1, size=(height, WIDTH, 1))
    pixels = np.clip(pixels + grain, 0, 255).astype(np.uint8)
    return Image.fromarray(pixels, "RGB")


def grade(image: Image.Image, mode: str) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")

    if mode in {"mono", "noir", "mono_lift"}:
        neutral = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=(1, 1))
        image = ImageOps.colorize(
            neutral,
            black=(8, 8, 10),
            white=(230, 220, 212),
        )
        image = ImageEnhance.Contrast(image).enhance(1.03)
        brightness = {"mono": 0.98, "noir": 0.88, "mono_lift": 1.07}[mode]
        image = ImageEnhance.Brightness(image).enhance(brightness)
    elif mode == "jaws":
        image = ImageEnhance.Contrast(image).enhance(1.06)
        image = ImageEnhance.Color(image).enhance(0.70)
        image = ImageEnhance.Brightness(image).enhance(0.92)
    elif mode == "werewolf":
        image = ImageEnhance.Contrast(image).enhance(1.02)
        image = ImageEnhance.Color(image).enhance(0.54)
        image = ImageEnhance.Brightness(image).enhance(0.84)

    return image


def cover_crop(
    image: Image.Image,
    size: tuple[int, int],
    centre: tuple[float, float],
) -> Image.Image:
    """Scale to cover while retaining the specified visual focal point."""

    return ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=centre,
    )


def text_mask(
    char: str,
    x: int,
    font: ImageFont.FreeTypeFont,
    height: int,
) -> Image.Image:
    mask = Image.new("L", (WIDTH, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.text((x, TITLE_Y), char, font=font, fill=255)
    if char == "A":
        # A deliberate cinematic counter: clearer than the narrow font default,
        # but kept below Bogart's eyes. The normal outline construction below
        # gives it the same black-and-gold edge sequence as the R counter.
        ImageDraw.floodfill(mask, (725, 300), 255)
        draw.polygon(((725, 268), (689, 360), (761, 360)), fill=0)
    return mask


def dilate(mask: Image.Image, radius: int) -> Image.Image:
    return mask.filter(ImageFilter.MaxFilter(radius * 2 + 1))


def place_letter(
    canvas: Image.Image,
    char: str,
    x: int,
    source_name: str,
    grade_mode: str,
    centre: tuple[float, float],
    font: ImageFont.FreeTypeFont,
) -> None:
    mask = text_mask(char, x, font, canvas.height)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError(f"Could not create mask for {char}")

    outer = dilate(mask, 12)
    inner = dilate(mask, 6)
    canvas.paste(GOLD, mask=outer)
    canvas.paste(INK, mask=inner)

    source = grade(Image.open(SOURCE / source_name), grade_mode)
    crop = cover_crop(source, (bbox[2] - bbox[0], bbox[3] - bbox[1]), centre)
    tile = Image.new("RGB", canvas.size, INK)
    tile.paste(crop, (bbox[0], bbox[1]))
    canvas.paste(tile, mask=mask)


def draw_tracked_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    centre_x: int,
    y: int,
    tracking: int,
) -> None:
    lengths = [draw.textlength(char, font=font) for char in text]
    total = sum(lengths) + tracking * (len(text) - 1)
    cursor = centre_x - total / 2
    for char, length in zip(text, lengths, strict=True):
        draw.text((round(cursor), y), char, font=font, fill=OFF_WHITE)
        cursor += length + tracking


def build(height: int = HEIGHT, subtitle_y: int = 638) -> Image.Image:
    canvas = build_background(height)
    title_font = ImageFont.truetype(FUTURA, 500, index=4)

    # Individually positioned for optical balance. The compact apostrophe avoids
    # the oversized possessive mark produced by the title face at full size.
    letters = [
        ("M", 125, "m-jaws.jpg", "jaws", (0.50, 0.52)),
        ("A", 575, "a-humphrey-bogart.jpg", "mono", (0.50, 0.48)),
        ("R", 895, "r-double-indemnity-fred-barbara.jpg", "noir", (0.58, 0.50)),
        ("K", 1215, "k-alfred-hitchcock.jpg", "mono_lift", (0.50, 0.46)),
        ("S", 1594, "s-american-werewolf.jpg", "werewolf", (0.76, 0.49)),
    ]
    for args in letters:
        place_letter(canvas, *args, title_font)

    draw = ImageDraw.Draw(canvas)

    apostrophe_font = ImageFont.truetype(FUTURA, 116, index=4)
    draw.text(
        (1549, 96),
        "'",
        font=apostrophe_font,
        fill=GOLD,
    )

    subtitle_font = ImageFont.truetype(AVENIR_CONDENSED, 88, index=8)
    draw_tracked_text(
        draw,
        "CINEMATIC UNIVERSE",
        subtitle_font,
        WIDTH // 2,
        subtitle_y,
        39,
    )

    # One frame only: a calmer hierarchy than the earlier double-border concept.
    draw.rounded_rectangle(
        (50, 50, WIDTH - 50, height - 50),
        radius=2,
        outline=GOLD,
        width=3,
    )
    return canvas


if __name__ == "__main__":
    hero = build()
    hero.save(OUTPUT / "hero-photo-five-v3.png", optimize=True)
    hero.resize((1200, 570), Image.Resampling.LANCZOS).save(
        OUTPUT / "hero-photo-five-v3-web.png",
        optimize=True,
    )

    compact = build(height=860, subtitle_y=600)
    compact.save(OUTPUT / "hero-photo-five-v3-compact.png", optimize=True)
    compact.resize((1200, 516), Image.Resampling.LANCZOS).save(
        OUTPUT / "hero-photo-five-v3-compact-web.png",
        optimize=True,
    )
