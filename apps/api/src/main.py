from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user, require_admin
from .config import settings  # noqa: F401  — validates env on startup

app = FastAPI(
    title="MCU API",
    description="Mark's Cinematic Universe API",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)) -> dict:  # type: ignore[type-arg]
    return user


@app.get("/api/admin/ping")
async def admin_ping(user: dict = Depends(require_admin)) -> dict:  # type: ignore[type-arg]
    return {"status": "ok", "user": user}
