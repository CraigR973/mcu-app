from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from .config import settings

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _supabase


security = HTTPBearer()

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)

_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase),
) -> dict:  # type: ignore[type-arg]
    try:
        response = supabase.auth.get_user(credentials.credentials)
        if response.user is None:
            raise _UNAUTHORIZED
        return {"id": response.user.id, "email": response.user.email}
    except Exception:
        raise _UNAUTHORIZED


async def require_admin(
    user: dict = Depends(get_current_user),  # type: ignore[type-arg]
    supabase: Client = Depends(get_supabase),
) -> dict:  # type: ignore[type-arg]
    result = (
        supabase.table("profiles").select("role").eq("id", user["id"]).single().execute()
    )
    if not result.data or result.data.get("role") != "admin":
        raise _FORBIDDEN
    return user
