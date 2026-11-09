"""Two genuinely concurrent observations cannot both win the same displayed revision."""

import asyncio
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.auth import get_current_user
from src.database import get_db
from src.main import app
from src.models.admin_action import AdminAction
from src.models.assigned_review import AssignedReview
from src.models.collection_item import CollectionItem
from src.models.identify import IdentifyDoubt
from src.models.movie import Movie
from src.models.profile import Profile, UserRole
from src.services.assigned_reviews import context


async def test_concurrent_answers_lock_one_revision(db_engine):
    sessions = async_sessionmaker(db_engine, expire_on_commit=False)
    person_id, movie_id, copy_id, doubt_id, review_id = [uuid.uuid4() for _ in range(5)]
    async with sessions() as db:
        person = Profile(id=person_id, display_name=f"ad1-{person_id.hex}", role=UserRole.viewer)
        db.add(person)
        db.add(Movie(id=movie_id, title="Titanic", year=1953))
        await db.flush()
        db.add(CollectionItem(id=copy_id, movie_id=movie_id, formats=["blu_ray"], condition="good"))
        await db.flush()
        db.add(
            IdentifyDoubt(
                id=doubt_id,
                movie_id=movie_id,
                collection_item_id=copy_id,
                source="specs",
                status="open",
                note="Check this physical disc",
            )
        )
        await db.flush()
        snapshot, _ = await context(db, "titanic_disc", doubt_id)
        db.add(
            AssignedReview(
                id=review_id,
                kind="titanic_disc",
                target_id=doubt_id,
                assigned_to=person_id,
                snapshot=snapshot,
            )
        )
        await db.commit()

    async def own_db():
        async with sessions() as db:
            yield db

    async def own_person():
        return person

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = own_db
    app.dependency_overrides[get_current_user] = own_person
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            answers = await asyncio.gather(
                *[
                    client.post(
                        f"/api/v1/needs-you/reviews/{review_id}/answer",
                        json={"revision": 1, "answer": value},
                    )
                    for value in ("1953", "1997")
                ]
            )
        assert sorted(answer.status_code for answer in answers) == [200, 409]
        winner = next(answer.json() for answer in answers if answer.status_code == 200)
        async with sessions() as db:
            row = await db.get(AssignedReview, review_id)
            assert row.revision == 2 and row.answer == winner["answer"]
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(AdminAction)
                    .where(
                        AdminAction.target_table == "assigned_reviews",
                        AdminAction.target_id == str(review_id),
                    )
                )
                == 1
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        async with sessions() as db:
            # Collection copies are soft-deleted by a trigger unless this transaction
            # explicitly requests permanent deletion. Only this test's disposable rows.
            await db.execute(text("SET LOCAL app.permanent_delete = 'on'"))
            await db.execute(delete(AdminAction).where(AdminAction.target_id == str(review_id)))
            await db.execute(delete(AssignedReview).where(AssignedReview.id == review_id))
            await db.execute(delete(IdentifyDoubt).where(IdentifyDoubt.id == doubt_id))
            await db.execute(delete(CollectionItem).where(CollectionItem.id == copy_id))
            await db.execute(delete(Movie).where(Movie.id == movie_id))
            await db.execute(delete(Profile).where(Profile.id == person_id))
            await db.commit()
            assert await db.get(CollectionItem, copy_id) is None
            assert await db.get(Movie, movie_id) is None
            assert await db.get(AssignedReview, review_id) is None
