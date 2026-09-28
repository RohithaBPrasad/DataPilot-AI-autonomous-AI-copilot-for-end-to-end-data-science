"""
main.py
FastAPI application entrypoint for the Autonomous Data Scientist Agent.

Run (from the `backend/` directory, with the project venv active):
    uvicorn app.main:app --reload --port 8000

All data-science logic is reused, unmodified, from `agent_core/` at the
project root (see app/agent/runner.py for the import wiring).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.base import init_db
from .utils.config import get_settings
from .api import upload, chat, conversations, reports, images

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create DB tables (SQLite or Postgres, per DATABASE_URL) and
    # make sure upload/report directories exist.
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.reports_dir, exist_ok=True)
    init_db()
    yield
    # Shutdown: nothing to clean up currently.


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(images.router, prefix="/api", tags=["images"])


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
