"""
Vector Diagrams for SAKSHI Academic Project Report.
Uses ReportLab Drawing, Rect, String, Line, Polygon to produce crisp, print-ready diagrams.
All diagrams fit cleanly within CONTENT_WIDTH = 451.27 pt.
"""
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group, Polygon
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

W_DIAG = 445

C_NAVY_DARK = colors.HexColor("#0A192F")
C_NAVY_MED = colors.HexColor("#0F294A")
C_BLUE = colors.HexColor("#1A365D")
C_BLUE_LIGHT = colors.HexColor("#EBF8FF")
C_SLATE = colors.HexColor("#2B6CB0")
C_BORDER = colors.HexColor("#2D3748")
C_FILL_MAIN = colors.HexColor("#F7FAFC")
C_FILL_ACCENT = colors.HexColor("#EDF2F7")
C_TEXT_DARK = colors.HexColor("#1A202C")
C_TEXT_MUTED = colors.HexColor("#4A5568")
C_GREEN_BG = colors.HexColor("#F0FFF4")
C_GREEN_BORDER = colors.HexColor("#38A169")
C_AMBER_BG = colors.HexColor("#FFFAF0")
C_AMBER_BORDER = colors.HexColor("#DD6B20")


def draw_box(d, x, y, w, h, title, subtitle=None, fill=C_FILL_MAIN, stroke=C_BORDER, stroke_w=1, text_color=C_TEXT_DARK):
    d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=stroke_w, rx=3, ry=3))
    if subtitle:
        d.add(String(x + w / 2, y + h / 2 + 3, title, textAnchor="middle", fontName="Times-Bold", fontSize=8, fillColor=text_color))
        d.add(String(x + w / 2, y + h / 2 - 8, subtitle, textAnchor="middle", fontName="Times-Roman", fontSize=6.5, fillColor=C_TEXT_MUTED))
    else:
        d.add(String(x + w / 2, y + h / 2 - 3, title, textAnchor="middle", fontName="Times-Bold", fontSize=8, fillColor=text_color))


def draw_arrow_down(d, x, y_start, y_end, label=None):
    d.add(Line(x, y_start, x, y_end, strokeColor=C_BORDER, strokeWidth=1))
    d.add(Polygon([x - 3, y_end + 4, x + 3, y_end + 4, x, y_end], fillColor=C_BORDER, strokeColor=C_BORDER))
    if label:
        d.add(String(x + 5, (y_start + y_end) / 2 - 2, label, fontName="Times-Italic", fontSize=6, fillColor=C_TEXT_MUTED))


def draw_arrow_right(d, x_start, x_end, y, label=None):
    d.add(Line(x_start, y, x_end, y, strokeColor=C_BORDER, strokeWidth=1))
    d.add(Polygon([x_end - 4, y - 3, x_end - 4, y + 3, x_end, y], fillColor=C_BORDER, strokeColor=C_BORDER))
    if label:
        d.add(String((x_start + x_end) / 2, y + 4, label, textAnchor="middle", fontName="Times-Italic", fontSize=6, fillColor=C_TEXT_MUTED))


# ==============================================================================
# Chapter 3 Diagrams
# ==============================================================================

def get_system_architecture_diagram():
    """Figure 3.1: Overall SAKSHI Architecture & Multi-Tier Topology."""
    h = 210
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Top: Investigator
    draw_box(d, 120, 175, 205, 26, "INVESTIGATING OFFICER (HUMAN-IN-THE-LOOP)", "Final Legal Decision-Maker & Inquest Authority", fill=C_AMBER_BG, stroke=C_AMBER_BORDER, stroke_w=1.2)
    draw_arrow_down(d, 222, 175, 150)

    # Web & API Gateway
    draw_box(d, 15, 122, 195, 28, "Presentation Tier", "Investigator Web UI / Forensic Dashboard", fill=C_FILL_ACCENT)
    draw_box(d, 235, 122, 195, 28, "Security & Ingestion Tier", "FastAPI / OIDC / RBAC-ABAC / Evidence Intake", fill=C_BLUE_LIGHT, stroke=C_SLATE)
    draw_arrow_right(d, 210, 235, 136, "HTTPS")
    draw_arrow_down(d, 332, 122, 92)

    # Core Security & Ingestion Pipeline
    draw_box(d, 15, 64, 415, 28, "Phase 2 & Phase 3: Cryptographic Evidence Security Pipeline", "MIME Validation -> Fail-Closed Antivirus -> WORM Commit -> Dual Hashing -> Object Lock -> AES-256-GCM", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    draw_arrow_down(d, 222, 64, 38)

    # Analytical / EC-MORE Future Pipeline
    draw_box(d, 15, 10, 415, 28, "Downstream EC-MORE Cognitive Tier (Phases 4-17: Architectural Roadmap)", "Multimodal Extraction | Case Memory | Knowledge Graph | Timeline | Dual Brains | Human Gate", fill=colors.white, stroke=colors.HexColor("#A0AEC0"), stroke_w=0.8)

    return d


def get_ec_more_architecture_diagram():
    """Figure 3.2: EC-MORE Architecture."""
    h = 160
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Left: Intuition Brain
    draw_box(d, 15, 100, 115, 45, "Intuition Brain", "Unconstrained Hypotheses\nExploratory Associations", fill=C_AMBER_BG, stroke=C_AMBER_BORDER)
    # Mid-Left: Information Firewall
    draw_box(d, 155, 100, 115, 45, "Information Firewall", "Filters Speculative Claims\nEnforces Exhibit Provenance", fill=C_FILL_ACCENT, stroke=C_BORDER)
    # Right: Discipline Brain
    draw_box(d, 295, 100, 135, 45, "Discipline Brain", "Evidence-Constrained Verification\nStrict Logical Falsification", fill=C_BLUE_LIGHT, stroke=C_SLATE)

    draw_arrow_right(d, 130, 155, 122, "Hypotheses")
    draw_arrow_right(d, 270, 295, 122, "Filtered")

    draw_arrow_down(d, 362, 100, 55)

    # Evidence Gate
    draw_box(d, 155, 20, 275, 35, "Evidence Gate & Gap Engine", "Only Verified WORM Exhibits Admitted -> Identifies Missing Inquest Facts", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    # Final feedback
    draw_arrow_right(d, 155, 72, 37)
    draw_arrow_down(d, 72, 37, 100)
    d.add(String(75, 65, "Contradiction Alerts", fontName="Times-Italic", fontSize=6, fillColor=C_TEXT_MUTED))

    return d


def get_pipeline_17_diagram():
    """Figure 3.3: 17-Phase Pipeline Flow."""
    h = 130
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    phases_r1 = ["P1: Case", "P2: Ingest", "P3: Security", "P4: Multimodal", "P5: NLP", "P6: Memory"]
    w_box = 62
    for i, name in enumerate(phases_r1):
        x = 15 + i * 70
        is_done = i < 3
        fill = C_GREEN_BG if is_done else colors.white
        stroke = C_GREEN_BORDER if is_done else C_BORDER
        draw_box(d, x, 78, w_box, 32, name, "Complete" if i < 2 else ("In Prog" if i == 2 else "Roadmap"), fill=fill, stroke=stroke)
        if i < 5:
            draw_arrow_right(d, x + w_box, x + 70, 94)

    phases_r2 = ["P7: Graph", "P8: Timeline", "P9: Contradict", "P10: Context", "P11-14: Brains", "P15-17: Output"]
    for i, name in enumerate(phases_r2):
        x = 15 + i * 70
        draw_box(d, x, 18, w_box, 32, name, "Roadmap", fill=colors.white, stroke=colors.HexColor("#CBD5E0"))
        if i < 5:
            draw_arrow_right(d, x + w_box, x + 70, 34)

    # Connecting curve from top to bottom
    d.add(Line(407, 78, 407, 56, strokeColor=C_BORDER, strokeWidth=1))
    d.add(Line(407, 56, 46, 56, strokeColor=C_BORDER, strokeWidth=1))
    draw_arrow_down(d, 46, 56, 50)

    return d


def get_phase1_architecture_diagram():
    """Figure 3.4: Phase 1 Architecture (Case Initiation)."""
    h = 100
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    mods = [
        ("MOD-01", "Case Management", "FIR & Metadata"),
        ("MOD-02", "Identity / OIDC", "JWT & Inquest IO Auth"),
        ("MOD-03", "RBAC / ABAC", "Case Role & Jurisdiction"),
        ("MOD-04", "Stage Engine", "Lifecycle Transitions")
    ]
    w = 95
    for i, (m_id, name, desc) in enumerate(mods):
        x = 15 + i * 107
        draw_box(d, x, 25, w, 50, f"{m_id}: {name}", desc, fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
        if i < 3:
            draw_arrow_right(d, x + w, x + 107, 50)

    return d


def get_phase2_architecture_diagram():
    """Figure 3.5: Phase 2 Architecture (Evidence Ingestion)."""
    h = 100
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    mods = [
        ("MOD-05", "Evidence Intake", "Multi-part Stream"),
        ("MOD-06", "MIME Validation", "Magic-Byte Verification"),
        ("MOD-07", "Antivirus Scan", "Fail-Closed ClamAV"),
        ("MOD-08", "WORM Commit", "Immutable Storage Ref")
    ]
    w = 95
    for i, (m_id, name, desc) in enumerate(mods):
        x = 15 + i * 107
        draw_box(d, x, 25, w, 50, f"{m_id}: {name}", desc, fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
        if i < 3:
            draw_arrow_right(d, x + w, x + 107, 50)

    return d


def get_phase3_architecture_diagram():
    """Figure 3.6: Phase 3 Architecture (Security & Integrity)."""
    h = 110
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    mods = [
        ("MOD-09", "Dual Hashing", "SHA256+SHA3-512", True),
        ("MOD-10", "WORM Object Lock", "Retention & Immutability", True),
        ("MOD-11", "AES-256-GCM", "Ciphertext & AAD", True),
        ("MOD-12", "TLS 1.3 / mTLS", "Network Encryption", False),
        ("MOD-13", "Merkle Ledger", "Cryptographic Audit", False)
    ]
    w = 78
    for i, (m_id, name, desc, is_done) in enumerate(mods):
        x = 12 + i * 86
        fill = C_GREEN_BG if is_done else colors.white
        stroke = C_GREEN_BORDER if is_done else colors.HexColor("#A0AEC0")
        sub = "COMPLETE" if is_done else "PENDING"
        draw_box(d, x, 25, w, 58, f"{m_id}\n{name}", f"{desc}\n[{sub}]", fill=fill, stroke=stroke)
        if i < 4:
            draw_arrow_right(d, x + w, x + 86, 54)

    return d


def get_evidence_security_pipeline_diagram():
    """Figure 3.7: Evidence Security Pipeline (MOD-05 to MOD-11)."""
    h = 120
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    stages = [
        ("1. Intake", "MOD-05"),
        ("2. MIME Check", "MOD-06"),
        ("3. AV Scan", "MOD-07"),
        ("4. WORM Commit", "MOD-08"),
        ("5. Dual Hash", "MOD-09"),
        ("6. Object Lock", "MOD-10"),
        ("7. AES Encrypt", "MOD-11"),
    ]
    w = 54
    for i, (st, mod) in enumerate(stages):
        x = 10 + i * 62
        draw_box(d, x, 35, w, 48, st, mod, fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
        if i < 6:
            draw_arrow_right(d, x + w, x + 62, 59)

    d.add(String(W_DIAG / 2, 14, "Protected Evidence Object: Cryptographically Bound, Locked, and Authenticated", textAnchor="middle", fontName="Times-Bold", fontSize=7.5, fillColor=C_NAVY_MED))
    return d


def get_use_case_diagram():
    """Figure 3.8: UML Use Case Diagram."""
    h = 180
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Actors
    d.add(String(45, 155, "Investigating Officer (IO)", textAnchor="middle", fontName="Times-Bold", fontSize=8, fillColor=C_NAVY_MED))
    d.add(Rect(30, 95, 30, 50, fillColor=C_AMBER_BG, strokeColor=C_AMBER_BORDER))
    d.add(String(45, 120, "IO Actor", textAnchor="middle", fontName="Times-Roman", fontSize=6))

    d.add(String(45, 65, "Supervisory Officer (SO)", textAnchor="middle", fontName="Times-Bold", fontSize=8, fillColor=C_NAVY_MED))
    d.add(Rect(30, 15, 30, 40, fillColor=C_FILL_ACCENT, strokeColor=C_BORDER))
    d.add(String(45, 35, "SO Actor", textAnchor="middle", fontName="Times-Roman", fontSize=6))

    # Boundary Box
    d.add(Rect(110, 10, 320, 160, fillColor=colors.white, strokeColor=C_SLATE, strokeWidth=1, rx=5, ry=5))
    d.add(String(270, 158, "SAKSHI Case Management & Forensics Boundary", textAnchor="middle", fontName="Times-Bold", fontSize=8, fillColor=C_NAVY_MED))

    ucs = [
        (130, 125, "UC-01: Inquest Case Registration"),
        (280, 125, "UC-02: Multi-modal Evidence Ingestion"),
        (130, 85, "UC-03: MIME & Antivirus Verification"),
        (280, 85, "UC-04: Immutable WORM & Object Lock"),
        (130, 45, "UC-05: AES-256-GCM Cryptographic Binding"),
        (280, 45, "UC-06: Forensic Audit Trail & Gap Review"),
    ]
    for x, y, label in ucs:
        d.add(Rect(x, y, 130, 22, fillColor=C_BLUE_LIGHT, strokeColor=C_BORDER, rx=10, ry=10))
        d.add(String(x + 65, y + 7, label, textAnchor="middle", fontName="Times-Roman", fontSize=6.5, fillColor=C_TEXT_DARK))

    # Association lines
    d.add(Line(60, 120, 130, 136, strokeColor=C_BORDER, strokeWidth=0.8))
    d.add(Line(60, 120, 130, 96, strokeColor=C_BORDER, strokeWidth=0.8))
    d.add(Line(60, 120, 130, 56, strokeColor=C_BORDER, strokeWidth=0.8))
    d.add(Line(60, 35, 280, 56, strokeColor=C_BORDER, strokeWidth=0.8))

    return d


def get_dfd_diagram():
    """Figure 3.9: Data Flow Diagram (Level 0 and Level 1)."""
    h = 160
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Level 0 Context
    draw_box(d, 15, 115, 80, 30, "Investigator", "External Entity", fill=C_AMBER_BG)
    draw_box(d, 160, 110, 120, 40, "0.0 SAKSHI System", "Forensic Investigation Platform", fill=C_BLUE_LIGHT, stroke=C_SLATE)
    draw_box(d, 340, 115, 90, 30, "Judicial Court", "Evidence Consumer", fill=C_FILL_ACCENT)

    draw_arrow_right(d, 95, 160, 130, "FIR & Exhibits")
    draw_arrow_right(d, 280, 340, 130, "Inquest Report")

    # Divider
    d.add(Line(15, 95, 430, 95, strokeColor=colors.HexColor("#CBD5E0"), strokeWidth=0.6))
    d.add(String(20, 83, "Level 1 Detailed Decomposition:", fontName="Times-Bold", fontSize=7.5, fillColor=C_NAVY_MED))

    # Level 1 Processes
    draw_box(d, 15, 20, 85, 45, "1.0 Auth & Case", "MOD-01 to MOD-04", fill=C_FILL_MAIN)
    draw_box(d, 120, 20, 85, 45, "2.0 Ingest & Scan", "MOD-05 to MOD-07", fill=C_FILL_MAIN)
    draw_box(d, 225, 20, 95, 45, "3.0 Integrity & Lock", "MOD-08 to MOD-10", fill=C_FILL_MAIN)
    draw_box(d, 340, 20, 90, 45, "4.0 Authenticated Enc", "MOD-11 (AES-GCM)", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)

    draw_arrow_right(d, 100, 120, 42)
    draw_arrow_right(d, 205, 225, 42)
    draw_arrow_right(d, 320, 340, 42)

    return d


def get_class_diagram():
    """Figure 3.10: UML Class Diagram."""
    h = 160
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Case Class
    draw_box(d, 15, 80, 125, 65, "Case", "+ case_id: UUID\n+ fir_number: str\n+ stage: CaseStage\n+ created_at: datetime", fill=C_FILL_MAIN)
    # Evidence Class
    draw_box(d, 175, 80, 135, 65, "Evidence", "+ evidence_id: UUID\n+ case_id: UUID [FK]\n+ sha256_hash: str\n+ sha3_512_hash: str\n+ worm_reference: str", fill=C_FILL_MAIN)
    # Protected Object
    draw_box(d, 175, 10, 135, 55, "EncryptedObject", "+ ciphertext_blob: bytes\n+ nonce: bytes\n+ aad: bytes\n+ key_id: UUID", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    # Investigator Class
    draw_box(d, 335, 80, 95, 65, "Investigator", "+ badge_number: str\n+ role: RoleEnum\n+ jurisdiction: str", fill=C_FILL_MAIN)

    # Relationships
    draw_arrow_right(d, 140, 175, 112, "1 .. *")
    draw_arrow_right(d, 335, 310, 112, "assigned_to")
    draw_arrow_down(d, 242, 80, 65, "1 .. 1")

    return d


def get_sequence_diagram():
    """Figure 3.11: UML Sequence Diagram for Evidence Registration."""
    h = 175
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    lifelines = [
        (45, "IO Client"),
        (135, "API Gateway"),
        (225, "Inspec Engine"),
        (315, "WORM Store"),
        (405, "Crypt Service")
    ]
    for x, label in lifelines:
        d.add(Rect(x - 35, 145, 70, 20, fillColor=C_FILL_ACCENT, strokeColor=C_BORDER))
        d.add(String(x, 152, label, textAnchor="middle", fontName="Times-Bold", fontSize=6.5, fillColor=C_TEXT_DARK))
        d.add(Line(x, 145, x, 15, strokeColor=colors.HexColor("#A0AEC0"), strokeWidth=0.8, strokeDashArray=[2, 2]))

    # Messages
    draw_arrow_right(d, 45, 135, 130, "1: Upload Exhibit")
    draw_arrow_right(d, 135, 225, 115, "2: MIME & AV Scan")
    draw_arrow_right(d, 225, 315, 100, "3: Commit WORM")
    draw_arrow_right(d, 315, 405, 85, "4: Dual Hash & Encrypt")
    draw_arrow_right(d, 405, 135, 65, "5: Return Protected Object")
    draw_arrow_right(d, 135, 45, 50, "6: 201 Created & Custody Proof")

    return d


def get_activity_diagram():
    """Figure 3.12: UML Activity Diagram."""
    h = 160
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    # Initial Node
    d.add(Rect(25, 125, 16, 16, fillColor=C_BORDER, strokeColor=C_BORDER, rx=8, ry=8))
    draw_arrow_right(d, 41, 70, 133)

    # Activities
    draw_box(d, 70, 118, 90, 30, "Receive Inquest File", "Stream byte-chunks")
    draw_arrow_right(d, 160, 195, 133)

    draw_box(d, 195, 118, 90, 30, "Validate Magic Bytes", "Spoofing Prevention")
    draw_arrow_right(d, 285, 320, 133)

    # Decision Node
    d.add(Polygon([335, 143, 345, 133, 335, 123, 325, 133], fillColor=C_AMBER_BG, strokeColor=C_AMBER_BORDER))
    draw_arrow_down(d, 335, 123, 85, "Valid")
    draw_arrow_right(d, 345, 385, 133, "Spoofed")
    draw_box(d, 385, 118, 48, 30, "Reject", "400 Error", fill=colors.HexColor("#FED7D7"))

    # Next steps
    draw_box(d, 285, 55, 100, 30, "ClamAV Scan & WORM", "Immutable Commit")
    draw_arrow_right(d, 285, 235, 70)

    draw_box(d, 135, 55, 100, 30, "Dual Hash & AES Encrypt", "Generate Custody Receipt", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    draw_arrow_right(d, 135, 80, 70)

    # Final Node
    d.add(Rect(60, 62, 16, 16, fillColor=colors.white, strokeColor=C_BORDER, rx=8, ry=8))
    d.add(Rect(63, 65, 10, 10, fillColor=C_BORDER, strokeColor=C_BORDER, rx=5, ry=5))

    return d


def get_component_diagram():
    """Figure 3.13: UML Component Diagram."""
    h = 140
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    components = [
        (15, 75, 125, 45, "<<component>>\nCaseManagement", "MOD-01 to MOD-04"),
        (160, 75, 125, 45, "<<component>>\nEvidencePipeline", "MOD-05 to MOD-08"),
        (305, 75, 125, 45, "<<component>>\nSecurityIntegrity", "MOD-09 to MOD-11"),
        (85, 15, 125, 45, "<<component>>\nStorageWORM", "Immutable Filesystem"),
        (235, 15, 125, 45, "<<component>>\nCryptoEngine", "AES-GCM / SHA3-512")
    ]
    for x, y, w, h_box, title, sub in components:
        draw_box(d, x, y, w, h_box, title, sub, fill=C_BLUE_LIGHT, stroke=C_BORDER)

    draw_arrow_right(d, 140, 160, 97)
    draw_arrow_right(d, 285, 305, 97)
    draw_arrow_down(d, 222, 75, 60)
    draw_arrow_down(d, 367, 75, 60)

    return d


def get_deployment_diagram():
    """Figure 3.14: UML Deployment Diagram."""
    h = 140
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    nodes = [
        (15, 20, 120, 95, "<<device>>\nInvestigator Workstation", "Forensic Browser / Client\nTLS 1.3 Endpoint", C_AMBER_BG),
        (160, 20, 130, 95, "<<execution env>>\nFastAPI Application Server", "Python 3.12 / Uvicorn\nSQLAlchemy / Pydantic\nClamAV Daemon", C_BLUE_LIGHT),
        (315, 20, 115, 95, "<<storage server>>\nWORM & Vault Storage", "WORM Read-Only Mount\nAES-256-GCM Vault\nSQLite/Postgres DB", C_GREEN_BG)
    ]
    for x, y, w, h_box, title, sub, fill in nodes:
        d.add(Rect(x, y, w, h_box, fillColor=fill, strokeColor=C_BORDER, strokeWidth=1, rx=3, ry=3))
        d.add(String(x + w / 2, y + h_box - 18, title, textAnchor="middle", fontName="Times-Bold", fontSize=7, fillColor=C_NAVY_MED))
        d.add(String(x + w / 2, y + 25, sub, textAnchor="middle", fontName="Times-Roman", fontSize=6.5, fillColor=C_TEXT_MUTED))

    draw_arrow_right(d, 135, 160, 67, "HTTPS:8000")
    draw_arrow_right(d, 290, 315, 67, "POSIX/WORM")

    return d


# ==============================================================================
# Chapter 4 Diagrams
# ==============================================================================

def get_backend_architecture_diagram():
    """Figure 4.1: Backend Architecture."""
    h = 135
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    layers = [
        (15, 85, 415, 30, "API Router & Middleware Tier", "FastAPI APIRouter | Bearer JWT Authenticator | CORS & Error Interceptors", C_FILL_ACCENT),
        (15, 45, 415, 30, "Service Orchestration Layer", "CaseService | EvidenceService | IntegrityService | ObjectLockService | EncryptionService", C_BLUE_LIGHT),
        (15, 5, 415, 30, "Data Access & Physical Storage Layer", "SQLAlchemy ORM Repositories | WORM POSIX Driver | Encrypted Vault Storage", C_GREEN_BG)
    ]
    for x, y, w, h_box, title, sub, fill in layers:
        draw_box(d, x, y, w, h_box, title, sub, fill=fill, stroke=C_BORDER)

    draw_arrow_down(d, 222, 85, 75)
    draw_arrow_down(d, 222, 45, 35)

    return d


def get_evidence_processing_workflow_diagram():
    """Figure 4.2: Evidence Processing Workflow."""
    h = 105
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    steps = ["1. Ingest", "2. Sniff", "3. ClamAV", "4. WORM", "5. DualHash", "6. Lock", "7. Encrypt"]
    w = 52
    for i, st in enumerate(steps):
        x = 12 + i * 61
        draw_box(d, x, 30, w, 45, st, f"Step {i+1}", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
        if i < 6:
            draw_arrow_right(d, x + w, x + 61, 52)

    d.add(String(W_DIAG / 2, 12, "End-to-End Strict Pre-Hash and Post-Cipher Validation Sequence", textAnchor="middle", fontName="Times-Italic", fontSize=7, fillColor=C_TEXT_MUTED))
    return d


def get_dual_hashing_workflow_diagram():
    """Figure 4.3: Dual Hashing Workflow (MOD-09)."""
    h = 110
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    draw_box(d, 15, 35, 95, 45, "WORM File Exhibit", "Immutable Source Bytes", fill=C_FILL_MAIN)
    draw_arrow_right(d, 110, 150, 68)
    draw_arrow_right(d, 110, 150, 48)

    draw_box(d, 150, 60, 125, 35, "SHA-256 Digest", "256-bit Collision Resistant", fill=C_BLUE_LIGHT)
    draw_box(d, 150, 15, 125, 35, "SHA3-512 Digest", "512-bit Keccak Sponge", fill=C_BLUE_LIGHT)

    draw_arrow_right(d, 275, 315, 77)
    draw_arrow_right(d, 275, 315, 32)

    draw_box(d, 315, 25, 115, 60, "Dual-Hash Gate", "Compares SHA-256 vs Pre-Hash\nBinds Dual Cryptographic Proof", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    return d


def get_aes_gcm_workflow_diagram():
    """Figure 4.4: AES-256-GCM Workflow (MOD-11)."""
    h = 115
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    draw_box(d, 15, 65, 105, 35, "Plaintext Bytes", "WORM Locked Exhibit", fill=C_FILL_MAIN)
    draw_box(d, 15, 15, 105, 35, "AAD Metadata", "case_id + dual_hashes", fill=C_AMBER_BG)

    draw_arrow_right(d, 120, 160, 82)
    draw_arrow_right(d, 120, 160, 32)

    draw_box(d, 160, 25, 120, 65, "AES-256-GCM Engine", "96-bit CSPRNG Nonce\n256-bit Case-Isolated Key\nGalois Field Authentication", fill=C_BLUE_LIGHT, stroke=C_SLATE)

    draw_arrow_right(d, 280, 320, 57)
    draw_box(d, 320, 25, 110, 65, "Encrypted Vault Object", "Ciphertext Blob\n128-bit Auth Tag\nUnmodified Nonce Ref", fill=C_GREEN_BG, stroke=C_GREEN_BORDER)
    return d


def get_auth_flow_diagram():
    """Figure 4.5: Authentication and Authorization Flow."""
    h = 110
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    steps = [
        ("IO Login", "OIDC Provider"),
        ("JWT Validation", "MOD-02"),
        ("RBAC Policy", "MOD-03 Role Gate"),
        ("ABAC Rules", "MOD-03 Jurisdiction"),
        ("Scoped Context", "Case Session")
    ]
    w = 75
    for i, (st, sub) in enumerate(steps):
        x = 12 + i * 86
        draw_box(d, x, 30, w, 50, st, sub, fill=C_FILL_ACCENT, stroke=C_BORDER)
        if i < 4:
            draw_arrow_right(d, x + w, x + 86, 55)

    return d


# ==============================================================================
# Chapter 5 Diagrams
# ==============================================================================

def get_testing_workflow_diagram():
    """Figure 5.1: Testing & Verification Workflow."""
    h = 100
    d = Drawing(W_DIAG, h)
    d.add(Rect(0, 0, W_DIAG, h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.8, rx=4, ry=4))

    stages = [
        ("Unit Tests", "Isolated Services"),
        ("Integration Tests", "End-to-End Pipeline"),
        ("Security Scans", "Tamper & Path Tests"),
        ("Regression Matrix", "298 Tests Passed (100%)")
    ]
    w = 95
    for i, (st, sub) in enumerate(stages):
        x = 15 + i * 107
        fill = C_GREEN_BG if i == 3 else C_FILL_MAIN
        stroke = C_GREEN_BORDER if i == 3 else C_BORDER
        draw_box(d, x, 25, w, 50, st, sub, fill=fill, stroke=stroke)
        if i < 3:
            draw_arrow_right(d, x + w, x + 107, 50)

    return d


# ==============================================================================
# Standardized Screenshot Placeholder Generator
# ==============================================================================

def get_screenshot_placeholder(fig_title, explanation):
    """Generates an academic, standardized placeholder for system screenshots."""
    t_data = [
        [Paragraph(f"<b>[ SCREENSHOT PLACEHOLDER ]</b><br/><b>{fig_title}</b>", ParagraphStyle(
            name="SPTitle", fontName="Times-Bold", fontSize=9, leading=12, alignment=1, textColor=C_NAVY_MED
        ))],
        [Paragraph(f"<i>{explanation}</i>", ParagraphStyle(
            name="SPExp", fontName="Times-Italic", fontSize=7.5, leading=10.5, alignment=1, textColor=C_TEXT_MUTED
        ))]
    ]
    t = Table(t_data, colWidths=[W_DIAG])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E0")),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor("#E2E8F0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t
