from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()
index_file = Path(__file__).resolve().parents[2] / "index.html"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="HTML-first AI stock selection dashboard for A-share research.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(index_file)


@app.get("/dashboard", include_in_schema=False)
def dashboard_alias() -> FileResponse:
    return FileResponse(index_file)


app.include_router(api_router, prefix=settings.api_v1_prefix)
