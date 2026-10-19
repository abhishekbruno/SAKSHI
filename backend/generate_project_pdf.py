"""
Script to generate a comprehensive, professional PDF technical report for SAKSHI.
Uses ReportLab to format architecture, modules, models, security policies, and test results.
"""
import os
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Skip headers/footers on page 1 (cover page)
        if self._pageNumber > 1:
            # Header
            self.drawString(54, 750, "SAKSHI — Explainable AI Investigation Companion (EC-MORE)")
            self.drawRightString(558, 750, "System Architecture & Verification Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

            # Footer
            self.line(54, 45, 558, 45)
            self.drawString(54, 32, "Confidential — Forensic Evidence Management Platform")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(558, 32, page_text)

        self.restoreState()


def create_project_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#0F172A")    # Slate 900
    accent_color = colors.HexColor("#0284C7")     # Sky 600
    text_color = colors.HexColor("#334155")       # Slate 700
    subtext_color = colors.HexColor("#64748B")    # Slate 500
    code_bg = colors.HexColor("#F8FAFC")          # Slate 50

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=primary_color,
        spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=accent_color,
        spaceAfter=15,
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=accent_color,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=text_color,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    )
    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=text_color,
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=primary_color,
    )

    story = []

    # ─── COVER / HEADER BANNER ──────────────────────────────────────────────
    story.append(Spacer(1, 15))
    story.append(Paragraph("SAKSHI PLATFORM", subtitle_style))
    story.append(Paragraph("System Architecture & Verification Report", title_style))
    story.append(Paragraph(
        "<b>Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)</b><br/>"
        "Explainable AI Investigation Companion for Unnatural Death Investigations",
        body_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=accent_color, spaceBefore=10, spaceAfter=15))

    # Meta Table
    meta_data = [
        [
            Paragraph("<b>Author / Project:</b> SAKSHI Core Engineering Team", table_cell),
            Paragraph(f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", table_cell)
        ],
        [
            Paragraph("<b>Platform Status:</b> Phase 1 (100%) & Phase 2 (MOD-05/06 Complete)", table_cell),
            Paragraph("<b>Test Suite:</b> 132 Tests Passing (0 Failures)", table_cell)
        ],
        [
            Paragraph("<b>Framework:</b> FastAPI + SQLAlchemy + SQLite/PostgreSQL", table_cell),
            Paragraph("<b>Security Standard:</b> OIDC + Zero-Trust RBAC/ABAC", table_cell)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    # ─── 1. EXECUTIVE SUMMARY & ARCHITECTURE ────────────────────────────────
    story.append(Paragraph("1. Executive Summary & Paradigm", h1_style))
    story.append(Paragraph(
        "SAKSHI is an explainable AI companion built to assist investigating officers (IOs) and supervisory "
        "authorities during complex unnatural death investigations. Under the <b>Evidence-Constrained Modus Operandi "
        "Reconstruction (EC-MORE)</b> paradigm, the platform enforces strict evidentiary grounding: no hypothesis or "
        "timeline can be constructed without verifiable, authenticated, and cryptographically anchored evidence.",
        body_style
    ))
    story.append(Paragraph(
        "The architecture establishes an immutable multi-phase pipeline where administrative governance, evidence ingestion, "
        "cryptographic security, and forensic reasoning remain cleanly decoupled.",
        body_style
    ))

    # High-level Pipeline Table
    pipe_data = [
        [Paragraph("Phase", table_cell_bold), Paragraph("Focus", table_cell_bold), Paragraph("Modules", table_cell_bold), Paragraph("Status", table_cell_bold)],
        [Paragraph("Phase 1", table_cell_bold), Paragraph("Case Initiation & Governance", table_cell), Paragraph("MOD-01 Case Management<br/>MOD-02 Identity / OIDC<br/>MOD-03 RBAC / ABAC<br/>MOD-04 Stage Engine", table_cell), Paragraph("<b>100% COMPLETE</b><br/>(92 tests)", table_cell)],
        [Paragraph("Phase 2", table_cell_bold), Paragraph("Evidence Ingestion", table_cell), Paragraph("MOD-05 Evidence Intake<br/>MOD-06 MIME / Signature Validation<br/>MOD-07 Antivirus Scan<br/>MOD-08 WORM Commit + Checksum", table_cell), Paragraph("<b>ACTIVE</b><br/>MOD-05: 100%<br/>MOD-06: 100%<br/>MOD-07/08: Next", table_cell)],
        [Paragraph("Phase 3", table_cell_bold), Paragraph("Security & Integrity", table_cell), Paragraph("Dual Hashing (SHA-256 + SHA3-512)<br/>WORM Object Lock & Merkle Audit Trail", table_cell), Paragraph("Queued", table_cell)],
    ]
    t_pipe = Table(pipe_data, colWidths=[60, 130, 204, 110])
    t_pipe.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_pipe)
    story.append(Spacer(1, 15))

    # ─── 2. PHASE 1: CASE INITIATION ────────────────────────────────────────
    story.append(Paragraph("2. Phase 1 — Case Initiation & Governance", h1_style))
    story.append(Paragraph(
        "Phase 1 anchors administrative accountability, identity verification, access authorization, and state machine "
        "lifecycle progression before any evidence can enter the system.",
        body_style
    ))

    mod_phase1_data = [
        [
            Paragraph("Module", table_cell_bold),
            Paragraph("Core Responsibilities", table_cell_bold),
            Paragraph("Security & Architectural Invariants", table_cell_bold)
        ],
        [
            Paragraph("<b>MOD-01</b><br/>Case Management", table_cell),
            Paragraph("• Mint collision-resistant Case IDs: <code>SAKSHI-CASE-YYYY-HEX8</code><br/>• Provision isolated Case Workspace boundaries<br/>• Bind FIR metadata & assigned Investigating Officer<br/>• Export Phase 2 Integration Contract", table_cell),
            Paragraph("• Duplicate FIR prevention across station jurisdictions<br/>• Relational ID isolation (internal UUID separated from Case ID)<br/>• Immutable workspace directory anchoring", table_cell)
        ],
        [
            Paragraph("<b>MOD-02</b><br/>Identity / OIDC", table_cell),
            Paragraph("• Centralized authentication boundary<br/>• JWT Bearer token validation (signature, issuer, expiry, audience)<br/>• Extraction of verified <code>AuthenticatedInvestigator</code>", table_cell),
            Paragraph("• Zero credential storage in database<br/>• Rejection of forged client identity claims<br/>• Dual development mock & production OIDC modes", table_cell)
        ],
        [
            Paragraph("<b>MOD-03</b><br/>RBAC / ABAC", table_cell),
            Paragraph("• Dual role & attribute policy evaluation<br/>• Dynamic permission registry (case:* and evidence:*)<br/>• Station/jurisdiction match checks<br/>• Explainable <code>AuthorizationDecision</code> with audit log", table_cell),
            Paragraph("• <b>DEFAULT DENY</b> architecture<br/>• Client-supplied roles never trusted<br/>• Supervisory privilege escalation isolation", table_cell)
        ],
        [
            Paragraph("<b>MOD-04</b><br/>Stage Engine", table_cell),
            Paragraph("• Deterministic case lifecycle state machine<br/>• Validates transitions: INITIALIZED -> EVIDENCE_INGESTION -> ...<br/>• Governs investigative feedback loops and closure", table_cell),
            Paragraph("• Anti-skipping protection (no jumping to CLOSED/ANALYSIS)<br/>• Supervisory-only closure and reopening checks<br/>• Ingestion gate control", table_cell)
        ],
    ]
    t_mod1 = Table(mod_phase1_data, colWidths=[90, 224, 190])
    t_mod1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_mod1)
    story.append(Spacer(1, 10))

    story.append(PageBreak())

    # ─── 3. PHASE 2: EVIDENCE INGESTION ─────────────────────────────────────
    story.append(Paragraph("3. Phase 2 — Evidence Ingestion Pipeline", h1_style))
    story.append(Paragraph(
        "Phase 2 transforms raw multi-modal artifacts (autopsy reports, crime scene photos, 112 emergency calls, CDR spreadsheets, "
        "and digital forensics dumps) into registered, verified, and secured evidence objects.",
        body_style
    ))

    # Phase 2 Diagram Representation
    story.append(Paragraph("<b>Phase 2 Modular Pipeline Flow:</b>", h2_style))
    pipe_steps = [
        [
            Paragraph("<b>MOD-05: Evidence Intake</b><br/>• Checks Stage Engine (EVIDENCE_INGESTION)<br/>• Generates Evidence ID (SAKSHI-EVID-...)<br/>• Sanitizes filenames (anti-traversal)<br/>• Stages file in <code>{workspace}/raw/</code><br/>• Output: <code>RegisteredEvidenceObject</code>", table_cell),
            Paragraph("➔", table_cell_bold),
            Paragraph("<b>MOD-06: MIME / Signature</b><br/>• Reads bounded 8KB header<br/>• Matches magic bytes vs declared type<br/>• Rejects disguised executables/scripts<br/>• Enforces 16-type allowlist<br/>• Output: <code>ValidatedEvidenceObject</code>", table_cell),
            Paragraph("➔", table_cell_bold),
            Paragraph("<b>MOD-07 & MOD-08 (Next)</b><br/>• MOD-07: Antivirus scan<br/>• MOD-08: WORM commit & pre-hash<br/>• Secure handoff to Phase 3", table_cell)
        ]
    ]
    t_steps = Table(pipe_steps, colWidths=[150, 15, 175, 15, 149])
    t_steps.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#E0F2FE")),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#DCFCE7")),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor("#F1F5F9")),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (3, 0), (3, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
    ]))
    story.append(t_steps)
    story.append(Spacer(1, 12))

    # MOD-05 & MOD-06 Detailed Breakdown
    story.append(Paragraph("MOD-05: Evidence Intake Specification", h2_style))
    story.append(Paragraph(
        "MOD-05 establishes forensic chain-of-custody at the moment of intake. It guarantees that files are associated with a valid Case ID, "
        "stored exclusively within the provisioned case workspace, and tied to the submitting officer. Filename sanitization strips null bytes, "
        "directory traversal delimiters (<code>../</code>, <code>..\\</code>), and filesystem escape sequences.",
        body_style
    ))

    story.append(Paragraph("MOD-06: MIME / File Signature Validation Specification", h2_style))
    story.append(Paragraph(
        "MOD-06 enforces strict binary signature verification. It rejects the trust of client-provided file extensions and MIME headers. "
        "Key protections include:",
        body_style
    ))
    story.append(Paragraph("• <b>Bounded 8KB Reads:</b> Inspects initial binary header bytes without loading large multi-gigabyte files into RAM.", bullet_style))
    story.append(Paragraph("• <b>Executable Trapping:</b> Detects Windows PE (<code>MZ</code>), Linux ELF (<code>\\x7fELF</code>), Mach-O binaries, Java classes, and shell scripts (<code>#!/bin/sh</code>). Disguised executables are instantly REJECTED.", bullet_style))
    story.append(Paragraph("• <b>MIME Allowlist:</b> Enforces approved forensic formats across PDF, JPEG, PNG, TIFF, WEBP, WAV, MP3, OGG, FLAC, CSV, XLS, XLSX, ZIP, GZIP, and JSON.", bullet_style))
    story.append(Paragraph("• <b>Polyglot / Ambiguity Handling:</b> Reject files with conflicting or ambiguous binary signatures.", bullet_style))
    story.append(Spacer(1, 10))

    # ─── 4. DATA MODELS & ENTITY CONTRACTS ──────────────────────────────────
    story.append(Paragraph("4. Data Models & Entity Contracts", h1_style))

    story.append(Paragraph("Database Schema (`cases` and `evidence` tables)", h2_style))
    schema_code = (
        "cases table:\n"
        "  - id (UUID PK)                   - case_id (Canonical Unique String, Indexed)\n"
        "  - title (String)                 - fir_metadata (JSON structured metadata)\n"
        "  - assigned_io_id (String)        - lifecycle_stage (INITIALIZED -> EVIDENCE_INGESTION...)\n"
        "  - status (ACTIVE/CLOSED)         - case_workspace_path (Filesystem boundary)\n"
        "  - created_by, created_at, updated_at\n\n"
        "evidence table:\n"
        "  - id (UUID PK)                   - evidence_id (SAKSHI-EVID-YYYY-HEX8, Unique)\n"
        "  - case_id (FK -> cases.case_id) - original_file_name, stored_file_name\n"
        "  - evidence_category (Enum)       - declared_mime_type (Client claimed)\n"
        "  - detected_mime_type (Verified)  - detected_format (PDF, JPEG, WAV, CSV...)\n"
        "  - file_size_bytes (Integer)      - status (REGISTERED_INTAKE, VALIDATED, REJECTED)\n"
        "  - raw_storage_path (File path)   - submitting_investigator_id (Audit anchor)\n"
        "  - validation_reason (Text)       - collection_location, collection_datetime"
    )
    t_schema = Table([[Paragraph(schema_code.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style)]], colWidths=[504])
    t_schema.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_schema)
    story.append(Spacer(1, 10))

    story.append(PageBreak())

    # ─── 5. SECURITY, PERMISSIONS & ISOLATION ───────────────────────────────
    story.append(Paragraph("5. Security, Access Controls & Case Isolation", h1_style))
    story.append(Paragraph(
        "SAKSHI enforces defense-in-depth across authentication, authorization, and workspace boundary confinement:",
        body_style
    ))

    sec_data = [
        [Paragraph("Security Layer", table_cell_bold), Paragraph("Policy Implementation", table_cell_bold), Paragraph("Forensic Safeguard", table_cell_bold)],
        [
            Paragraph("Authentication (MOD-02)", table_cell),
            Paragraph("Stateless JWT OIDC Tokens signed by trusted IdP.<br/>Extracts <code>subject_id</code>, roles, police station.", table_cell),
            Paragraph("Prevents forged officer identities. Token expiration strictly enforced.", table_cell)
        ],
        [
            Paragraph("Authorization (MOD-03)", table_cell),
            Paragraph("RBAC + ABAC matrix.<br/>Permissions: <code>case:*</code>, <code>evidence:create</code>, <code>evidence:read</code>, <code>evidence:validate</code>.", table_cell),
            Paragraph("Default Deny. An officer from Station A cannot access or intake evidence into Station B cases without supervisory clearance.", table_cell)
        ],
        [
            Paragraph("Workspace Isolation", table_cell),
            Paragraph("Resolved canonical paths verified against <code>case_workspace_path</code>.", table_cell),
            Paragraph("Blocks path traversal (<code>../../</code>) and prevents cross-case tampering.", table_cell)
        ],
        [
            Paragraph("Audit Ledger", table_cell),
            Paragraph("Structured JSON events logged for all transitions, intake, and validation verdicts via <code>AuditIntegrationService</code>.", table_cell),
            Paragraph("Prepares append-only cryptographic Merkle audit trail for court admissibility.", table_cell)
        ],
    ]
    t_sec = Table(sec_data, colWidths=[110, 204, 190])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_sec)
    story.append(Spacer(1, 15))

    # ─── 6. TEST VERIFICATION & REGRESSION SUMMARY ───────────────────────────
    story.append(Paragraph("6. Quality Assurance & Test Verification", h1_style))
    story.append(Paragraph(
        "The SAKSHI platform maintains 100% automated test coverage across unit and integration tiers. "
        "All previous Phase 1 tests remain non-regressed alongside new Phase 2 modules.",
        body_style
    ))

    test_data = [
        [Paragraph("Module", table_cell_bold), Paragraph("Component", table_cell_bold), Paragraph("Tests", table_cell_bold), Paragraph("Pass Rate", table_cell_bold)],
        [Paragraph("MOD-01", table_cell), Paragraph("Case Management & Workspace Provisioning", table_cell), Paragraph("16", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("MOD-02", table_cell), Paragraph("Identity / OIDC Authentication Boundary", table_cell), Paragraph("33", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("MOD-03", table_cell), Paragraph("RBAC / ABAC Authorization Engine", table_cell), Paragraph("25", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("MOD-04", table_cell), Paragraph("Stage Engine Lifecycle Governance", table_cell), Paragraph("18", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("MOD-05", table_cell), Paragraph("Evidence Intake & Staging Service", table_cell), Paragraph("15", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("MOD-06", table_cell), Paragraph("MIME / File Signature Validation Service", table_cell), Paragraph("25", table_cell), Paragraph("100% (Passed)", table_cell)],
        [Paragraph("<b>TOTAL</b>", table_cell_bold), Paragraph("<b>Entire SAKSHI Test Suite</b>", table_cell_bold), Paragraph("<b>132</b>", table_cell_bold), Paragraph("<b>100% (0 Failures)</b>", table_cell_bold)],
    ]
    t_test = Table(test_data, colWidths=[70, 234, 70, 130])
    t_test.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#DCFCE7")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_test)
    story.append(Spacer(1, 15))

    # ─── 7. ROADMAP & NEXT MODULES ──────────────────────────────────────────
    story.append(Paragraph("7. Phase 2 Roadmap & Next Steps", h1_style))
    story.append(Paragraph(
        "With MOD-05 (Intake) and MOD-06 (MIME Validation) 100% verified, the next implementation milestones in Phase 2 are:",
        body_style
    ))
    story.append(Paragraph("• <b>MOD-07: Antivirus Scan:</b> Consumes <code>ValidatedEvidenceObject</code> to scan payloads for viruses, Trojans, and malware without executing files.", bullet_style))
    story.append(Paragraph("• <b>MOD-08: WORM Commit + Checksum:</b> Pre-hashes evidence payloads with SHA-256 and stages them for immutable Write-Once-Read-Many (WORM) storage.", bullet_style))
    story.append(Paragraph("• <b>Phase 3: Security & Integrity Handoff:</b> Dual hashing (SHA-256 + SHA3-512), AWS S3 Object Lock compliance, and append-only Merkle tree audit trails.", bullet_style))

    subtext_style = ParagraphStyle(
        'Subtext_Custom',
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=subtext_color,
        alignment=1,  # Center
    )

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceBefore=5, spaceAfter=10))
    story.append(Paragraph("<i>Report generated automatically by SAKSHI Platform Documentation Engine.</i>", subtext_style))

    # Build PDF with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {output_path}")


if __name__ == "__main__":
    out_pdf = r"c:\main project\SAKSHI_Architecture_and_Implementation_Report.pdf"
    create_project_pdf(out_pdf)
