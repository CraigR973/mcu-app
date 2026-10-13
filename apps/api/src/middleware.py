import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import Environment, settings


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a request correlation ID to logs and echo it in the response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)
        if settings.environment != Environment.development:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        # This policy decorates API responses only. Browser-page capability policy
        # belongs in Vercel configuration and lands with its camera fix in Batch 2.
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


#: What a person's screen says for a fault in the API: a sentence, not a traceback.
SERVER_FAULT = "The archive had a problem. Try again in a minute."


class UnhandledErrorMiddleware:
    """Answer an unhandled exception with a 500 **inside** CORS (Batch X8, UX48-03).

    Starlette answers an unhandled exception from its outermost layer, outside
    `CORSMiddleware`, so the 500 carried no `Access-Control-Allow-Origin`; the browser blocked
    it, and the page read "Failed to fetch", the words for no signal. Registered before CORS,
    this sits inside it, so the 500 reaches the page as a 500 and the page can say the archive
    had a problem. The traceback is still logged. A response already started cannot be
    replaced, so that case re-raises as before.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            structlog.get_logger(__name__).exception(
                "unhandled_error", path=scope.get("path"), method=scope.get("method")
            )
            if started:
                raise
            await JSONResponse(status_code=500, content={"detail": SERVER_FAULT})(
                scope, receive, send
            )
