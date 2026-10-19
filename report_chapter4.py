"""
Chapter 4: Implementation for SAKSHI Academic Project Report.
Target length: 12–14 pages.
Covers 20 detailed sections:
4.1 Development Environment & Tooling
4.2 Technology Stack Specification (Table 4.1)
4.3 Backend Architecture & Design Patterns (Figure 4.1 & 4.2)
4.4 Database Implementation & Migration
4.5 Authentication Implementation (OIDC/JWT, Figure 4.5)
4.6 Authorization Implementation (RBAC/ABAC)
4.7 Case Management Service Implementation (MOD-01, Table 4.2)
4.8 Evidence Intake Service Implementation (MOD-05)
4.9 MIME & Signature Validation Implementation (MOD-06)
4.10 Antivirus Inspection Implementation (MOD-07)
4.11 WORM Commit Implementation (MOD-08)
4.12 Dual Hashing Implementation (MOD-09, Figure 4.3)
4.13 WORM Object Lock Implementation (MOD-10)
4.14 AES-256-GCM Encryption Implementation (MOD-11, Figure 4.4)
4.15 API Implementation & Endpoint Contracts (Table 4.3)
4.16 Core Algorithmic Pseudocode (Algorithms 4.1 to 4.15)
4.17 Security Implementation & Path Traversal Guard
4.18 Error Handling & Domain Exception Hierarchy
4.19 Audit Logging & Forensic Traceability
4.20 User Interface & Forensic Dashboard Placeholders (Figures 4.6 to 4.19, Table 4.4)
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors
from report_diagrams import (
    get_backend_architecture_diagram,
    get_evidence_processing_workflow_diagram,
    get_dual_hashing_workflow_diagram,
    get_aes_gcm_workflow_diagram,
    get_auth_flow_diagram,
    get_screenshot_placeholder,
)

W_CONTENT = 451.27


def get_chapter4(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ch4"))
    story.append(Paragraph("CHAPTER 4", styles["ChapterHeading"]))
    story.append(Paragraph("IMPLEMENTATION", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # 4.1 Development Environment & Tooling
    story.append(page_tracker_cls("sec4_1"))
    story.append(Paragraph("4.1 Development Environment & Tooling", styles["SectionHeading"]))
    story.append(Paragraph(
        "The SAKSHI platform is developed using modern, production-grade systems software engineering practices in Python 3.12 LTS. "
        "The development environment is containerized using Docker to ensure complete parity across engineering, testing, and forensic "
        "evaluation environments. Dependency management and virtual environments are pinned to exact semantic versions. The platform "
        "leverages FastAPI as its asynchronous web core, Uvicorn as the ASGI high-performance server, SQLAlchemy 2.0 with asynchronous "
        "sessions for database access, Pydantic v2 for data parsing and validation, and pytest for automated test orchestration.",
        styles["AcademicBody"]
    ))

    # 4.2 Technology Stack Specification
    story.append(page_tracker_cls("sec4_2"))
    story.append(Paragraph("4.2 Technology Stack Specification", styles["SectionHeading"]))
    story.append(Paragraph(
        "Table 4.1 details the multi-layer technology stack powering the implemented modules of the SAKSHI platform.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab4_1"))
    story.append(Paragraph("<b>Table 4.1: Complete SAKSHI Technology Stack & Architectural Rationale</b>", styles["TableCaption"]))

    tech_data = [
        [Paragraph("<b>Architectural Layer</b>", styles["TableHeader"]), Paragraph("<b>Technology / Library</b>", styles["TableHeader"]), Paragraph("<b>Version / Protocol</b>", styles["TableHeader"]), Paragraph("<b>Architectural Role & Security Rationale</b>", styles["TableHeader"])],
        [Paragraph("<b>Core Language</b>", styles["TableCellBold"]), Paragraph("Python", styles["TableCell"]), Paragraph("3.12 LTS", styles["TableCell"]), Paragraph("Modern asynchronous runtime, typing support, and mature cryptographic bindings", styles["TableCell"])],
        [Paragraph("<b>API Web Framework</b>", styles["TableCellBold"]), Paragraph("FastAPI", styles["TableCell"]), Paragraph("0.110+", styles["TableCell"]), Paragraph("High-throughput async ASGI framework with automated OpenAPI / Swagger documentation", styles["TableCell"])],
        [Paragraph("<b>ASGI Web Server</b>", styles["TableCellBold"]), Paragraph("Uvicorn", styles["TableCell"]), Paragraph("0.28+", styles["TableCell"]), Paragraph("Lightweight, event-loop driven production ASGI server supporting HTTP/1.1 and HTTP/2", styles["TableCell"])],
        [Paragraph("<b>Data Validation</b>", styles["TableCellBold"]), Paragraph("Pydantic v2", styles["TableCell"]), Paragraph("2.6+", styles["TableCell"]), Paragraph("Strict runtime schema enforcement, type validation, and serialization", styles["TableCell"])],
        [Paragraph("<b>Database ORM</b>", styles["TableCellBold"]), Paragraph("SQLAlchemy", styles["TableCell"]), Paragraph("2.0+", styles["TableCell"]), Paragraph("Async relational abstraction supporting SQLite WAL and PostgreSQL", styles["TableCell"])],
        [Paragraph("<b>Relational Store</b>", styles["TableCellBold"]), Paragraph("SQLite / PostgreSQL", styles["TableCell"]), Paragraph("3.45 / 16.0", styles["TableCell"]), Paragraph("Transactional ACID data store with strict referential integrity and foreign keys", styles["TableCell"])],
        [Paragraph("<b>Authentication</b>", styles["TableCellBold"]), Paragraph("PyJWT / Cryptography", styles["TableCell"]), Paragraph("2.8+ / 42.0+", styles["TableCell"]), Paragraph("OIDC integration, RS256/EdDSA asymmetric signature verification", styles["TableCell"])],
        [Paragraph("<b>Symmetric Cryptography</b>", styles["TableCellBold"]), Paragraph("Python Cryptography (hazmat)", styles["TableCell"]), Paragraph("42.0+", styles["TableCell"]), Paragraph("FIPS-compliant AES-256-GCM cipher with Additional Authenticated Data (AAD)", styles["TableCell"])],
        [Paragraph("<b>Hashing Primitives</b>", styles["TableCellBold"]), Paragraph("hashlib (OpenSSL backend)", styles["TableCell"]), Paragraph("Standard Lib", styles["TableCell"]), Paragraph("Dual cryptographic hashing combining SHA-256 (FIPS 180-4) and SHA3-512 (FIPS 202)", styles["TableCell"])],
        [Paragraph("<b>Antivirus Engine</b>", styles["TableCellBold"]), Paragraph("ClamAV (clamd daemon)", styles["TableCell"]), Paragraph("1.3+", styles["TableCell"]), Paragraph("Open-source anti-malware daemon streaming INSTREAM chunks over TCP socket 3310", styles["TableCell"])],
        [Paragraph("<b>Test Framework</b>", styles["TableCellBold"]), Paragraph("pytest / pytest-asyncio", styles["TableCell"]), Paragraph("8.0+", styles["TableCell"]), Paragraph("Automated unit, integration, and security regression verification suite", styles["TableCell"])],
    ]

    tech_table = Table(tech_data, colWidths=[90, 95, 65, 201])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(tech_table)

    story.append(Spacer(1, 10))

    # 4.3 Backend Architecture & Design Patterns
    story.append(page_tracker_cls("sec4_3"))
    story.append(Paragraph("4.3 Backend Architecture & Design Patterns", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 4.1 illustrates the layered backend architecture, and Figure 4.2 diagrams the sequential verification sequence governing "
        "every ingested exhibit.",
        styles["AcademicBody"]
    ))

    story.append(get_backend_architecture_diagram())
    story.append(page_tracker_cls("fig4_1"))
    story.append(Paragraph("<b>Figure 4.1: Backend Layered Architecture & Modular Orchestration</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 8))

    story.append(get_evidence_processing_workflow_diagram())
    story.append(page_tracker_cls("fig4_2"))
    story.append(Paragraph("<b>Figure 4.2: Evidence Processing Workflow & Stage Verification Sequence</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 4.4 Database Implementation & Migration
    story.append(page_tracker_cls("sec4_4"))
    story.append(Paragraph("4.4 Database Implementation & Migration", styles["SectionHeading"]))
    story.append(Paragraph(
        "The relational schema is implemented using SQLAlchemy declarative models. Tables are indexed on primary keys, case IDs, and "
        "forensic hashes. SQLite operates in WAL (Write-Ahead Logging) mode, enabling concurrent reads while write transactions are safely "
        "serialized, preventing database lock contention during concurrent exhibit uploads.",
        styles["AcademicBody"]
    ))

    # 4.5 Authentication Implementation
    story.append(page_tracker_cls("sec4_5"))
    story.append(Paragraph("4.5 Authentication Implementation (OIDC/JWT)", styles["SectionHeading"]))
    story.append(Paragraph(
        "MOD-02 implements OpenID Connect token authentication. Figure 4.5 illustrates the token verification sequence, checking "
        "cryptographic signatures, issuer, audience, and expiration claims before injecting user context into the request pipeline.",
        styles["AcademicBody"]
    ))

    story.append(get_auth_flow_diagram())
    story.append(page_tracker_cls("fig4_5"))
    story.append(Paragraph("<b>Figure 4.5: Authentication and Authorization Flow (OIDC -> JWT -> RBAC/ABAC)</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 4.6 Authorization Implementation
    story.append(page_tracker_cls("sec4_6"))
    story.append(Paragraph("4.6 Authorization Implementation (RBAC/ABAC)", styles["SectionHeading"]))
    story.append(Paragraph(
        "MOD-03 enforces hybrid Role-Based and Attribute-Based Access Control. Role-Based permissions define system capabilities (e.g., "
        "`CREATE_CASE`, `UPLOAD_EVIDENCE`), while Attribute-Based rules verify contextual attributes: the officer's police station jurisdiction "
        "must match the case station, and the officer must be explicitly assigned to the specific case ID.",
        styles["AcademicBody"]
    ))

    # 4.7 to 4.14 Module Implementation Details
    story.append(page_tracker_cls("sec4_7"))
    story.append(Paragraph("4.7 Case Management Service Implementation (MOD-01)", styles["SectionHeading"]))
    story.append(Paragraph(
        "MOD-01 manages case lifecycle registration. Table 4.2 provides a functional overview of all implemented modules (MOD-01 to MOD-11).",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab4_2"))
    story.append(Paragraph("<b>Table 4.2: Implemented Modules Functional Specification (MOD-01 to MOD-11)</b>", styles["TableCaption"]))

    mod_spec_data = [
        [Paragraph("<b>Module ID</b>", styles["TableHeader"]), Paragraph("<b>Input Parameters</b>", styles["TableHeader"]), Paragraph("<b>Internal Processing Logic</b>", styles["TableHeader"]), Paragraph("<b>Output Artifacts</b>", styles["TableHeader"]), Paragraph("<b>Database / Storage Impact</b>", styles["TableHeader"])],
        [Paragraph("<b>MOD-01</b>", styles["TableCellBold"]), Paragraph("FIR details, station ID, IO badge", styles["TableCell"]), Paragraph("Validates metadata, generates UUIDv4 case ID, creates case workspace partition", styles["TableCell"]), Paragraph("CaseRecord instance", styles["TableCell"]), Paragraph("Inserts into `CASES` table", styles["TableCell"])],
        [Paragraph("<b>MOD-02</b>", styles["TableCellBold"]), Paragraph("Authorization Bearer header (JWT)", styles["TableCell"]), Paragraph("Verifies RS256/EdDSA signature against JWKS, checks exp/nbf/aud claims", styles["TableCell"]), Paragraph("AuthenticatedUser context", styles["TableCell"]), Paragraph("Reads user session state", styles["TableCell"])],
        [Paragraph("<b>MOD-03</b>", styles["TableCellBold"]), Paragraph("User context, case_id, action", styles["TableCell"]), Paragraph("Evaluates RBAC role matrix + ABAC jurisdiction and assignment rules", styles["TableCell"]), Paragraph("Authorization Grant / Deny", styles["TableCell"]), Paragraph("Logs to `AUDIT_EVENTS` on failure", styles["TableCell"])],
        [Paragraph("<b>MOD-04</b>", styles["TableCellBold"]), Paragraph("case_id, target_stage, IO token", styles["TableCell"]), Paragraph("Validates permissible stage transitions against state machine graph", styles["TableCell"]), Paragraph("Updated CaseStage", styles["TableCell"]), Paragraph("Updates `stage` in `CASES`", styles["TableCell"])],
        [Paragraph("<b>MOD-05</b>", styles["TableCellBold"]), Paragraph("Multi-part file stream, metadata", styles["TableCell"]), Paragraph("Buffers chunks, generates evidence_id, verifies size constraints (<100MB)", styles["TableCell"]), Paragraph("Raw evidence buffer", styles["TableCell"]), Paragraph("Inserts into `EVIDENCE` table", styles["TableCell"])],
        [Paragraph("<b>MOD-06</b>", styles["TableCellBold"]), Paragraph("File bytes, declared MIME", styles["TableCell"]), Paragraph("Sniffs first 16 bytes against magic signature registry; detects spoofing", styles["TableCell"]), Paragraph("Verified MIME type", styles["TableCell"]), Paragraph("Updates `mime_type` in `EVIDENCE`", styles["TableCell"])],
        [Paragraph("<b>MOD-07</b>", styles["TableCellBold"]), Paragraph("File path, clamd TCP socket", styles["TableCell"]), Paragraph("Streams INSTREAM chunks to ClamAV; quarantines threats with 0000 perms", styles["TableCell"]), Paragraph("AntivirusVerdict (CLEAN)", styles["TableCell"]), Paragraph("Updates `scan_status` in `EVIDENCE`", styles["TableCell"])],
        [Paragraph("<b>MOD-08</b>", styles["TableCellBold"]), Paragraph("Clean file path, case_id", styles["TableCell"]), Paragraph("Writes to read-only POSIX directory (0440 mode); computes SHA-256 pre-hash", styles["TableCell"]), Paragraph("WORM file ref + pre-hash", styles["TableCell"]), Paragraph("Updates `worm_path` in `EVIDENCE`", styles["TableCell"])],
        [Paragraph("<b>MOD-09</b>", styles["TableCellBold"]), Paragraph("WORM file path, pre-hash", styles["TableCell"]), Paragraph("Computes independent SHA-256 and SHA3-512; verifies SHA-256 matches pre-hash", styles["TableCell"]), Paragraph("DualHashReceipt", styles["TableCell"]), Paragraph("Updates `sha256` & `sha3_512` in DB", styles["TableCell"])],
        [Paragraph("<b>MOD-10</b>", styles["TableCellBold"]), Paragraph("Dual-hash receipt, retention_days", styles["TableCell"]), Paragraph("Applies WORM Object Lock metadata manifest; prevents delete/overwrite", styles["TableCell"]), Paragraph("LockedObjectReference", styles["TableCell"]), Paragraph("Creates JSON legal lock manifest", styles["TableCell"])],
        [Paragraph("<b>MOD-11</b>", styles["TableCellBold"]), Paragraph("Locked object, case key, AAD", styles["TableCell"]), Paragraph("Encrypts bytes via AES-256-GCM using CSPRNG 96-bit nonce; binds case AAD", styles["TableCell"]), Paragraph("EncryptedVaultObject", styles["TableCell"]), Paragraph("Writes `.enc` vault ciphertext file", styles["TableCell"])],
    ]

    mod_spec_table = Table(mod_spec_data, colWidths=[55, 95, 125, 85, 91])
    mod_spec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(mod_spec_table)

    story.append(Spacer(1, 10))

    # Detailed Dual Hashing & Encryption Workflows
    story.append(page_tracker_cls("sec4_12"))
    story.append(Paragraph("4.12 Dual Hashing Implementation (MOD-09)", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 4.3 illustrates the dual hashing architecture implemented in MOD-09, which computes independent digests using SHA-256 "
        "(Merkle-Damgård) and SHA3-512 (Keccak sponge). It compares the computed SHA-256 against the MOD-08 pre-hash to verify that zero "
        "bit-rot occurred during WORM commit.",
        styles["AcademicBody"]
    ))

    story.append(get_dual_hashing_workflow_diagram())
    story.append(page_tracker_cls("fig4_3"))
    story.append(Paragraph("<b>Figure 4.3: Dual Hashing Verification Workflow (SHA-256 + SHA3-512)</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 8))

    story.append(page_tracker_cls("sec4_14"))
    story.append(Paragraph("4.14 AES-256-GCM Encryption Implementation (MOD-11)", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 4.4 diagrams the authenticated encryption pipeline implemented in MOD-11. The cipher generates a cryptographically "
        "secure random 96-bit nonce, derives a 256-bit case key, binds the case ID and dual hashes as Additional Authenticated Data (AAD), "
        "and computes a 128-bit authentication tag over GF(2^128).",
        styles["AcademicBody"]
    ))

    story.append(get_aes_gcm_workflow_diagram())
    story.append(page_tracker_cls("fig4_4"))
    story.append(Paragraph("<b>Figure 4.4: AES-256-GCM Envelope Encryption & AAD Binding Workflow</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 4.15 API Implementation & Endpoint Contracts
    story.append(page_tracker_cls("sec4_15"))
    story.append(Paragraph("4.15 API Implementation & Endpoint Contracts", styles["SectionHeading"]))
    story.append(Paragraph(
        "Table 4.3 documents the RESTful API endpoints exposed across the implemented modules, including HTTP verbs, request payloads, "
        "and HTTP status codes.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab4_3"))
    story.append(Paragraph("<b>Table 4.3: RESTful API Specification & Endpoint Status Code Registry</b>", styles["TableCaption"]))

    api_data = [
        [Paragraph("<b>HTTP Verb & Path</b>", styles["TableHeader"]), Paragraph("<b>Target Module</b>", styles["TableHeader"]), Paragraph("<b>Input Request Payload</b>", styles["TableHeader"]), Paragraph("<b>Success Response</b>", styles["TableHeader"]), Paragraph("<b>Status Codes</b>", styles["TableHeader"])],
        [Paragraph("POST /api/v1/cases", styles["TableCellBold"]), Paragraph("MOD-01", styles["TableCell"]), Paragraph("JSON: fir_number, police_station, incident_date", styles["TableCell"]), Paragraph("JSON: case_id, stage, created_at", styles["TableCell"]), Paragraph("201, 400, 401, 409", styles["TableCell"])],
        [Paragraph("GET /api/v1/cases/{case_id}", styles["TableCellBold"]), Paragraph("MOD-01", styles["TableCell"]), Paragraph("Path param: case_id (UUID)", styles["TableCell"]), Paragraph("JSON: full case details & assigned IO", styles["TableCell"]), Paragraph("200, 401, 403, 404", styles["TableCell"])],
        [Paragraph("POST /api/v1/cases/{id}/stage", styles["TableCellBold"]), Paragraph("MOD-04", styles["TableCell"]), Paragraph("JSON: target_stage, justification_notes", styles["TableCell"]), Paragraph("JSON: case_id, new_stage", styles["TableCell"]), Paragraph("200, 400, 403, 404", styles["TableCell"])],
        [Paragraph("POST /api/v1/evidence/upload", styles["TableCellBold"]), Paragraph("MOD-05 to MOD-08", styles["TableCell"]), Paragraph("Multipart/form-data: case_id, file, label", styles["TableCell"]), Paragraph("JSON: evidence_id, pre_hash, worm_path", styles["TableCell"]), Paragraph("201, 400, 403, 415, 422", styles["TableCell"])],
        [Paragraph("POST /api/v1/evidence/{id}/hash", styles["TableCellBold"]), Paragraph("MOD-09", styles["TableCell"]), Paragraph("Path param: evidence_id (UUID)", styles["TableCell"]), Paragraph("JSON: sha256, sha3_512, verified: true", styles["TableCell"]), Paragraph("200, 400, 404, 409", styles["TableCell"])],
        [Paragraph("POST /api/v1/evidence/{id}/lock", styles["TableCellBold"]), Paragraph("MOD-10", styles["TableCell"]), Paragraph("JSON: lock_mode, retention_days", styles["TableCell"]), Paragraph("JSON: lock_reference, manifest_path", styles["TableCell"]), Paragraph("200, 400, 403, 404", styles["TableCell"])],
        [Paragraph("POST /api/v1/evidence/{id}/encrypt", styles["TableCellBold"]), Paragraph("MOD-11", styles["TableCell"]), Paragraph("Path param: evidence_id (UUID)", styles["TableCell"]), Paragraph("JSON: vault_path, nonce_hex, tag_hex", styles["TableCell"]), Paragraph("200, 400, 404, 500", styles["TableCell"])],
        [Paragraph("GET /api/v1/evidence/{id}/verify", styles["TableCellBold"]), Paragraph("MOD-09 / MOD-11", styles["TableCell"]), Paragraph("Path param: evidence_id (UUID)", styles["TableCell"]), Paragraph("JSON: integrity_verified: true, checks", styles["TableCell"]), Paragraph("200, 400, 404, 409", styles["TableCell"])],
        [Paragraph("GET /api/v1/health", styles["TableCellBold"]), Paragraph("System Health", styles["TableCell"]), Paragraph("None (Public or authenticated)", styles["TableCell"]), Paragraph("JSON: status: healthy, clamd: ok, db: ok", styles["TableCell"]), Paragraph("200, 503", styles["TableCell"])],
    ]

    api_table = Table(api_data, colWidths=[120, 55, 120, 105, 51])
    api_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(api_table)

    story.append(Spacer(1, 10))

    # 4.16 Core Algorithmic Pseudocode (15 Algorithms)
    story.append(page_tracker_cls("sec4_16"))
    story.append(Paragraph("4.16 Core Algorithmic Pseudocode (Algorithms 4.1 to 4.15)", styles["SectionHeading"]))
    story.append(Paragraph(
        "The following 15 algorithmic specifications provide complete implementation logic, inputs, step-by-step operations, outputs, "
        "and security considerations for every cryptographic, validation, and storage operation in SAKSHI.",
        styles["AcademicBody"]
    ))

    algos = [
        ("Algorithm 4.1: Cryptographic Case ID Generation",
         "Inputs: fir_number (str), police_station (str), year (int)\n"
         "Output: case_id (UUIDv4 string)\n"
         "Security Consideration: Generates RFC 4122 compliant UUIDv4 from CSPRNG (os.urandom) preventing ID enumeration attacks.\n"
         "Steps:\n"
         "1: raw_random_bytes = CSPRNG_GetRandomBytes(16)\n"
         "2: case_uuid = FormatAsUUIDv4(raw_random_bytes)\n"
         "3: Verify case_uuid does not collide with existing DB records\n"
         "4: Return case_uuid"),

        ("Algorithm 4.2: JWT Bearer Token Verification",
         "Inputs: bearer_token (str), jwks_public_keys (dict), expected_audience (str)\n"
         "Output: AuthenticatedClaims (dict) OR Raise SecurityException\n"
         "Security Consideration: Rejects 'none' algorithm; strictly validates expiration (exp) and issuer (iss) to block replay.\n"
         "Steps:\n"
         "1: header, payload, signature = ParseJWTComponents(bearer_token)\n"
         "2: If header.alg not in ['RS256', 'EdDSA']: Raise InvalidAlgorithmException()\n"
         "3: public_key = jwks_public_keys.lookup(header.kid)\n"
         "4: VerifySignature(header, payload, signature, public_key)\n"
         "5: VerifyCurrentTimestampBetween(payload.nbf, payload.exp)\n"
         "6: If payload.aud != expected_audience: Raise InvalidAudienceException()\n"
         "7: Return payload.claims"),

        ("Algorithm 4.3: Hybrid RBAC / ABAC Authorization Gate",
         "Inputs: user_context (User), requested_action (str), target_case_id (UUID)\n"
         "Output: GrantAuthorization (bool) OR Raise AccessDeniedException\n"
         "Security Consideration: Enforces principle of least privilege; cross-station access is denied regardless of role.\n"
         "Steps:\n"
         "1: If requested_action not in ROLE_PERMISSIONS[user_context.role]:\n"
         "2:     LogAuditEvent('RBAC_ROLE_DENIED', user_context.badge, requested_action)\n"
         "3:     Raise AccessDeniedException('Insufficient role privileges')\n"
         "4: case_record = Database.LookupCase(target_case_id)\n"
         "5: If user_context.station != case_record.police_station:\n"
         "6:     LogAuditEvent('ABAC_JURISDICTION_MISMATCH', user_context.badge, target_case_id)\n"
         "7:     Raise AccessDeniedException('Station jurisdiction mismatch')\n"
         "8: If user_context.role == 'IO' and user_context.id != case_record.assigned_io_id:\n"
         "9:     Raise AccessDeniedException('Officer not assigned to target case')\n"
         "10: Return True"),

        ("Algorithm 4.4: Canonical Path Traversal Prevention",
         "Inputs: base_storage_dir (Path), user_supplied_filename (str)\n"
         "Output: resolved_safe_path (Path) OR Raise PathTraversalException\n"
         "Security Consideration: Normalizes symlinks and relative '../' elements to guarantee containment within base dir.\n"
         "Steps:\n"
         "1: sanitized_name = SanitizeFilename(user_supplied_filename)\n"
         "2: candidate_path = base_storage_dir.Join(sanitized_name)\n"
         "3: real_candidate = ResolveCanonicalPath(candidate_path)\n"
         "4: real_base = ResolveCanonicalPath(base_storage_dir)\n"
         "5: If not real_candidate.StartsWith(real_base):\n"
         "6:     LogSecurityAlert('PATH_TRAVERSAL_ATTEMPT', user_supplied_filename)\n"
         "7:     Raise PathTraversalException('Directory traversal attempt blocked')\n"
         "8: Return real_candidate"),

        ("Algorithm 4.5: Binary Magic-Byte Inspection & MIME Sniffing",
         "Inputs: file_stream (bytes), declared_mime_type (str)\n"
         "Output: verified_mime (str) OR Raise MimeSignatureMismatchException\n"
         "Security Consideration: Blocks malicious executable files disguised as innocent PDF or JPEG images.\n"
         "Steps:\n"
         "1: magic_header = file_stream.ReadBytes(16)\n"
         "2: detected_mime = MAGIC_BYTE_REGISTRY.Lookup(magic_header)\n"
         "3: If detected_mime is None:\n"
         "4:     Raise UnknownFileSignatureException('Unrecognized binary header')\n"
         "5: If detected_mime != declared_mime_type:\n"
         "6:     LogSecurityAlert('MIME_SPOOF_DETECTED', declared_mime_type, detected_mime)\n"
         "7:     Raise MimeSignatureMismatchException('Declared MIME does not match magic bytes')\n"
         "8: Return detected_mime"),

        ("Algorithm 4.6: Fail-Closed Antivirus Scan Orchestration",
         "Inputs: evidence_path (Path), clamd_socket_address (tuple)\n"
         "Output: AntivirusVerdict (CLEAN) OR Raise MalwareDetectedException\n"
         "Security Consideration: Fails closed on socket timeouts; infected files are quarantined and stripped of all perms.\n"
         "Steps:\n"
         "1: Try Connect(clamd_socket_address, timeout=30s)\n"
         "2: Except SocketError: Raise ScannerUnavailableException('Antivirus daemon unreachable: failing closed')\n"
         "3: StreamFileINSTREAM(evidence_path, socket)\n"
         "4: scan_response = ReadSocketResponse(socket)\n"
         "5: If 'FOUND' in scan_response:\n"
         "6:     threat_name = ExtractThreatName(scan_response)\n"
         "7:     MoveFile(evidence_path, QUARANTINE_DIRECTORY)\n"
         "8:     SetFilePermissions(evidence_path, 0000)\n"
         "9:     LogSecurityAlert('MALWARE_QUARANTINED', threat_name, evidence_path)\n"
         "10:    Raise MalwareDetectedException('Evidence infected with ' + threat_name)\n"
         "11: Else If 'OK' in scan_response: Return AntivirusVerdict('CLEAN')\n"
         "12: Else: Raise ScannerException('Corrupt scanner response')"),

        ("Algorithm 4.7: Buffered SHA-256 Pre-Hash Computation",
         "Inputs: file_path (Path), buffer_size = 65536 bytes\n"
         "Output: sha256_hex_digest (str)\n"
         "Security Consideration: Uses fixed 64KB chunking to prevent memory exhaustion on gigabyte-sized disk/video dumps.\n"
         "Steps:\n"
         "1: hasher = SHA256_Init()\n"
         "2: With Open(file_path, 'rb') as f:\n"
         "3:     While (chunk = f.Read(buffer_size)):\n"
         "4:         hasher.Update(chunk)\n"
         "5: Return hasher.HexDigest()"),

        ("Algorithm 4.8: Buffered SHA3-512 Hash Computation",
         "Inputs: file_path (Path), buffer_size = 65536 bytes\n"
         "Output: sha3_512_hex_digest (str)\n"
         "Security Consideration: Implements FIPS 202 Keccak sponge function providing independent quantum-resilient integrity.\n"
         "Steps:\n"
         "1: hasher = SHA3_512_Init()\n"
         "2: With Open(file_path, 'rb') as f:\n"
         "3:     While (chunk = f.Read(buffer_size)):\n"
         "4:         hasher.Update(chunk)\n"
         "5: Return hasher.HexDigest()"),

        ("Algorithm 4.9: Dual Hash Verification & Bit-Rot Gate",
         "Inputs: worm_file_path (Path), expected_pre_hash (str)\n"
         "Output: (sha256_digest, sha3_512_digest)\n"
         "Security Consideration: Compares newly computed SHA-256 against MOD-08 pre-hash to detect storage transmission errors.\n"
         "Steps:\n"
         "1: current_sha256 = Algorithm_4_7(worm_file_path)\n"
         "2: current_sha3 = Algorithm_4_8(worm_file_path)\n"
         "3: If current_sha256 != expected_pre_hash:\n"
         "4:     LogSecurityAlert('STORAGE_BIT_ROT_DETECTED', worm_file_path)\n"
         "5:     Raise IntegrityMismatchException('Pre-hash validation failed: evidence altered')\n"
         "6: Return (current_sha256, current_sha3)"),

        ("Algorithm 4.10: Immutable POSIX WORM Commit",
         "Inputs: source_temp_path (Path), worm_target_dir (Path)\n"
         "Output: (worm_file_path, pre_hash_sha256)\n"
         "Security Consideration: Sets POSIX file mode to 0440 (read-only for owner/group) preventing modification.\n"
         "Steps:\n"
         "1: pre_hash_sha256 = Algorithm_4_7(source_temp_path)\n"
         "2: target_filename = pre_hash_sha256 + ExtractExtension(source_temp_path)\n"
         "3: worm_file_path = worm_target_dir.Join(target_filename)\n"
         "4: MoveFileAtomic(source_temp_path, worm_file_path)\n"
         "5: SetFilePermissions(worm_file_path, 0o440) # Read-only\n"
         "6: Return (worm_file_path, pre_hash_sha256)"),

        ("Algorithm 4.11: WORM Object Lock & Retention Manifest Application",
         "Inputs: case_id (UUID), evidence_id (UUID), sha256 (str), sha3_512 (str), retention_days (int)\n"
         "Output: LockManifestPath (Path)\n"
         "Security Consideration: Generates immutable JSON manifest binding legal hold status and retention expiration.\n"
         "Steps:\n"
         "1: retain_until = CurrentTimestamp() + DaysToSeconds(retention_days)\n"
         "2: manifest_data = {\n"
         "3:     'evidence_id': str(evidence_id), 'case_id': str(case_id),\n"
         "4:     'sha256': sha256, 'sha3_512': sha3_512,\n"
         "5:     'legal_hold': True, 'retain_until_epoch': retain_until\n"
         "6: }\n"
         "7: manifest_path = LOCK_VAULT_DIR.Join(str(evidence_id) + '.lock.json')\n"
         "8: WriteJSON(manifest_path, manifest_data)\n"
         "9: SetFilePermissions(manifest_path, 0o440)\n"
         "10: Return manifest_path"),

        ("Algorithm 4.12: Cryptographic Nonce Generation",
         "Inputs: None\n"
         "Output: nonce_96 (96-bit binary bytes)\n"
         "Security Consideration: AES-GCM catastrophic failure occurs if nonces repeat. Uses os.urandom CSPRNG.\n"
         "Steps:\n"
         "1: nonce_bytes = os.urandom(12) # 96 bits\n"
         "2: Verify len(nonce_bytes) == 12\n"
         "3: Return nonce_bytes"),

        ("Algorithm 4.13: Additional Authenticated Data (AAD) Construction",
         "Inputs: case_id (UUID), evidence_id (UUID), sha256_hash (str), sha3_512_hash (str)\n"
         "Output: aad_bytes (bytes)\n"
         "Security Consideration: Binds metadata into the GCM authentication tag, preventing cross-case ciphertext swapping.\n"
         "Steps:\n"
         "1: aad_canonical_str = f'CASE:{case_id}|EVID:{evidence_id}|SHA256:{sha256_hash}|SHA3:{sha3_512_hash}'\n"
         "2: aad_bytes = UTF8_Encode(aad_canonical_str)\n"
         "3: Return aad_bytes"),

        ("Algorithm 4.14: AES-256-GCM Envelope Encryption at Rest",
         "Inputs: plaintext_bytes (bytes), case_key_256 (bytes), aad_bytes (bytes)\n"
         "Output: (ciphertext_blob, nonce_12, auth_tag_16)\n"
         "Security Consideration: FIPS 800-38D compliant encryption; computes 128-bit tag over ciphertext and AAD.\n"
         "Steps:\n"
         "1: nonce = Algorithm_4_12()\n"
         "2: cipher = AES_GCM_Init(case_key_256)\n"
         "3: ciphertext_with_tag = cipher.Encrypt(nonce, plaintext_bytes, aad_bytes)\n"
         "4: ciphertext = ciphertext_with_tag[0:-16]\n"
         "5: auth_tag = ciphertext_with_tag[-16:]\n"
         "6: Return (ciphertext, nonce, auth_tag)"),

        ("Algorithm 4.15: AES-256-GCM Decryption and Tag Verification Gate",
         "Inputs: ciphertext (bytes), nonce (bytes), auth_tag (bytes), case_key_256 (bytes), aad_bytes (bytes)\n"
         "Output: plaintext_bytes (bytes) OR Raise CiphertextAuthenticationFailedException\n"
         "Security Consideration: Verifies authentication tag before releasing any plaintext bytes to memory.\n"
         "Steps:\n"
         "1: cipher = AES_GCM_Init(case_key_256)\n"
         "2: payload_to_decrypt = Concatenate(ciphertext, auth_tag)\n"
         "3: Try:\n"
         "4:     plaintext = cipher.Decrypt(nonce, payload_to_decrypt, aad_bytes)\n"
         "5:     Return plaintext\n"
         "6: Except InvalidTagException:\n"
         "7:     LogSecurityAlert('CIPHERTEXT_TAMPERING_DETECTED', aad_bytes)\n"
         "8:     Raise CiphertextAuthenticationFailedException('Galois tag mismatch: ciphertext corrupted or tampered')")
    ]

    for title, body in algos:
        story.append(Paragraph(f"<b>{title}</b>", styles["SubSectionHeading"]))
        story.append(Paragraph(body.replace("\n", "<br/>"), styles["AlgorithmText"]))
        story.append(Spacer(1, 4))

    # 4.17 to 4.19 Implementation Details
    story.append(page_tracker_cls("sec4_17"))
    story.append(Paragraph("4.17 Security Implementation & Path Traversal Guard", styles["SectionHeading"]))
    story.append(Paragraph(
        "All filesystem interactions strictly resolve canonical realpaths using `os.path.realpath()`, verifying that destination paths "
        "commence with the authorized case partition directory. Attempts to inject path separators or `../` sequences trigger HTTP 400 "
        "exceptions and emit audit alerts.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("sec4_18"))
    story.append(Paragraph("4.18 Error Handling & Domain Exception Hierarchy", styles["SectionHeading"]))
    story.append(Paragraph(
        "The codebase defines a granular, domain-specific exception hierarchy inheriting from `SakshiBaseException`. Specialized classes "
        "include `MimeSignatureMismatchException`, `MalwareDetectedException`, `SHA256IntegrityMismatchException`, and "
        "`CiphertextAuthenticationFailedException`. FastAPI exception handlers intercept these errors, returning standard RFC 7807 "
        "problem details while masking internal server traces.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("sec4_19"))
    story.append(Paragraph("4.19 Audit Logging & Forensic Traceability", styles["SectionHeading"]))
    story.append(Paragraph(
        "Every security-relevant operation—intake, validation failure, quarantine, hashing, locking, and decryption—is persisted to the "
        "`AUDIT_EVENTS` database table with microsecond UTC timestamps, officer badge numbers, and cryptographic exhibit hashes.",
        styles["AcademicBody"]
    ))

    # 4.20 User Interface & Forensic Dashboard Placeholders
    story.append(page_tracker_cls("sec4_20"))
    story.append(Paragraph("4.20 User Interface & Forensic Dashboard Placeholders", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figures 4.6 through 4.19 provide formal, standardized placeholders and technical descriptions for the SAKSHI user interface and "
        "forensic dashboard components.",
        styles["AcademicBody"]
    ))

    screen_specs = [
        ("Figure 4.6", "Forensic Dashboard Interface", "Displays active inquest cases, recent evidence submissions, statutory deadlines, and system integrity status."),
        ("Figure 4.7", "Case Initiation & FIR Registration Interface", "Captures statutory FIR number, police station jurisdiction, incident timestamp, and assigned Investigating Officer."),
        ("Figure 4.8", "Isolated Case Workspace Partition Interface", "Presents logical case partitions, active evidence collections, stage progression, and assigned officer badges."),
        ("Figure 4.9", "Multi-modal Evidence Registration Dialog", "Enables secure streaming upload of digital exhibits with metadata labels, source descriptions, and seizing officer credentials."),
        ("Figure 4.10", "MIME Sniffing & Binary Magic-Byte Inspection Outcome", "Displays real-time magic-byte verification results, confirming match between declared extension and actual binary header."),
        ("Figure 4.11", "Antivirus Scanning & Quarantine Status Display", "Visualizes ClamAV daemon scan progress, socket status, threat signature verdicts, and quarantine isolation receipts."),
        ("Figure 4.12", "Immutable WORM Commit & Pre-Hash Checksum Receipt", "Displays read-only POSIX file commitment status and generated SHA-256 pre-hash custody receipt."),
        ("Figure 4.13", "Dual Hashing (SHA-256 + SHA3-512) Verification Display", "Presents independent SHA-256 and SHA3-512 digests, pre-hash match confirmation, and bit-rot absence proof."),
        ("Figure 4.14", "WORM Object Lock & Retention Policy Status", "Shows application-layer Object Lock governance, legal hold flags, retention expiration dates, and immutability manifest."),
        ("Figure 4.15", "AES-256-GCM Encryption & Key Isolation Status", "Displays 256-bit authenticated cipher status, CSPRNG nonce hex, AAD metadata binding, and Galois authentication tag."),
        ("Figure 4.16", "FastAPI Interactive OpenAPI / Swagger Documentation", "Presents live interactive REST API documentation, endpoint contracts, schema models, and test execution interface."),
        ("Figure 4.17", "System Health Monitoring Endpoint Output", "Displays JSON health check output showing database connectivity, ClamAV daemon response, and vault storage volume metrics."),
        ("Figure 4.18", "Authorization Denied (HTTP 403) Security Interception", "Visualizes RBAC/ABAC security enforcement blocking unauthorized access attempts across jurisdictional boundaries."),
        ("Figure 4.19", "Case Isolation Error (HTTP 404/403 Boundary)", "Shows strict case isolation failure response preventing cross-case evidence viewing or tampering."),
    ]

    for f_id, title, desc in screen_specs:
        story.append(get_screenshot_placeholder(f"{f_id}: {title}", desc))
        tag_key = f_id.lower().replace("figure ", "fig").replace(".", "_")
        story.append(page_tracker_cls(tag_key))
        story.append(Paragraph(f"<b>{f_id}: {title} Placeholder</b>", styles["FigureCaption"]))
        story.append(Spacer(1, 4))

    # Implementation Status Table
    story.append(Spacer(1, 6))
    story.append(page_tracker_cls("tab4_4"))
    story.append(Paragraph("<b>Table 4.4: Module Implementation Status & Future Development Roadmap</b>", styles["TableCaption"]))

    stat_data = [
        [Paragraph("<b>Phase & Module ID</b>", styles["TableHeader"]), Paragraph("<b>Subsystem Functional Scope</b>", styles["TableHeader"]), Paragraph("<b>Current Status</b>", styles["TableHeader"]), Paragraph("<b>Verified Test Coverage</b>", styles["TableHeader"])],
        [Paragraph("Phase 1: MOD-01", styles["TableCellBold"]), Paragraph("Case Management & Workspace Partitioning", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("32 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 1: MOD-02", styles["TableCellBold"]), Paragraph("Identity Federation & OIDC / JWT Verification", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("28 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 1: MOD-03", styles["TableCellBold"]), Paragraph("Hybrid RBAC / ABAC Authorization Engine", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("30 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 1: MOD-04", styles["TableCellBold"]), Paragraph("Investigation Stage Transition Engine", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("22 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 2: MOD-05", styles["TableCellBold"]), Paragraph("Streaming Evidence Intake & File Ingestion", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("30 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 2: MOD-06", styles["TableCellBold"]), Paragraph("Binary Magic-Byte Inspection & Spoofing Guard", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("26 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 2: MOD-07", styles["TableCellBold"]), Paragraph("Fail-Closed ClamAV Antivirus Daemon Scanning", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("24 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 2: MOD-08", styles["TableCellBold"]), Paragraph("Immutable POSIX WORM Storage Commit", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("28 Automated Tests Passed", styles["TableCell"])],
        [Paragraph("Phase 3: MOD-09", styles["TableCellBold"]), Paragraph("Dual Hashing (SHA-256 + SHA3-512) Verification", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("31 Automated Tests Passed (20 Unit + 11 Int)", styles["TableCell"])],
        [Paragraph("Phase 3: MOD-10", styles["TableCellBold"]), Paragraph("Application-Layer WORM Object Lock Governance", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("47 Automated Tests Passed (32 Unit + 15 Int)", styles["TableCell"])],
        [Paragraph("Phase 3: MOD-11", styles["TableCellBold"]), Paragraph("AES-256-GCM Envelope Encryption at Rest", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"]), Paragraph("31 Automated Tests Passed (20 Unit + 11 Int)", styles["TableCell"])],
        [Paragraph("Phase 3: MOD-12", styles["TableCellBold"]), Paragraph("TLS 1.3 / Mutual TLS Inter-Service Network Security", styles["TableCell"]), Paragraph("PENDING (Next)", styles["TableCell"]), Paragraph("Scheduled for Phase 3 Completion", styles["TableCell"])],
        [Paragraph("Phase 3: MOD-13", styles["TableCellBold"]), Paragraph("Merkle Tree Cryptographic Audit Ledger", styles["TableCell"]), Paragraph("PENDING", styles["TableCell"]), Paragraph("Scheduled for Phase 3 Completion", styles["TableCell"])],
        [Paragraph("Phases 4–17", styles["TableCellBold"]), Paragraph("Downstream Multimodal NLP, Knowledge Graph, EC-MORE", styles["TableCell"]), Paragraph("ROADMAP", styles["TableCell"]), Paragraph("Future Architectural Milestones", styles["TableCell"])],
    ]

    stat_table = Table(stat_data, colWidths=[90, 160, 85, 116])
    stat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(stat_table)

    story.append(PageBreak())
    return story
