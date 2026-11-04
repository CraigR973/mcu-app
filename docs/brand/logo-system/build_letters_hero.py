"""Build AC2's Home banner (treatment T1): the five photo letters on transparency.

Same sources, grading and letterforms as `build_photo_hero.py`'s v3 five-image hero, without
its crimson field, frame or baked subtitle: Home draws the field in each theme's colours and
sets "Cinematic Universe" as live text (`DECISIONS.md` #337). Writes WebP at a phone's 3x
width (1125 px) and a desktop's 2x width (1800 px) into the API's private brand assets.

    apps/api/.venv/bin/python3.12 docs/brand/logo-system/build_letters_hero.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# v3 needs numpy only for its crimson field, which this treatment does not draw.
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_photo_hero as v3  # noqa: E402

ASSETS = v3.ROOT / "apps/api/src/assets/brand"
TITLE = ImageFont.truetype(v3.FUTURA, 500, index=4)
LETTERS = [
    ("M", 125, "m-jaws.jpg", "jaws", (0.50, 0.52)),
    ("A", 575, "a-humphrey-bogart.jpg", "mono", (0.50, 0.48)),
    ("R", 895, "r-double-indemnity-fred-barbara.jpg", "noir", (0.58, 0.50)),
    ("K", 1215, "k-alfred-hitchcock.jpg", "mono_lift", (0.50, 0.46)),
    ("S", 1594, "s-american-werewolf.jpg", "werewolf", (0.76, 0.49)),
]


def letters() -> Image.Image:
    canvas = Image.new("RGBA", (v3.WIDTH, v3.HEIGHT), (0, 0, 0, 0))
    for char, x, source_name, mode, centre in LETTERS:
        mask = v3.text_mask(char, x, TITLE, canvas.height)
        bbox = mask.getbbox()
        assert bbox is not None
        canvas.paste((*v3.GOLD, 255), mask=v3.dilate(mask, 12))
        canvas.paste((*v3.INK, 255), mask=v3.dilate(mask, 6))
        source = v3.grade(Image.open(v3.SOURCE / source_name), mode)
        crop = v3.cover_crop(source, (bbox[2] - bbox[0], bbox[3] - bbox[1]), centre)
        tile = Image.new("RGBA", canvas.size, (*v3.INK, 255))
        tile.paste(crop, (bbox[0], bbox[1]))
        canvas.paste(tile, mask=mask)
    ImageDraw.Draw(canvas).text(
        (1549, 96), "'", font=ImageFont.truetype(v3.FUTURA, 116, index=4), fill=(*v3.GOLD, 255)
    )
    box = canvas.getbbox()
    assert box is not None
    return canvas.crop((box[0] - 16, box[1] - 16, box[2] + 16, box[3] + 16))


if __name__ == "__main__":
    art = letters()
    for width in (1125, 1800):
        sized = art.resize((width, round(art.height * width / art.width)), Image.Resampling.LANCZOS)
        path = ASSETS / f"hero-letters-v1-{width}.webp"
        sized.save(path, "WEBP", quality=82, method=6)
        print(f"{path.name}: {sized.width}x{sized.height}, {path.stat().st_size // 1024} KB")
