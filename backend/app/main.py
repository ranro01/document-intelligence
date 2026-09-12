from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.database import Base, engine
from app.models.document import Document
from app.api.routes.documents import router as documents_router


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

FRONTEND_DIR = BASE_DIR / "frontend"


# ============================================================
# Database
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Financial Document Intelligence API",
    version="1.0.0",
)


# ============================================================
# Frontend static files
# ============================================================

app.mount(
    "/static",
    StaticFiles(
        directory=FRONTEND_DIR / "static"
    ),
    name="static",
)


# ============================================================
# Frontend templates
# ============================================================

templates = Jinja2Templates(
    directory=FRONTEND_DIR / "templates"
)


# ============================================================
# API routes
# ============================================================

app.include_router(
    documents_router
)


# ============================================================
# Frontend home page
# ============================================================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
      request=request,
      name="index.html",
      context={
        "request": request
      },
    )


# ============================================================
# Health check
# ============================================================

@app.get("/api/v1/health")
def health_check():

    return {
        "status": "healthy",
        "service": "financial-document-intelligence",
    }