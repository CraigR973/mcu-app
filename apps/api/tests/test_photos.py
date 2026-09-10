"""§3.10 — photo upload, gallery and deletion.

The resize pipeline is pure and runs on this machine; the endpoints need Postgres and run
in CI. Both halves are here because the sizing is the entire reason this batch is shaped
the way it is: §3.10's raw numbers are 5 MB × 5 × 1,857 ≈ 46 GB in a database that is 35 MB.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user, require_admin
from src.config import settings
from src.database import get_db
from src.main import app
from src.models.collection_item import CollectionItem
from src.models.item_photo import MAX_PHOTOS_PER_ITEM, ItemPhoto
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.services.photos import MAX_DIMENSION, PhotoRejected, process


def _jpeg(width: int, height: int, *, quality: int = 95) -> bytes:
    """A real photo-shaped JPEG — noisy, so it does not compress to nothing."""
    image = Image.new("RGB", (width, height))
    for x in range(0, width, 4):
        for y in range(0, height, 4):
            image.putpixel((x, y), ((x * 7) % 256, (y * 13) % 256, ((x + y) * 5) % 256))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


class TestProcessing:
    """No database — this is the half that can be checked on the build machine."""

    def test_a_phone_sized_photo_comes_out_under_the_target(self) -> None:
        """**The whole point of the batch.** 4032×3024 is what a phone actually sends."""
        raw = _jpeg(4032, 3024)

        result = process(raw)

        assert len(raw) > 1_000_000, "the fixture really is a big photo"
        assert result.byte_size <= settings.photo_target_kb * 1024
        assert max(result.width, result.height) <= MAX_DIMENSION

    def test_a_small_photo_is_not_enlarged(self) -> None:
        result = process(_jpeg(320, 240))

        assert (result.width, result.height) == (320, 240)

    def test_the_aspect_ratio_survives(self) -> None:
        result = process(_jpeg(4000, 1000))

        assert result.width / result.height == pytest.approx(4.0, abs=0.05)

    def test_a_transparent_png_composites_onto_white(self) -> None:
        """Onto black is what you get by default, and it looks like a corrupted photo."""
        image = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        result = process(buffer.getvalue())

        assert result.content_type == "image/jpeg"
        decoded = Image.open(io.BytesIO(result.data))
        assert decoded.getpixel((50, 50))[0] > 200, "white, not black"

    def test_everything_is_re_encoded_as_jpeg(self) -> None:
        """What lands in the database is bytes this process produced, not the upload."""
        assert process(_jpeg(200, 200)).content_type == "image/jpeg"

    def test_the_checksum_is_of_the_stored_bytes(self) -> None:
        import hashlib

        result = process(_jpeg(200, 200))

        assert result.checksum == hashlib.sha256(result.data).hexdigest()

    def test_the_same_photo_twice_produces_the_same_checksum(self) -> None:
        """What makes a double-tapped upload recognisable rather than a second row."""
        raw = _jpeg(400, 300)

        assert process(raw).checksum == process(raw).checksum

    def test_a_non_image_is_refused_with_something_readable(self) -> None:
        with pytest.raises(PhotoRejected, match="could not be read"):
            process(b"PK\x03\x04 this is a zip file")

    def test_an_empty_file_is_refused(self) -> None:
        with pytest.raises(PhotoRejected, match="empty"):
            process(b"")

    def test_a_decompression_bomb_is_refused_rather_than_allocated(self) -> None:
        """A 50,000-square PNG is a tiny upload that unpacks to gigabytes."""
        image = Image.new("RGB", (1, 1))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        bomb = bytearray(buffer.getvalue())
        # Rewrite the IHDR dimensions in place: a real bomb, without generating one.
        bomb[16:24] = (50000).to_bytes(4, "big") + (50000).to_bytes(4, "big")

        with pytest.raises(PhotoRejected):
            process(bytes(bomb))

    def test_a_lower_target_produces_a_smaller_photo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**The target is configuration, so it can be turned down without a migration.**

        `OWNER-ACTIONS.md` reserved this number because it "sets a shape that is annoying to
        reverse"; this is the test that it is not.
        """
        raw = _jpeg(3000, 2000)
        at_default = process(raw).byte_size

        monkeypatch.setattr(settings, "photo_target_kb", 60)
        at_sixty = process(raw).byte_size

        assert at_sixty < at_default
        assert at_sixty <= 60 * 1024


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(
        bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def admin(db: AsyncSession) -> Profile:
    profile = Profile(id=uuid.uuid4(), display_name=f"A{uuid.uuid4().hex[:8]}", role=UserRole.admin)
    db.add(profile)
    await db.flush()
    return profile


@pytest_asyncio.fixture
async def item(db: AsyncSession) -> CollectionItem:
    movie = Movie(
        id=uuid.uuid4(), tmdb_id=None, title="Heat", original_title="Heat", media_type="film"
    )
    db.add(movie)
    await db.flush()
    row = CollectionItem(id=uuid.uuid4(), movie_id=movie.id)
    db.add(row)
    await db.flush()
    return row


@pytest_asyncio.fixture
async def client(db: AsyncSession, admin: Profile) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_user() -> Profile:
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[require_admin] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


async def _upload(client: AsyncClient, item: CollectionItem, raw: bytes | None = None):
    return await client.post(
        f"/api/v1/collection/{item.id}/photos",
        files={"file": ("shelf.jpg", raw or _jpeg(1200, 900), "image/jpeg")},
    )


class TestGallery:
    """§3.10's acceptance — *"upload succeeds; photos appear in gallery; deletion works"*."""

    async def test_an_upload_succeeds(self, client: AsyncClient, item: CollectionItem) -> None:
        response = await _upload(client, item)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["url"] == f"/api/v1/photos/{body['id']}"
        assert body["byteSize"] > 0
        assert "data" not in body, "bytes never travel in the JSON"

    async def test_the_photo_appears_in_the_gallery(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        created = (await _upload(client, item)).json()

        gallery = (await client.get(f"/api/v1/collection/{item.id}/photos")).json()

        assert gallery["total"] == 1
        assert gallery["items"][0]["id"] == created["id"]
        assert gallery["remaining"] == MAX_PHOTOS_PER_ITEM - 1

    async def test_deletion_works(
        self, client: AsyncClient, db: AsyncSession, item: CollectionItem
    ) -> None:
        created = (await _upload(client, item)).json()

        removed = await client.delete(f"/api/v1/photos/{created['id']}")

        assert removed.status_code == 204
        rows = (await db.execute(select(ItemPhoto))).scalars().all()
        assert list(rows) == [], "a hard delete — the bytes are the cost this batch avoids"

    async def test_the_bytes_are_served_with_a_strong_etag(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        created = (await _upload(client, item)).json()

        served = await client.get(created["url"])

        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"
        assert served.headers["etag"].startswith('"')
        assert "immutable" in served.headers["cache-control"]
        assert "private" in served.headers["cache-control"]

    async def test_a_revisit_answers_304(self, client: AsyncClient, item: CollectionItem) -> None:
        """What makes a gallery re-render free, and lets the service worker cache it."""
        created = (await _upload(client, item)).json()
        first = await client.get(created["url"])

        again = await client.get(created["url"], headers={"If-None-Match": first.headers["etag"]})

        assert again.status_code == 304
        assert again.content == b""

    async def test_a_sixth_photo_is_refused(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        """§3.10's "max 5 per item"."""
        for index in range(MAX_PHOTOS_PER_ITEM):
            assert (await _upload(client, item, _jpeg(600 + index, 400))).status_code == 201

        sixth = await _upload(client, item, _jpeg(700, 500))

        assert sixth.status_code == 409
        assert "5 photos" in sixth.json()["detail"]

    async def test_the_same_photo_twice_is_one_photo(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        """A double-tapped upload, which on a phone is the normal way to send one twice."""
        raw = _jpeg(800, 600)
        first = (await _upload(client, item, raw)).json()
        second = (await _upload(client, item, raw)).json()

        assert first["id"] == second["id"]
        gallery = (await client.get(f"/api/v1/collection/{item.id}/photos")).json()
        assert gallery["total"] == 1

    async def test_a_non_image_is_refused_with_422(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        response = await client.post(
            f"/api/v1/collection/{item.id}/photos",
            files={"file": ("notes.txt", b"just some text", "text/plain")},
        )

        assert response.status_code == 422
        assert "image" in response.json()["detail"]

    async def test_a_photo_for_a_missing_item_is_404(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/collection/{uuid.uuid4()}/photos",
            files={"file": ("shelf.jpg", _jpeg(200, 200), "image/jpeg")},
        )

        assert response.status_code == 404

    async def test_what_is_stored_is_far_smaller_than_what_was_sent(
        self, client: AsyncClient, item: CollectionItem
    ) -> None:
        """The sizing claim, measured rather than asserted in a comment."""
        raw = _jpeg(4032, 3024)

        created = (await _upload(client, item, raw)).json()

        assert len(raw) > 1_000_000
        assert created["byteSize"] <= settings.photo_target_kb * 1024
