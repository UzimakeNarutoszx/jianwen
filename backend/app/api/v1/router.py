from fastapi import APIRouter

from app.api.v1 import auth, content, profile, weekly


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

api_router.include_router(weekly.router, prefix="/profile", tags=["weekly-report"])
