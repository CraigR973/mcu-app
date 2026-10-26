"""AA7: real image processing, private reads and caller-only replacement/removal."""

import io
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.profile import Profile, UserRole
from src.models.profile_photo import ProfilePhoto
from src.services.photos import MAX_UPLOAD_BYTES


def image_bytes(colour: str = "red") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (1800, 900), colour).save(out, "PNG")
    return out.getvalue()


@pytest_asyncio.fixture
async def db(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    try:
        async with AsyncSession(
            bind=db_conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
    finally:
        app.dependency_overrides.clear()


async def person(db: AsyncSession, role: UserRole) -> Profile:
    p = Profile(id=uuid.uuid4(), display_name=uuid.uuid4().hex, role=role)
    db.add(p)
    await db.flush()
    return p


def client(db: AsyncSession, p: Profile) -> AsyncClient:
    async def database() -> AsyncIterator[AsyncSession]:
        yield db

    async def current() -> Profile:
        return p

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("role", [UserRole.admin, UserRole.viewer])
async def test_each_person_uploads_replaces_and_removes_their_own_photo(
    db: AsyncSession, role: UserRole
) -> None:
    a = await person(db, role)
    b = await person(db, UserRole.viewer)
    async with client(db, a) as c:
        missing = await c.get(f"/api/v1/profile-photos/{a.id}")
        assert missing.status_code == 404
        assert missing.headers["cache-control"] == "private, no-store"
        assert (
            await c.put("/api/v1/profile-photos/me", files={"file": image_bytes()})
        ).status_code == 204
        first = await c.get(f"/api/v1/profile-photos/{a.id}")
        assert first.status_code == 200
        assert first.headers["cache-control"] == "private, no-store"
        assert first.headers["content-type"] == "image/jpeg"
        assert len(first.content) <= 300 * 1024
        with Image.open(io.BytesIO(first.content)) as image:
            assert image.size == (1600, 800)
            assert not image.getexif()
        assert (
            await c.put("/api/v1/profile-photos/me", files={"file": image_bytes("blue")})
        ).status_code == 204
        second = await c.get(f"/api/v1/profile-photos/{a.id}")
        assert second.content != first.content
        assert second.headers["etag"] != first.headers["etag"]
        assert (
            await db.scalar(
                select(func.count())
                .select_from(ProfilePhoto)
                .where(ProfilePhoto.profile_id == a.id)
            )
            == 1
        )
        # A guessed id offers no route for editing somebody else's photo.
        assert (
            await c.put(f"/api/v1/profile-photos/{b.id}", files={"file": image_bytes()})
        ).status_code == 405
        assert (await c.delete(f"/api/v1/profile-photos/{b.id}")).status_code == 405
    async with client(db, b) as c:
        assert (await c.get(f"/api/v1/profile-photos/{a.id}")).content == second.content
        assert (await c.delete("/api/v1/profile-photos/me")).status_code == 204
        assert (await c.get(f"/api/v1/profile-photos/{a.id}")).status_code == 200
    async with client(db, a) as c:
        assert (await c.delete("/api/v1/profile-photos/me")).status_code == 204
        assert (await c.get(f"/api/v1/profile-photos/{a.id}")).status_code == 404
        assert (await c.delete("/api/v1/profile-photos/me")).status_code == 204


async def test_bad_or_oversized_upload_keeps_the_previous_photo(db: AsyncSession) -> None:
    p = await person(db, UserRole.viewer)
    async with client(db, p) as c:
        await c.put("/api/v1/profile-photos/me", files={"file": image_bytes()})
        before = (await c.get(f"/api/v1/profile-photos/{p.id}")).content
        for raw, status in [
            (b"not an image", 422),
            (b"x" * (MAX_UPLOAD_BYTES + 1), 413),
            (b"", 422),
        ]:
            response = await c.put(
                "/api/v1/profile-photos/me", files={"file": ("photo.jpg", raw, "image/jpeg")}
            )
            assert response.status_code == status
            assert (await c.get(f"/api/v1/profile-photos/{p.id}")).content == before
        p.is_active = False
        await db.flush()
        assert (await c.get(f"/api/v1/profile-photos/{p.id}")).status_code == 404


async def test_anonymous_cannot_read_upload_or_delete() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get(f"/api/v1/profile-photos/{uuid.uuid4()}")).status_code == 401
        assert (
            await c.put("/api/v1/profile-photos/me", files={"file": image_bytes()})
        ).status_code == 401
        assert (await c.delete("/api/v1/profile-photos/me")).status_code == 401


async def test_photo_roles_never_gain_profile_credentials(db: AsyncSession) -> None:
    # Roles exist in production, but not necessarily in a test database.
    for role in ("mcu_readonly", "mcu_backup"):
        if await db.scalar(
            text("SELECT EXISTS (SELECT FROM pg_roles WHERE rolname=:role)"), {"role": role}
        ):
            assert await db.scalar(
                text("SELECT has_table_privilege(:role, 'profile_photos', 'SELECT')"),
                {"role": role},
            )
            assert not await db.scalar(
                text("SELECT has_column_privilege(:role, 'profiles', 'pin_hash', 'SELECT')"),
                {"role": role},
            )
