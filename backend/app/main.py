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
from app.db.session import engine, SessionLocal
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.organization import Organization, Jurisdiction, PoliceStation
from app.models.officer import Officer
from app.models.case_assignment import CaseAssignment
from app.api.v1.cases import router as cases_router
from app.api.v1.auth import router as auth_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.rag import router as rag_router
from app.api.v1.iam import router as iam_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist for local development SQLite workflows.
    # In production or PostgreSQL environments, create_all() is NOT used as a migration
    # substitute, nor are migrations run automatically on startup; schema changes must be
    # applied through versioned Alembic migrations (`alembic upgrade head`).
    if settings.is_sqlite and settings.ENVIRONMENT != "production":
        logger.info("Initializing SAKSHI Investigation Platform development SQLite tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Development database tables verified.")
        if settings.ENABLE_STARTUP_SEED:
            try:
                with SessionLocal() as db:
                    existing_case = db.query(Case).filter(Case.case_id == "SAKSHI-TEST-2026-002").first()
                    if not existing_case:
                        test_case = Case(
                            case_id="SAKSHI-TEST-2026-002",
                            title="Unnatural Death Investigation - Case 002",
                            fir_metadata={
                                "fir_number": "FIR-TEST-2026-002",
                                "police_station": "Fort Police Station",
                                "incident_date": "2026-10-01T10:00:00Z",
                                "report_date": "2026-10-01T11:30:00Z",
                                "jurisdiction_code": "KERALA",
                            },
                            assigned_io_id="dev-investigator-001",
                            lifecycle_stage="EVIDENCE_INGESTION",
                            status="ACTIVE",
                            case_workspace_path="/cases/SAKSHI-TEST-2026-002",
                            created_by="dev-investigator-001",
                        )
                        db.add(test_case)
                        db.commit()

                    existing_ev = db.query(Evidence).filter(Evidence.evidence_id == "SAKSHI-EVID-2026-E51D496A").first()
                    if not existing_ev:
                        test_ev = Evidence(
                            evidence_id="SAKSHI-EVID-2026-E51D496A",
                            case_id="SAKSHI-TEST-2026-002",
                            original_file_name="SAKSHI_Synthetic_Evidence_RAG_Test.pdf",
                            stored_file_name="SAKSHI-EVID-2026-E51D496A.pdf",
                            evidence_category="DOCUMENT_PDF",
                            declared_mime_type="application/pdf",
                            detected_mime_type="application/pdf",
                            file_size_bytes=42000,
                            submitting_investigator_id="dev-investigator-001",
                            status="COMMITTED",
                            worm_status="COMMITTED",
                            integrity_status="VERIFIED",
                            raw_storage_path="/storage/SAKSHI-EVID-2026-E51D496A.pdf",
                        )
                        db.add(test_ev)
                        db.commit()
                    logger.info("Development synthetic test fixtures seeded (ENABLE_STARTUP_SEED=True).")
            except Exception as e:
                logger.warning("Could not auto-seed development fixtures: %s", e)
        else:
            logger.info("Startup fixture seeding disabled (ENABLE_STARTUP_SEED=False); Case Directory remains clean.")
    else:
        logger.info(
            "Production/PostgreSQL environment detected (%s). "
            "Bypassing automatic create_all(); database schema is governed by versioned Alembic migrations.",
            settings.ENVIRONMENT,
        )
    yield
    # Shutdown
    logger.info("Shutting down SAKSHI Case Management Service.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.6.0",
    description="SAKSHI Investigation Platform — Phase 4: secure case-scoped evidence retrieval",
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
        "phase": "04 - Secure RAG Retrieval",
        "modules": [
            "MOD-01 Case Management",
            "MOD-02 Identity/OIDC",
            "MOD-03 RBAC/ABAC Authorization",
            "MOD-04 Stage Engine",
            "MOD-05 Evidence Intake",
            "MOD-06 MIME/Signature Validation",
            "MOD-07 Antivirus Scan",
            "MOD-08 WORM Commit + Checksum",
            "MOD-09 Dual Hashing (SHA-256 + SHA3-512)",
            "MOD-10 WORM Object Lock / Dual Storage",
            "MOD-11 AES-256-GCM Encryption",
        ],
        "auth_mode": settings.AUTH_MODE,
        "version": "0.6.0"
    }


# Include API v1 routers
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(evidence_router, prefix=settings.API_V1_STR)
app.include_router(rag_router, prefix=settings.API_V1_STR)
app.include_router(iam_router, prefix=settings.API_V1_STR)

# Serve frontend UI at root if frontend directory exists
import os
from fastapi.staticfiles import StaticFiles

_frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(_frontend_path):
    app.mount("/", StaticFiles(directory=_frontend_path, html=True), name="frontend")
