"""
Appendices for SAKSHI Academic Project Report.
Target length: 4–6 pages.
Covers:
Appendix A — API Endpoint Summary
Appendix B — Database Schema Specification
Appendix C — Empirical Test Suite Catalog
Appendix D — Core Domain Pydantic Data Models
Appendix E — Example API Payloads and JSON Responses
Appendix F — Acronyms and Technical Glossary
Appendix G — Additional System Interface Specifications
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27


def get_appendices(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("app"))
    story.append(Paragraph("APPENDICES", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX A: API ENDPOINT SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_a"))
    story.append(Paragraph("Appendix A — API Endpoint Summary", styles["SectionHeading"]))
    story.append(Paragraph(
        "This appendix provides a consolidated reference of all RESTful API endpoints exposed across the SAKSHI backend services, "
        "including path parameters, authentication requirements, and rate-limiting thresholds.",
        styles["AcademicBody"]
    ))

    app_a_data = [
        [Paragraph("<b>Route / Path</b>", styles["TableHeader"]), Paragraph("<b>Method</b>", styles["TableHeader"]), Paragraph("<b>Auth Required</b>", styles["TableHeader"]), Paragraph("<b>Module</b>", styles["TableHeader"]), Paragraph("<b>Rate Limit</b>", styles["TableHeader"])],
        [Paragraph("/api/v1/auth/token", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("None (OIDC Exchange)", styles["TableCell"]), Paragraph("MOD-02", styles["TableCell"]), Paragraph("10 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/cases", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (IO/Admin)", styles["TableCell"]), Paragraph("MOD-01", styles["TableCell"]), Paragraph("30 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/cases/{case_id}", styles["TableCellBold"]), Paragraph("GET", styles["TableCell"]), Paragraph("Bearer JWT (Assigned IO)", styles["TableCell"]), Paragraph("MOD-01", styles["TableCell"]), Paragraph("120 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/cases/{case_id}/stage", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (Supervisory)", styles["TableCell"]), Paragraph("MOD-04", styles["TableCell"]), Paragraph("10 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/evidence/upload", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (Assigned IO)", styles["TableCell"]), Paragraph("MOD-05 to MOD-08", styles["TableCell"]), Paragraph("60 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/evidence/{id}/hash", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (Assigned IO)", styles["TableCell"]), Paragraph("MOD-09", styles["TableCell"]), Paragraph("60 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/evidence/{id}/lock", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (Assigned IO)", styles["TableCell"]), Paragraph("MOD-10", styles["TableCell"]), Paragraph("30 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/evidence/{id}/encrypt", styles["TableCellBold"]), Paragraph("POST", styles["TableCell"]), Paragraph("Bearer JWT (System/IO)", styles["TableCell"]), Paragraph("MOD-11", styles["TableCell"]), Paragraph("60 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/evidence/{id}/verify", styles["TableCellBold"]), Paragraph("GET", styles["TableCell"]), Paragraph("Bearer JWT (Assigned IO)", styles["TableCell"]), Paragraph("MOD-09 / MOD-11", styles["TableCell"]), Paragraph("120 req / min", styles["TableCell"])],
        [Paragraph("/api/v1/health", styles["TableCellBold"]), Paragraph("GET", styles["TableCell"]), Paragraph("Public / Optional Token", styles["TableCell"]), Paragraph("Health", styles["TableCell"]), Paragraph("300 req / min", styles["TableCell"])],
    ]
    t_app_a = Table(app_a_data, colWidths=[150, 45, 120, 65, 71])
    t_app_a.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_app_a)

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX B: DATABASE SCHEMA SPECIFICATION
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_b"))
    story.append(Paragraph("Appendix B — Database Schema Specification", styles["SectionHeading"]))
    story.append(Paragraph(
        "This appendix documents the Data Definition Language (DDL) physical schema specifications for the core relational tables "
        "persisted in the database.",
        styles["AcademicBody"]
    ))

    schema_sql = (
        "CREATE TABLE cases (\n"
        "    case_id VARCHAR(36) PRIMARY KEY, -- UUIDv4\n"
        "    fir_number VARCHAR(64) UNIQUE NOT NULL,\n"
        "    police_station VARCHAR(128) NOT NULL,\n"
        "    stage VARCHAR(32) NOT NULL DEFAULT 'INITIATED',\n"
        "    assigned_io_id VARCHAR(64) NOT NULL,\n"
        "    incident_datetime TIMESTAMP NOT NULL,\n"
        "    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
        ");\n\n"
        "CREATE TABLE evidence (\n"
        "    evidence_id VARCHAR(36) PRIMARY KEY, -- UUIDv4\n"
        "    case_id VARCHAR(36) NOT NULL REFERENCES cases(case_id) ON DELETE RESTRICT,\n"
        "    original_filename VARCHAR(256) NOT NULL,\n"
        "    mime_type VARCHAR(128) NOT NULL,\n"
        "    file_size_bytes BIGINT NOT NULL,\n"
        "    sha256_hash VARCHAR(64) NOT NULL,\n"
        "    sha3_512_hash VARCHAR(128),\n"
        "    worm_path VARCHAR(512) NOT NULL,\n"
        "    vault_path VARCHAR(512),\n"
        "    is_locked BOOLEAN NOT NULL DEFAULT FALSE,\n"
        "    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,\n"
        "    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
        ");\n\n"
        "CREATE TABLE audit_events (\n"
        "    event_id VARCHAR(36) PRIMARY KEY, -- UUIDv4\n"
        "    case_id VARCHAR(36) REFERENCES cases(case_id) ON DELETE SET NULL,\n"
        "    officer_badge VARCHAR(64) NOT NULL,\n"
        "    action_type VARCHAR(64) NOT NULL,\n"
        "    evidence_id VARCHAR(36),\n"
        "    status VARCHAR(32) NOT NULL,\n"
        "    details_json TEXT,\n"
        "    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
        ");"
    )
    story.append(Paragraph(schema_sql.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["AlgorithmText"]))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX C: TEST SUITE CATALOG
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_c"))
    story.append(Paragraph("Appendix C — Empirical Test Suite Catalog", styles["SectionHeading"]))
    story.append(Paragraph(
        "A structured summary of test case classes and automated verification suites verifying all 298 tests with zero failures.",
        styles["AcademicBody"]
    ))

    app_c_data = [
        [Paragraph("<b>Test Suite File</b>", styles["TableHeader"]), Paragraph("<b>Target Subsystem</b>", styles["TableHeader"]), Paragraph("<b>Scope & Coverage</b>", styles["TableHeader"]), Paragraph("<b>Tests Count</b>", styles["TableHeader"])],
        [Paragraph("tests/unit/test_case_service.py", styles["TableCellBold"]), Paragraph("MOD-01 Case Service", styles["TableCell"]), Paragraph("Case creation, duplicate FIR handling, isolation", styles["TableCell"]), Paragraph("22 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_auth_service.py", styles["TableCellBold"]), Paragraph("MOD-02 / MOD-03", styles["TableCell"]), Paragraph("JWT parsing, expiration, signature, RBAC/ABAC", styles["TableCell"]), Paragraph("40 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_stage_engine.py", styles["TableCellBold"]), Paragraph("MOD-04 Stage Engine", styles["TableCell"]), Paragraph("Statutory state transitions, illegal stage jumps", styles["TableCell"]), Paragraph("16 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_intake_service.py", styles["TableCellBold"]), Paragraph("MOD-05 Intake Service", styles["TableCell"]), Paragraph("Streaming buffers, chunk boundary conditions", styles["TableCell"]), Paragraph("20 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_mime_validator.py", styles["TableCellBold"]), Paragraph("MOD-06 MIME Sniffer", styles["TableCell"]), Paragraph("Magic byte lookup, spoofed extension detection", styles["TableCell"]), Paragraph("18 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_antivirus_scanner.py", styles["TableCellBold"]), Paragraph("MOD-07 Antivirus", styles["TableCell"]), Paragraph("ClamAV socket mocking, fail-closed quarantine", styles["TableCell"]), Paragraph("16 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_worm_commit.py", styles["TableCellBold"]), Paragraph("MOD-08 WORM Commit", styles["TableCell"]), Paragraph("POSIX read-only permission, SHA-256 pre-hash", styles["TableCell"]), Paragraph("18 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_dual_hash_service.py", styles["TableCellBold"]), Paragraph("MOD-09 Dual Hashing", styles["TableCell"]), Paragraph("SHA256+SHA3-512, pre-hash matching, bit-rot", styles["TableCell"]), Paragraph("20 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_object_lock_service.py", styles["TableCellBold"]), Paragraph("MOD-10 Object Lock", styles["TableCell"]), Paragraph("Retention manifests, legal hold immutability", styles["TableCell"]), Paragraph("32 passed", styles["TableCell"])],
        [Paragraph("tests/unit/test_encryption_service.py", styles["TableCellBold"]), Paragraph("MOD-11 AES-GCM", styles["TableCell"]), Paragraph("GCM cipher, nonce uniqueness, AAD verification", styles["TableCell"]), Paragraph("20 passed", styles["TableCell"])],
        [Paragraph("tests/integration/test_end_to_end.py", styles["TableCellBold"]), Paragraph("Phases 1–3 Integration", styles["TableCell"]), Paragraph("End-to-end multi-step ingest, lock, encrypt", styles["TableCell"]), Paragraph("76 passed", styles["TableCell"])],
        [Paragraph("<b>Total Verified Suite</b>", styles["TableHeader"]), Paragraph("<b>Cumulative Platform</b>", styles["TableHeader"]), Paragraph("<b>100% Pass Rate Across All Modules</b>", styles["TableHeader"]), Paragraph("<b>298 passed</b>", styles["TableHeader"])],
    ]
    t_app_c = Table(app_c_data, colWidths=[150, 95, 140, 66])
    t_app_c.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_app_c)

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX D: CORE PYDANTIC MODELS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_d"))
    story.append(Paragraph("Appendix D — Core Domain Pydantic Data Models", styles["SectionHeading"]))
    story.append(Paragraph(
        "Representative Python Pydantic v2 schemas enforcing strict validation boundaries across the API.",
        styles["AcademicBody"]
    ))

    pydantic_code = (
        "from pydantic import BaseModel, Field, UUID4\n"
        "from datetime import datetime\n"
        "from enum import Enum\n\n"
        "class CaseStage(str, Enum):\n"
        "    INITIATED = 'INITIATED'\n"
        "    INQUEST = 'INQUEST'\n"
        "    FORENSIC_ANALYSIS = 'FORENSIC_ANALYSIS'\n"
        "    CHARGESHEET_PREPARATION = 'CHARGESHEET_PREPARATION'\n"
        "    CLOSED = 'CLOSED'\n\n"
        "class EvidenceUploadResponse(BaseModel):\n"
        "    evidence_id: UUID4\n"
        "    case_id: UUID4\n"
        "    original_filename: str\n"
        "    mime_type: str\n"
        "    file_size_bytes: int\n"
        "    sha256_pre_hash: str = Field(..., min_length=64, max_length=64)\n"
        "    worm_storage_path: str\n"
        "    scan_status: str\n"
        "    created_at: datetime\n\n"
        "class DualHashVerificationResponse(BaseModel):\n"
        "    evidence_id: UUID4\n"
        "    sha256: str = Field(..., min_length=64, max_length=64)\n"
        "    sha3_512: str = Field(..., min_length=128, max_length=128)\n"
        "    pre_hash_matched: bool\n"
        "    integrity_verified: bool"
    )
    story.append(Paragraph(pydantic_code.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["AlgorithmText"]))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX E: EXAMPLE API RESPONSES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_e"))
    story.append(Paragraph("Appendix E — Example API Payloads and JSON Responses", styles["SectionHeading"]))
    story.append(Paragraph(
        "Sample JSON response produced by the `/api/v1/evidence/{id}/hash` endpoint confirming dual hashing and bit-rot absence:",
        styles["AcademicBody"]
    ))

    json_sample = (
        "{\n"
        '  "status": "SUCCESS",\n'
        '  "timestamp": "2026-10-02T10:15:30.124567Z",\n'
        '  "data": {\n'
        '    "evidence_id": "c7a8b9d0-1234-5678-9abc-def012345678",\n'
        '    "case_id": "e4f5a6b7-8901-2345-6789-abcdef012345",\n'
        '    "sha256_digest": "a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2",\n'
        '    "sha3_512_digest": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e",\n'
        '    "pre_hash_match": true,\n'
        '    "bit_rot_detected": false,\n'
        '    "cryptographic_binding": "COMPLETED",\n'
        '    "signed_custody_receipt": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."\n'
        "  }\n"
        "}"
    )
    story.append(Paragraph(json_sample.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["AlgorithmText"]))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX F: ACRONYMS & GLOSSARY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_f"))
    story.append(Paragraph("Appendix F — Acronyms and Technical Glossary", styles["SectionHeading"]))
    story.append(Paragraph(
        "• <b>Bit-Rot:</b> Spontaneous, silent degradation of data bits on electronic storage media over time.<br/>"
        "• <b>Chain of Custody:</b> The chronological, unbroken documentation showing seizure, custody, control, transfer, and analysis of evidence.<br/>"
        "• <b>EC-MORE:</b> Evidence-Constrained Modus Operandi Reconstruction; SAKSHI's core paradigm preventing ungrounded AI inferences.<br/>"
        "• <b>Inquest:</b> A statutory judicial or police inquiry into the cause and manner of an unnatural or unexplained death.<br/>"
        "• <b>WORM:</b> Write Once, Read Many; storage media controls ensuring data cannot be rewritten, modified, or deleted once committed.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX G: ADDITIONAL INTERFACE SPECIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("app_g"))
    story.append(Paragraph("Appendix G — Additional System Interface Specifications", styles["SectionHeading"]))
    story.append(Paragraph(
        "The web-based forensic interface adheres to WCAG 2.1 AA accessibility standards and enforces high-contrast forensic viewing "
        "modes suitable for police station and laboratory environments. Interface states communicate cryptographic validity through unambiguous "
        "visual status indicators: Green (Verified & Locked WORM Exhibit), Amber (Pending Verification / Antivirus Scan), and Red "
        "(Quarantined Threat / Integrity Mismatch / Security Denial).",
        styles["AcademicBody"]
    ))

    story.append(PageBreak())
    return story
