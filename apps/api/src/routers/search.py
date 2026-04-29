from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchResultItem(BaseModel):
    id: int
    title: str
    original_title: str | None
    poster_path: str | None
    release_date: str | None
    vote_average: float | None
    best_format_owned: str | None


class SearchResponse(BaseModel):
    data: list[SearchResultItem]
    query: str
    total: int


_SQL = text("""
SELECT * FROM (
  SELECT DISTINCT ON (id)
    id, title, original_title, poster_path,
    CAST(release_date AS TEXT) AS release_date,
    vote_average, popularity, best_format_owned,
    rank
  FROM (
    SELECT
      m.id, m.title, m.original_title, m.poster_path,
      m.release_date, m.vote_average, m.popularity, m.best_format_owned,
      ts_rank(m.search_vector, websearch_to_tsquery('english', :q)) AS rank
    FROM movies m
    WHERE m.search_vector @@ websearch_to_tsquery('english', :q)

    UNION ALL

    SELECT
      m.id, m.title, m.original_title, m.poster_path,
      m.release_date, m.vote_average, m.popularity, m.best_format_owned,
      0.05::float8 AS rank
    FROM movies m
    JOIN movie_credits mc ON mc.movie_id = m.id
    WHERE mc.credit_type = 'crew'
      AND mc.department = 'Directing'
      AND lower(mc.person_name) LIKE :q_like
  ) combined
  ORDER BY id, rank DESC
) deduped
ORDER BY rank DESC, popularity DESC NULLS LAST
LIMIT :limit
""")


@router.get("", response_model=SearchResponse)
def search_movies(
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
) -> SearchResponse:
    rows = db.execute(_SQL, {"q": q, "q_like": f"%{q.lower()}%", "limit": limit}).mappings().all()
    items = [SearchResultItem(**dict(row)) for row in rows]
    return SearchResponse(data=items, query=q, total=len(items))
