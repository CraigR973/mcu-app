from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

_url = settings.database_url
# Supabase / Heroku-style URLs use "postgres://" — SQLAlchemy 2.x requires "postgresql+psycopg2://"
if _url.startswith("postgres://"):
    _url = "postgresql+psycopg2://" + _url[len("postgres://"):]
elif _url.startswith("postgresql://") and "+psycopg2" not in _url:
    _url = "postgresql+psycopg2://" + _url[len("postgresql://"):]

_engine = create_engine(_url, pool_pre_ping=True) if _url else None
_SessionLocal: type[Session] | None = (
    sessionmaker(autocommit=False, autoflush=False, bind=_engine) if _engine else None  # type: ignore[assignment]
)


def get_db() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    session: Session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
