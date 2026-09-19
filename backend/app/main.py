from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import init_database
from app.services.daily_articles import scheduled_daily_article_refresh, start_daily_article_scheduler, stop_daily_article_scheduler


app = FastAPI(title=settings.PROJECT_NAME)

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_database()
    scheduled_daily_article_refresh()
    start_daily_article_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_daily_article_scheduler()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
