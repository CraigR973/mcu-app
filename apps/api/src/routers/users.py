from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from ..auth import get_current_user, get_supabase

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class ProfileOut(BaseModel):
    id: str
    role: str
    username: str | None
    created_at: str
    onboarding_completed: bool


class OnboardingPatch(BaseModel):
    completed: bool = True


def _fetch_profile(supabase: Client, user_id: str) -> ProfileOut:
    result = (
        supabase.table("profiles")
        .select("id, role, username, created_at, onboarding_completed")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not result.data or not isinstance(result.data, dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileOut(**result.data)  # type: ignore[arg-type]


@router.get("/me", response_model=ProfileOut)
async def get_me(
    user: dict[str, str] = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> ProfileOut:
    return _fetch_profile(supabase, user["id"])


@router.patch("/me/onboarding", response_model=ProfileOut)
async def patch_onboarding(
    body: OnboardingPatch,
    user: dict[str, str] = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> ProfileOut:
    supabase.table("profiles").update({"onboarding_completed": body.completed}).eq("id", user["id"]).execute()
    return _fetch_profile(supabase, user["id"])
