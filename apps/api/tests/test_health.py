from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_health_returns_running_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.routers.health as health_router

    monkeypatch.setattr(health_router.settings, "railway_git_commit_sha", "abc1234")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commitSha": "abc1234"}


@pytest.mark.asyncio
async def test_health_reports_unknown_commit_when_not_in_railway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.routers.health as health_router

    monkeypatch.setattr(health_router.settings, "railway_git_commit_sha", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commitSha": "unknown"}


@pytest.mark.asyncio
async def test_readiness_returns_ok_when_database_responds() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routers.health.AsyncSessionLocal", return_value=session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "db": "ok"}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_unreachable() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(side_effect=ConnectionError("database unavailable"))
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("src.routers.health.AsyncSessionLocal", return_value=session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "db": "unreachable"}


def test_health_is_the_only_application_route() -> None:
    application_paths = set(app.openapi()["paths"])
    assert application_paths == {"/api/v1/health", "/api/v1/health/ready"}
