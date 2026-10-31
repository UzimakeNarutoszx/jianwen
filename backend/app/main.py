from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import init_database
from app.services.daily_articles import scheduled_daily_article_refresh, start_daily_article_scheduler, stop_daily_article_scheduler


app = FastAPI(title=settings.PROJECT_NAME, docs_url=None, redoc_url=None)

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
# Content records use the same image paths as the H5 bundle. Mount those
# directories explicitly before the backend-owned static directory.
frontend_static = Path(__file__).resolve().parents[2] / "frontend" / "static"
for directory_name in ("images", "icons", "app-icons"):
    directory = frontend_static / directory_name
    if directory.is_dir():
        app.mount(f"/static/{directory_name}", StaticFiles(directory=directory), name=f"static-{directory_name}")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Share only the public content catalogs and weekly media, never the website root.
webpage_root = Path(__file__).resolve().parents[2] / "webpage"
for public_path, directory in (
    ("/public/data", webpage_root / "data"),
    ("/public/assets/weekly-video", webpage_root / "assets" / "weekly-video"),
):
    if directory.is_dir():
        app.mount(public_path, StaticFiles(directory=directory), name=public_path.strip("/").replace("/", "-"))

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
    start_daily_article_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_daily_article_scheduler()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def service_root() -> dict[str, str]:
    return {"service": app.title, "health": "/health", "docs": "/docs"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "favicon.ico")


@app.get("/docs", include_in_schema=False)
def swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_favicon_url="/static/brand-icon.svg",
    )


@app.get("/redoc", include_in_schema=False)
def redoc_ui() -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_favicon_url="/static/brand-icon.svg",
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
