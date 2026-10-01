"""
Main application entrypoint for SAKSHI Case Management Service (MOD-01).
Phase 1: Case Initiation.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import SakshiException
from app.core.logging import logger
from app.db.base import Base
from app.db.session import engine
from app.api.v1.cases import router as cases_router
from app.api.v1.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist
    logger.info("Initializing SAKSHI Case Management database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
    yield
    # Shutdown
    logger.info("Shutting down SAKSHI Case Management Service.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.2.0",
    description="SAKSHI Investigation Platform — Phase 1: Case Initiation (MOD-01 + MOD-02 Identity/OIDC)",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SakshiException)
async def sakshi_exception_handler(request: Request, exc: SakshiException):
    """Formats domain exceptions into secure, standardized JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "SAKSHI Investigation Platform",
        "phase": "01 - Case Initiation",
        "modules": ["MOD-01 Case Management", "MOD-02 Identity/OIDC"],
        "auth_mode": settings.AUTH_MODE,
        "version": "0.2.0"
    }


# Include API v1 routers
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)

# Serve frontend UI at root if frontend directory exists
import os
from fastapi.staticfiles import StaticFiles

_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")
