"""Turning an uploaded image into something a database should hold — §3.10.

**The size ceiling is the whole reason this module exists.** §3.10 says 5 MB per photo and
5 per item; across 1,857 discs that is about 46 GB, in a database that is 35 MB today.
Resized to the target below the worst case is roughly 2.8 GB and the realistic case under
200 MB — the difference between a feature and a hosting bill.

**The target is a setting, not a constant.** `OWNER-ACTIONS.md` reserves this number as an
owner choice because it "sets a shape that is annoying to reverse once photos exist". Making
it configuration is what stops that being true: changing it is an environment variable and
a re-upload, not a migration. The database's own CHECK sits well above it for the same
reason — a tuned-up target must not need schema changes.

**Every upload is re-encoded, never passed through.** That is not only about size. A file
arriving from a phone can carry an EXIF payload, a colour profile, an embedded thumbnail,
and in the worst case something that is not an image at all with a JPEG extension. Decoding
and re-encoding it means what lands in the database is bytes this process produced.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import structlog
from PIL import Image, UnidentifiedImageError

from src.config import settings

logger = structlog.get_logger(__name__)

#: Longest edge after resize. A phone photo of a shelf does not need more, and this is what
#: keeps a five-photo item in the low hundreds of kilobytes.
MAX_DIMENSION = 1600

#: What the API accepts *before* resizing. Generous, because it is the phone's original;
#: the thing that matters is what is stored.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

#: Pillow refuses an image whose pixel count exceeds this rather than allocating for it —
#: the decompression-bomb guard. A 1600px photo is nowhere near it; a 50,000 × 50,000 PNG
#: that unpacks to gigabytes is, and that is a small file to upload.
MAX_PIXELS = 40_000_000

ALLOWED_INPUT_TYPES = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"}
)


class PhotoRejected(Exception):
    """The upload cannot become a stored photo. The message is shown to a person."""


@dataclass(frozen=True)
class ProcessedPhoto:
    data: bytes
    content_type: str
    width: int
    height: int
    checksum: str

    @property
    def byte_size(self) -> int:
        return len(self.data)


def _target_bytes() -> int:
    return max(settings.photo_target_kb, 32) * 1024


def process(raw: bytes) -> ProcessedPhoto:
    """Decode, orient, resize and re-encode one upload.

    Raises :class:`PhotoRejected` with a sentence a person can read. Never raises anything
    else: an upload is something somebody did, and a 500 tells them nothing about what to
    do differently.
    """
    if not raw:
        raise PhotoRejected("That file was empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PhotoRejected(
            f"That photo is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
            "Most phones can send a smaller version."
        )

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(raw)) as image:
            # EXIF orientation, applied and then discarded. A phone photo that is "sideways"
            # is upright bytes plus a rotation tag, and dropping the tag without applying it
            # is how a gallery ends up full of sideways shelves.
            from PIL import ImageOps

            oriented = ImageOps.exif_transpose(image) or image
            # Flattened onto white: a PNG with transparency re-encoded to JPEG otherwise
            # composites onto black, which looks like a corrupted photo rather than a
            # design choice.
            if oriented.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", oriented.size, (255, 255, 255))
                converted = oriented.convert("RGBA")
                background.paste(converted, mask=converted.split()[-1])
                oriented = background
            elif oriented.mode != "RGB":
                oriented = oriented.convert("RGB")

            oriented.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            width, height = oriented.size
            data = _encode_within_budget(oriented)
    except PhotoRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        # Pillow raises `Image.DecompressionBombError` (a `ValueError`) for the bomb case,
        # and `OSError` for a truncated or non-image file. Both are the same answer here.
        logger.info("photo_rejected", error=str(exc)[:200])
        raise PhotoRejected("That file could not be read as an image.") from exc

    return ProcessedPhoto(
        data=data,
        content_type="image/jpeg",
        width=width,
        height=height,
        checksum=hashlib.sha256(data).hexdigest(),
    )


def _encode_within_budget(image: Image.Image) -> bytes:
    """Encode as JPEG, dropping quality until it fits the target.

    Quality first, then dimensions. A photo of a shelf survives quality 60 looking fine and
    survives being halved looking noticeably worse, so the cheaper concession is spent
    first. The last step always returns something rather than raising — a slightly-too-big
    photo is a better outcome than a refused upload, and the database's CHECK is far above
    the target for exactly this reason.
    """
    budget = _target_bytes()
    working = image

    for _ in range(4):
        for quality in (85, 75, 65, 55):
            buffer = io.BytesIO()
            working.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = buffer.getvalue()
            if len(data) <= budget:
                return data
        # Still too big at the lowest quality worth using: halve the longest edge and try
        # the quality ladder again.
        width, height = working.size
        if max(width, height) <= 400:
            return data
        working = working.resize(
            (max(width // 2, 1), max(height // 2, 1)), Image.Resampling.LANCZOS
        )

    return data
