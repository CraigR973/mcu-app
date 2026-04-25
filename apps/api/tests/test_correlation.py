import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_correlation_id_generated() -> None:
    """Server generates a correlation ID when none is provided."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert "x-correlation-id" in response.headers
    correlation_id = response.headers["x-correlation-id"]
    assert len(correlation_id) == 36  # UUID4 format


@pytest.mark.asyncio
async def test_correlation_id_forwarded() -> None:
    """Server echoes back a caller-supplied correlation ID."""
    supplied_id = "test-correlation-id-abc123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Correlation-ID": supplied_id})
    assert response.headers["x-correlation-id"] == supplied_id


@pytest.mark.asyncio
async def test_debug_error_returns_500() -> None:
    """The /debug/error endpoint raises and returns a 500."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/debug/error")
    assert response.status_code == 500
