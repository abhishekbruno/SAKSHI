"""
Chapter 3: System Analysis and Design for SAKSHI Academic Project Report.
Target length: 10–12 pages.
Covers 19 detailed sections:
3.1 Existing System
3.2 Existing System Architecture
3.3 Problems in Existing System
3.4 Proposed System
3.5 Proposed System Architecture
3.6 Functional Requirements Specification (Table 3.1)
3.7 Non-Functional Requirements Specification (Table 3.2)
3.8 System Actors and Personas
3.9 Overall SAKSHI Architecture Diagram (Figures 3.1 & 3.2)
3.10 SAKSHI 17-Phase Comprehensive Pipeline (Table 3.3 & Figure 3.3)
3.11 Phase 1 Architecture (Table 3.4 & Figure 3.4)
3.12 Phase 2 Architecture (Table 3.5 & Figure 3.5)
3.13 Phase 3 Architecture (Table 3.6 & Figure 3.6)
3.14 Security Architecture & Defense-in-Depth (Figure 3.7)
3.15 Data Flow Modeling (Figure 3.9)
3.16 UML Use Case Model & Formal Specifications (Figure 3.8)
3.17 UML Structural and Behavioral Models (Figures 3.10, 3.11, 3.12, 3.13, 3.14)
3.18 Database Architecture and Storage Design
3.19 Human-in-the-Loop Governance Architecture
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors
from report_diagrams import (
    get_system_architecture_diagram,
    get_ec_more_architecture_diagram,
    get_pipeline_17_diagram,
    get_phase1_architecture_diagram,
    get_phase2_architecture_diagram,
    get_phase3_architecture_diagram,
    get_evidence_security_pipeline_diagram,
    get_use_case_diagram,
    get_dfd_diagram,
    get_class_diagram,
    get_sequence_diagram,
    get_activity_diagram,
    get_component_diagram,
    get_deployment_diagram,
)

W_CONTENT = 451.27


def get_chapter3(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ch3"))
    story.append(Paragraph("CHAPTER 3", styles["ChapterHeading"]))
    story.append(Paragraph("SYSTEM ANALYSIS AND DESIGN", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # 3.1 Existing System
    story.append(page_tracker_cls("sec3_1"))
    story.append(Paragraph("3.1 Existing System", styles["SectionHeading"]))
    story.append(Paragraph(
        "Contemporary unnatural death inquiries across police departments and forensic jurisdictions rely primarily on a hybrid "
        "operational model consisting of physical paper case dockets (Case Diaries) augmented by standalone, uncoordinated digital "
        "forensic utilities. When an unnatural death is reported under statutory inquest provisions (such as BNSS Section 194 or CrPC Section "
        "174), the initial panchnama, First Information Report (FIR), and witness depositions are manually handwritten or typed into "
        "general incident tracking software. As the investigation unfolds, digital exhibits—including Call Detail Record (CDR) spreadsheets, "
        "mobile extraction reports, CCTV video files, digital autopsy photographs, and chemical analysis certificates—are collected on "
        "removable optical media (CDs/DVDs), portable USB hard drives, or local desktop workstation folders.",
        styles["AcademicBody"]
    ))

    # 3.2 Existing System Architecture
    story.append(page_tracker_cls("sec3_2"))
    story.append(Paragraph("3.2 Existing System Architecture", styles["SectionHeading"]))
    story.append(Paragraph(
        "The architecture of the conventional investigation workflow is fundamentally fragmented and decentralized. There is no central "
        "computational repository that enforces cryptographic provenance across the case lifecycle. Digital evidence is acquired using "
        "proprietary vendor tools (such as Cellebrite UFED for mobile devices or EnCase for computer disk clones), and the resulting "
        "extracted files are stored in unstructured directories on local file servers. Access control is governed solely by basic operating "
        "system logins, lacking granular case-level role segregation, attribute-based jurisdictional gating, or immutable audit trails. "
        "Furthermore, communication between forensic laboratories and the investigating police station relies on physical transit of "
        "sealed dockets or unencrypted email attachments, creating significant vulnerabilities in the chain of custody.",
        styles["AcademicBody"]
    ))

    # 3.3 Problems in Existing System
    story.append(page_tracker_cls("sec3_3"))
    story.append(Paragraph("3.3 Problems in Existing System", styles["SectionHeading"]))
    story.append(Paragraph(
        "The existing operational architecture suffers from severe structural and technical deficiencies:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "1. <b>Extreme Cognitive Overload & Manual Synthesis:</b> The Investigating Officer is required to manually inspect hundreds of "
        "pages of depositions, thousands of rows of telecommunication logs, and complex medical reports. Reconciling conflicting timestamps "
        "or identifying subtle narrative contradictions relies entirely on human memory, leading to critical investigative oversights.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "2. <b>Vulnerability to Data Tampering and Bit-Rot:</b> Files stored on standard NTFS or ext4 filesystems can be accidentally "
        "modified, renamed, or deleted by authorized workstation users. Without continuous cryptographic hash verification and write-once "
        "hardware or software locking, the defense can easily challenge the digital chain of custody during trial.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "3. <b>Absence of Automated Gap Detection:</b> Conventional systems provide no active assistance regarding procedural omissions. "
        "If an investigator omits to seize the victim's mobile tower logs or fails to submit viscera samples within the statutory window, "
        "the deficiency remains undetected until pointed out by defense counsel or supervisory scrutiny.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "4. <b>Lack of Cross-Modal Integration:</b> Textual statements, cellular location pings, and autopsy findings remain in isolated "
        "formats, preventing automated cross-modal validation (e.g., verifying if a suspect's claimed alibi location matches their "
        "cellular tower azimuth at the estimated time of death).",
        styles["BulletText"]
    ))

    # 3.4 Proposed System
    story.append(page_tracker_cls("sec3_4"))
    story.append(Paragraph("3.4 Proposed System", styles["SectionHeading"]))
    story.append(Paragraph(
        "The proposed system, <b>SAKSHI</b>, is an explainable AI investigation companion designed specifically for unnatural death "
        "inquiries. SAKSHI replaces vulnerable, disconnected workflows with a unified, <b>evidence-first architecture</b> governed by the "
        "<b>Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)</b> paradigm. SAKSHI introduces multi-tier cryptographic integrity, "
        "fail-closed malware inspection, immutable WORM commitment, independent dual hashing, application-layer Object Locking, and "
        "case-isolated AES-256-GCM authenticated encryption at rest.",
        styles["AcademicBody"]
    ))

    # 3.5 Proposed System Architecture
    story.append(page_tracker_cls("sec3_5"))
    story.append(Paragraph("3.5 Proposed System Architecture", styles["SectionHeading"]))
    story.append(Paragraph(
        "The proposed architecture establishes a layered defense-in-depth model that cleanly separates evidence ingestion, cryptographic "
        "custody, structured case memory, adversarial dual-brain reasoning, and human oversight. Crucially, the architecture incorporates "
        "a strict <b>Evidence Gate</b>: no inference, timeline event, or relation can be synthesized by the computational engines unless it is "
        "mathematically anchored in a verified, locked exhibit.",
        styles["AcademicBody"]
    ))

    # 3.6 Functional Requirements Specification
    story.append(page_tracker_cls("sec3_6"))
    story.append(Paragraph("3.6 Functional Requirements Specification", styles["SectionHeading"]))
    story.append(Paragraph(
        "Table 3.1 specifies the 12 primary Functional Requirements (FR-01 to FR-12) governing the SAKSHI platform.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab3_1"))
    story.append(Paragraph("<b>Table 3.1: Formal Functional Requirements Specification (FR-01 to FR-12)</b>", styles["TableCaption"]))

    fr_data = [
        [Paragraph("<b>Req ID</b>", styles["TableHeader"]), Paragraph("<b>Functional Requirement Name</b>", styles["TableHeader"]), Paragraph("<b>Technical Specification & Behavior</b>", styles["TableHeader"]), Paragraph("<b>Target Subsystem</b>", styles["TableHeader"])],
        [Paragraph("<b>FR-01</b>", styles["TableCellBold"]), Paragraph("Inquest Case Registration", styles["TableCell"]), Paragraph("Create investigation cases with FIR number, incident datetime, and police jurisdiction", styles["TableCell"]), Paragraph("Case Management (MOD-01)", styles["TableCell"])],
        [Paragraph("<b>FR-02</b>", styles["TableCellBold"]), Paragraph("Investigator Authentication", styles["TableCell"]), Paragraph("Authenticate sworn officers via OIDC provider and validate RS256/EdDSA signed JWTs", styles["TableCell"]), Paragraph("Identity & Auth (MOD-02)", styles["TableCell"])],
        [Paragraph("<b>FR-03</b>", styles["TableCellBold"]), Paragraph("Access Control Governance", styles["TableCell"]), Paragraph("Enforce hybrid RBAC/ABAC checking badge role, assigned case ID, and station jurisdiction", styles["TableCell"]), Paragraph("Authorization (MOD-03)", styles["TableCell"])],
        [Paragraph("<b>FR-04</b>", styles["TableCellBold"]), Paragraph("Stage Lifecycle Engine", styles["TableCell"]), Paragraph("Control transitions across statutory stages (Initiated -> Inquest -> Forensic -> Chargesheet)", styles["TableCell"]), Paragraph("Stage Engine (MOD-04)", styles["TableCell"])],
        [Paragraph("<b>FR-05</b>", styles["TableCellBold"]), Paragraph("Streaming Evidence Intake", styles["TableCell"]), Paragraph("Ingest multi-part file streams with upload rate limiting, chunking, and metadata binding", styles["TableCell"]), Paragraph("Evidence Intake (MOD-05)", styles["TableCell"])],
        [Paragraph("<b>FR-06</b>", styles["TableCellBold"]), Paragraph("MIME & Signature Sniffing", styles["TableCell"]), Paragraph("Inspect binary magic bytes (16 bytes) to verify actual file format and block spoofing", styles["TableCell"]), Paragraph("Validation (MOD-06)", styles["TableCell"])],
        [Paragraph("<b>FR-07</b>", styles["TableCellBold"]), Paragraph("Fail-Closed Antivirus Scan", styles["TableCell"]), Paragraph("Scan exhibits via ClamAV socket; quarantine infected files and strip read/write permissions", styles["TableCell"]), Paragraph("Antivirus (MOD-07)", styles["TableCell"])],
        [Paragraph("<b>FR-08</b>", styles["TableCellBold"]), Paragraph("Immutable WORM Commit", styles["TableCell"]), Paragraph("Write exhibits to read-only POSIX directory (0440 permissions) and generate SHA-256 pre-hash", styles["TableCell"]), Paragraph("WORM Commit (MOD-08)", styles["TableCell"])],
        [Paragraph("<b>FR-09</b>", styles["TableCellBold"]), Paragraph("Dual Cryptographic Hashing", styles["TableCell"]), Paragraph("Compute SHA-256 and SHA3-512 digests; verify SHA-256 matches pre-hash to detect bit-rot", styles["TableCell"]), Paragraph("Dual Hashing (MOD-09)", styles["TableCell"])],
        [Paragraph("<b>FR-10</b>", styles["TableCellBold"]), Paragraph("WORM Object Locking", styles["TableCell"]), Paragraph("Enforce application-layer retention policies and legal hold manifests in object repository", styles["TableCell"]), Paragraph("Object Lock (MOD-10)", styles["TableCell"])],
        [Paragraph("<b>FR-11</b>", styles["TableCellBold"]), Paragraph("AES-256-GCM Encryption", styles["TableCell"]), Paragraph("Encrypt exhibits at rest using 256-bit AES-GCM cipher with per-case keys and AAD binding", styles["TableCell"]), Paragraph("Encryption (MOD-11)", styles["TableCell"])],
        [Paragraph("<b>FR-12</b>", styles["TableCellBold"]), Paragraph("Forensic Audit Logging", styles["TableCell"]), Paragraph("Record every access, validation, quarantine, and cipher event in immutable database ledger", styles["TableCell"]), Paragraph("Audit Subsystem", styles["TableCell"])],
    ]

    fr_table = Table(fr_data, colWidths=[52, 110, 195, 94])
    fr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(fr_table)

    story.append(Spacer(1, 10))

    # 3.7 Non-Functional Requirements Specification
    story.append(page_tracker_cls("sec3_7"))
    story.append(Paragraph("3.7 Non-Functional Requirements Specification", styles["SectionHeading"]))
    story.append(Paragraph(
        "Table 3.2 details the 8 essential Non-Functional Requirements (NFR-01 to NFR-08) governing security, integrity, and performance.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab3_2"))
    story.append(Paragraph("<b>Table 3.2: Formal Non-Functional Requirements Specification (NFR-01 to NFR-08)</b>", styles["TableCaption"]))

    nfr_data = [
        [Paragraph("<b>Req ID</b>", styles["TableHeader"]), Paragraph("<b>Quality Attribute</b>", styles["TableHeader"]), Paragraph("<b>Architectural Specification & Metric</b>", styles["TableHeader"]), Paragraph("<b>Enforcement Mechanism</b>", styles["TableHeader"])],
        [Paragraph("<b>NFR-01</b>", styles["TableCellBold"]), Paragraph("Cryptographic Security", styles["TableCell"]), Paragraph("256-bit symmetric security level; authenticated encryption for all stored forensic data", styles["TableCell"]), Paragraph("AES-256-GCM cipher with CSPRNG 96-bit nonces (MOD-11)", styles["TableCell"])],
        [Paragraph("<b>NFR-02</b>", styles["TableCellBold"]), Paragraph("Evidentiary Integrity", styles["TableCell"]), Paragraph("Mathematical tamper-evidence; zero tolerance for undetected bit-rot or byte modification", styles["TableCell"]), Paragraph("Dual Hashing (SHA-256 + SHA3-512) and WORM Object Lock", styles["TableCell"])],
        [Paragraph("<b>NFR-03</b>", styles["TableCellBold"]), Paragraph("Fail-Closed Security", styles["TableCell"]), Paragraph("Any scanner failure, socket timeout, or hash mismatch must halt pipeline immediately", styles["TableCell"]), Paragraph("Strict Python exception hierarchy raising HTTP 503 / 400", styles["TableCell"])],
        [Paragraph("<b>NFR-04</b>", styles["TableCellBold"]), Paragraph("Case Isolation", styles["TableCell"]), Paragraph("Complete physical and logical segregation of files and encryption keys between cases", styles["TableCell"]), Paragraph("UUID-partitioned directories and per-case key derivation", styles["TableCell"])],
        [Paragraph("<b>NFR-05</b>", styles["TableCellBold"]), Paragraph("System Availability", styles["TableCell"]), Paragraph("High service uptime with resilient database transaction handling under WAL journal mode", styles["TableCell"]), Paragraph("SQLAlchemy connection pooling & SQLite/Postgres WAL", styles["TableCell"])],
        [Paragraph("<b>NFR-06</b>", styles["TableCellBold"]), Paragraph("Ingestion Throughput", styles["TableCell"]), Paragraph("Sub-second processing for standard forensic documents (<10 MB) through intake pipeline", styles["TableCell"]), Paragraph("Asynchronous streaming file intake & buffered hashing", styles["TableCell"])],
        [Paragraph("<b>NFR-07</b>", styles["TableCellBold"]), Paragraph("Full Explainability", styles["TableCell"]), Paragraph("100% of analytical findings must trace back to immutable exhibit hashes and citations", styles["TableCell"]), Paragraph("EC-MORE Evidence Gate binding (Phases 14–17)", styles["TableCell"])],
        [Paragraph("<b>NFR-08</b>", styles["TableCellBold"]), Paragraph("Human Supremacy", styles["TableCell"]), Paragraph("Zero autonomous legal, judicial, or operational actions permitted without human IO sign-off", styles["TableCell"]), Paragraph("Architectural HITL gate at all stage transitions", styles["TableCell"])],
    ]

    nfr_table = Table(nfr_data, colWidths=[52, 105, 195, 99])
    nfr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(nfr_table)

    story.append(Spacer(1, 10))

    # 3.8 System Actors and Personas
    story.append(page_tracker_cls("sec3_8"))
    story.append(Paragraph("3.8 System Actors and Personas", styles["SectionHeading"]))
    story.append(Paragraph(
        "The SAKSHI platform defines three primary system actors with strictly segregated statutory privileges:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "• <b>Investigating Officer (IO):</b> The sworn police official legally charged with conducting the unnatural death inquest. The IO "
        "creates cases, uploads forensic evidence, reviews automated validation receipts, inspects temporal contradictions, reviews "
        "investigative gaps, and authorizes case stage transitions. The IO retains sole legal decision-making authority.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Supervisory Officer (SO):</b> A senior law enforcement official (e.g., Superintendent of Police or Sub-Divisional Police Officer) "
        "exercising administrative and procedural oversight. The SO reviews case progression, approves formal inquest stage escalations, "
        "inspects cross-case contradiction summaries, and audits compliance with statutory guidelines.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>System Administrator / Forensic Custodian:</b> Technical personnel responsible for infrastructure health, ClamAV daemon updates, "
        "WORM volume storage maintenance, KMS/vault key rotation, and cryptographic audit log verification. The Administrator has zero access "
        "to plaintext case evidence without explicit judicial audit authorization.",
        styles["BulletText"]
    ))

    # 3.9 Overall SAKSHI Architecture Diagram
    story.append(page_tracker_cls("sec3_9"))
    story.append(Paragraph("3.9 Overall SAKSHI Architecture Diagram", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 3.1 illustrates the complete multi-tier architecture of the SAKSHI platform, highlighting the logical boundaries between "
        "the presentation tier, the API/security gateway, the cryptographic evidence pipeline, and the downstream EC-MORE cognitive tier. "
        "The human Investigating Officer is positioned at the apex as the final decision-maker.",
        styles["AcademicBody"]
    ))

    story.append(get_system_architecture_diagram())
    story.append(page_tracker_cls("fig3_1"))
    story.append(Paragraph("<b>Figure 3.1: SAKSHI Overall System Architecture & Multi-Tier Topology</b>", styles["FigureCaption"]))
    story.append(Paragraph(
        "<i>Explanation of Figure 3.1:</i> The architecture illustrates the complete flow of data from the Investigating Officer's client "
        "workstation across the TLS-secured network boundary into the FastAPI API Gateway. Incoming requests undergo OIDC token validation "
        "and hybrid RBAC/ABAC evaluation. All uploaded evidence streams are routed directly into the Cryptographic Evidence Security Pipeline "
        "(Phases 2 and 3), where files are validated, scanned, committed to immutable WORM storage, dual-hashed, locked, and encrypted using "
        "AES-256-GCM. Downstream cognitive processing (Phases 4–17) operates strictly on cryptographically verified exhibits, culminating in "
        "explainable briefings returned to the human investigator.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 8))

    story.append(get_ec_more_architecture_diagram())
    story.append(page_tracker_cls("fig3_2"))
    story.append(Paragraph("<b>Figure 3.2: EC-MORE Dual-Brain & Evidence-Constrained Reasoning Architecture</b>", styles["FigureCaption"]))
    story.append(Paragraph(
        "<i>Explanation of Figure 3.2:</i> The diagram models the EC-MORE reasoning paradigm. The Intuition Brain generates unconstrained "
        "exploratory investigative hypotheses, which are passed through an Information Firewall to eliminate speculative assumptions. The "
        "Discipline Brain evaluates the filtered hypotheses against the strict Evidence Gate, which only admits exhibits with verified WORM "
        "hashes. Unsupported hypotheses are pruned, and missing leads are routed to the Investigative Gap Engine.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))

    # 3.10 SAKSHI 17-Phase Comprehensive Pipeline
    story.append(page_tracker_cls("sec3_10"))
    story.append(Paragraph("3.10 SAKSHI 17-Phase Comprehensive Pipeline", styles["SectionHeading"]))
    story.append(Paragraph(
        "The complete end-to-end SAKSHI roadmap is formulated across 17 structured phases, specified in Table 3.3 and modeled in Figure 3.3. "
        "This architectural breakdown establishes clear engineering boundaries between current implementation and future roadmap.",
        styles["AcademicBody"]
    ))

    story.append(get_pipeline_17_diagram())
    story.append(page_tracker_cls("fig3_3"))
    story.append(Paragraph("<b>Figure 3.3: SAKSHI 17-Phase End-to-End Investigation Lifecycle Flow</b>", styles["FigureCaption"]))

    story.append(page_tracker_cls("tab3_3"))
    story.append(Paragraph("<b>Table 3.3: Comprehensive SAKSHI 17-Phase Architecture Specification</b>", styles["TableCaption"]))

    p17_data = [
        [Paragraph("<b>Phase # & Name</b>", styles["TableHeader"]), Paragraph("<b>Input Artifacts</b>", styles["TableHeader"]), Paragraph("<b>Core Processing & Transformation</b>", styles["TableHeader"]), Paragraph("<b>Output Artifacts</b>", styles["TableHeader"]), Paragraph("<b>Next Phase</b>", styles["TableHeader"])],
        [Paragraph("<b>1. Case Initiation</b>", styles["TableCellBold"]), Paragraph("FIR metadata, Inquest IO token", styles["TableCell"]), Paragraph("Case registration, OIDC auth, RBAC/ABAC checks, workspace creation", styles["TableCell"]), Paragraph("Isolated Case Workspace", styles["TableCell"]), Paragraph("Phase 2", styles["TableCell"])],
        [Paragraph("<b>2. Evidence Ingestion</b>", styles["TableCellBold"]), Paragraph("Raw binary multi-modal exhibits", styles["TableCell"]), Paragraph("Magic-byte sniffing, fail-closed ClamAV, WORM commit, pre-hash", styles["TableCell"]), Paragraph("Immutable WORM File Object", styles["TableCell"]), Paragraph("Phase 3", styles["TableCell"])],
        [Paragraph("<b>3. Security & Integrity</b>", styles["TableCellBold"]), Paragraph("WORM File Object", styles["TableCell"]), Paragraph("Dual hashing (SHA256+SHA3), WORM Object Lock, AES-256-GCM cipher", styles["TableCell"]), Paragraph("Protected Vault Evidence Object", styles["TableCell"]), Paragraph("Phase 4", styles["TableCell"])],
        [Paragraph("<b>4. Multimodal Processing</b>", styles["TableCellBold"]), Paragraph("Protected Vault Evidence", styles["TableCell"]), Paragraph("OCR text extraction, speech-to-text, frame sampling from CCTV", styles["TableCell"]), Paragraph("Normalized Text & Visual Tokens", styles["TableCell"]), Paragraph("Phase 5", styles["TableCell"])],
        [Paragraph("<b>5. NLP / Info Extraction</b>", styles["TableCellBold"]), Paragraph("Normalized Text & Metadata", styles["TableCell"]), Paragraph("Legal-domain entity recognition, relation extraction, event parsing", styles["TableCell"]), Paragraph("Structured Forensic Entities", styles["TableCell"]), Paragraph("Phase 6", styles["TableCell"])],
        [Paragraph("<b>6. Structured Case Memory</b>", styles["TableCellBold"]), Paragraph("Forensic Entities & Relations", styles["TableCell"]), Paragraph("Entity deduplication, coreference resolution, relational storage", styles["TableCell"]), Paragraph("Structured Case Memory (SCM)", styles["TableCell"]), Paragraph("Phase 7", styles["TableCell"])],
        [Paragraph("<b>7. Knowledge Graph</b>", styles["TableCellBold"]), Paragraph("Case Memory Entities", styles["TableCell"]), Paragraph("Graph embedding, associative linking, cross-case entity resolution", styles["TableCell"]), Paragraph("Forensic Knowledge Graph", styles["TableCell"]), Paragraph("Phase 8", styles["TableCell"])],
        [Paragraph("<b>8. Timeline Reconstruction</b>", styles["TableCellBold"]), Paragraph("Temporal events & CDR logs", styles["TableCell"]), Paragraph("Chronological event aggregation, interval calculus, clock alignment", styles["TableCell"]), Paragraph("Unified Master Inquest Timeline", styles["TableCell"]), Paragraph("Phase 9", styles["TableCell"])],
        [Paragraph("<b>9. Contradiction Detection</b>", styles["TableCellBold"]), Paragraph("Timeline & witness depositions", styles["TableCell"]), Paragraph("Temporal, spatial, and physiological contradiction discovery algorithms", styles["TableCell"]), Paragraph("Flagged Contradiction Matrix", styles["TableCell"]), Paragraph("Phase 10", styles["TableCell"])],
        [Paragraph("<b>10. Context Assembly</b>", styles["TableCellBold"]), Paragraph("Case Memory, Graph, Timeline", styles["TableCell"]), Paragraph("Context window packaging, evidentiary constraint binding", styles["TableCell"]), Paragraph("Assembled Inquest Context", styles["TableCell"]), Paragraph("Phase 11", styles["TableCell"])],
        [Paragraph("<b>11. Intuition Brain</b>", styles["TableCellBold"]), Paragraph("Assembled Inquest Context", styles["TableCell"]), Paragraph("Associative hypothesis generation, exploratory modus operandi patterns", styles["TableCell"]), Paragraph("Candidate Investigative Hypotheses", styles["TableCell"]), Paragraph("Phase 12", styles["TableCell"])],
        [Paragraph("<b>12. Information Firewall</b>", styles["TableCellBold"]), Paragraph("Candidate Hypotheses", styles["TableCell"]), Paragraph("Speculative assumption filtering, unverified claim stripping", styles["TableCell"]), Paragraph("Filtered Hypothesis Candidates", styles["TableCell"]), Paragraph("Phase 13", styles["TableCell"])],
        [Paragraph("<b>13. Discipline Brain</b>", styles["TableCellBold"]), Paragraph("Filtered Candidates & Exhibits", styles["TableCell"]), Paragraph("Strict evidential falsification, logical consistency verification", styles["TableCell"]), Paragraph("Falsified / Corroborated Claims", styles["TableCell"]), Paragraph("Phase 14", styles["TableCell"])],
        [Paragraph("<b>14. Evidence Gate</b>", styles["TableCellBold"]), Paragraph("Corroborated Claims & Hashes", styles["TableCell"]), Paragraph("Cryptographic hash verification; blocks any unanchored deduction", styles["TableCell"]), Paragraph("Evidence-Constrained Findings", styles["TableCell"]), Paragraph("Phase 15", styles["TableCell"])],
        [Paragraph("<b>15. Legal / Procedural Rules</b>", styles["TableCellBold"]), Paragraph("Constrained Findings", styles["TableCell"]), Paragraph("BNSS / statutory inquest compliance check, mandatory protocol audit", styles["TableCell"]), Paragraph("Legally Validated Findings", styles["TableCell"]), Paragraph("Phase 16", styles["TableCell"])],
        [Paragraph("<b>16. Gap Engine</b>", styles["TableCellBold"]), Paragraph("Case State & Evidence Graph", styles["TableCell"]), Paragraph("Discovery of missing forensic swabs, uninterrogated contacts, missing CDR", styles["TableCell"]), Paragraph("Investigative Action Checklist", styles["TableCell"]), Paragraph("Phase 17", styles["TableCell"])],
        [Paragraph("<b>17. Explainable Output & Review</b>", styles["TableCellBold"]), Paragraph("Findings & Action Checklist", styles["TableCell"]), Paragraph("Natural language briefing generation with interactive exhibit citations", styles["TableCell"]), Paragraph("Inquest Briefing for IO Sign-Off", styles["TableCell"]), Paragraph("IO Decision", styles["TableCell"])],
    ]

    p17_table = Table(p17_data, colWidths=[95, 80, 115, 95, 66])
    p17_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(p17_table)

    story.append(Spacer(1, 10))

    # 3.11 Phase 1 Architecture
    story.append(page_tracker_cls("sec3_11"))
    story.append(Paragraph("3.11 Phase 1 Architecture: Case Initiation", styles["SectionHeading"]))
    story.append(Paragraph(
        "Phase 1 establishes the legal and administrative perimeter of an inquest inquiry. It comprises four core modules (MOD-01 to "
        "MOD-04) that govern case registration, identity authentication, fine-grained authorization, and statutory lifecycle tracking. "
        "Table 3.4 outlines their responsibilities, and Figure 3.4 illustrates their sequential integration.",
        styles["AcademicBody"]
    ))

    story.append(get_phase1_architecture_diagram())
    story.append(page_tracker_cls("fig3_4"))
    story.append(Paragraph("<b>Figure 3.4: Phase 1 Architecture: Inquest Case Initiation (MOD-01 to MOD-04)</b>", styles["FigureCaption"]))

    story.append(page_tracker_cls("tab3_4"))
    story.append(Paragraph("<b>Table 3.4: Phase 1 Core Modules: Case Initiation & RBAC Governance</b>", styles["TableCaption"]))

    p1_data = [
        [Paragraph("<b>Module ID</b>", styles["TableHeader"]), Paragraph("<b>Module Name</b>", styles["TableHeader"]), Paragraph("<b>Core Functional Scope</b>", styles["TableHeader"]), Paragraph("<b>Status</b>", styles["TableHeader"])],
        [Paragraph("<b>MOD-01</b>", styles["TableCellBold"]), Paragraph("Case Management", styles["TableCell"]), Paragraph("Registers FIR numbers, assigns lead IO, creates isolated case directory partition", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-02</b>", styles["TableCellBold"]), Paragraph("Identity / OIDC", styles["TableCell"]), Paragraph("Federates identity via OpenID Connect, parses and validates RS256/EdDSA JWT tokens", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-03</b>", styles["TableCellBold"]), Paragraph("RBAC / ABAC", styles["TableCell"]), Paragraph("Evaluates user roles, station jurisdictions, and case assignments; enforces case isolation", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-04</b>", styles["TableCellBold"]), Paragraph("Stage Engine", styles["TableCell"]), Paragraph("Governs statutory inquest stages (INITIATED, INQUEST, FORENSIC, CHARGESHEET, CLOSED)", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
    ]
    p1_table = Table(p1_data, colWidths=[65, 110, 205, 71])
    p1_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(p1_table)

    story.append(Spacer(1, 10))

    # 3.12 Phase 2 Architecture
    story.append(page_tracker_cls("sec3_12"))
    story.append(Paragraph("3.12 Phase 2 Architecture: Evidence Ingestion", styles["SectionHeading"]))
    story.append(Paragraph(
        "Phase 2 implements the multi-modal evidence ingestion gateway across modules MOD-05 to MOD-08. It guarantees that no file enters "
        "the repository without binary verification, malware scanning, and immutable storage commitment, as detailed in Table 3.5 and Figure 3.5.",
        styles["AcademicBody"]
    ))

    story.append(get_phase2_architecture_diagram())
    story.append(page_tracker_cls("fig3_5"))
    story.append(Paragraph("<b>Figure 3.5: Phase 2 Architecture: Evidence Ingestion Pipeline (MOD-05 to MOD-08)</b>", styles["FigureCaption"]))

    story.append(page_tracker_cls("tab3_5"))
    story.append(Paragraph("<b>Table 3.5: Phase 2 Core Modules: Multi-modal Evidence Ingestion Pipeline</b>", styles["TableCaption"]))

    p2_data = [
        [Paragraph("<b>Module ID</b>", styles["TableHeader"]), Paragraph("<b>Module Name</b>", styles["TableHeader"]), Paragraph("<b>Core Functional Scope</b>", styles["TableHeader"]), Paragraph("<b>Status</b>", styles["TableHeader"])],
        [Paragraph("<b>MOD-05</b>", styles["TableCellBold"]), Paragraph("Evidence Intake", styles["TableCell"]), Paragraph("Multi-part file streaming, chunking, rate limiting, and initial exhibit registration", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-06</b>", styles["TableCellBold"]), Paragraph("MIME Validation", styles["TableCell"]), Paragraph("Sniffs initial 16 bytes for magic signatures; blocks spoofed extension attacks", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-07</b>", styles["TableCellBold"]), Paragraph("Antivirus Scan", styles["TableCell"]), Paragraph("Streams file to ClamAV daemon over TCP socket; fail-closed isolation of infected files", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-08</b>", styles["TableCellBold"]), Paragraph("WORM Commit", styles["TableCell"]), Paragraph("Writes exhibit to read-only POSIX directory (0440 mode) and computes SHA-256 pre-hash", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
    ]
    p2_table = Table(p2_data, colWidths=[65, 110, 205, 71])
    p2_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(p2_table)

    story.append(Spacer(1, 10))

    # 3.13 Phase 3 Architecture
    story.append(page_tracker_cls("sec3_13"))
    story.append(Paragraph("3.13 Phase 3 Architecture: Security & Integrity", styles["SectionHeading"]))
    story.append(Paragraph(
        "Phase 3 establishes the cryptographic vault layer across modules MOD-09 to MOD-13. Crucially, the implementation status is: "
        "<b>MOD-09, MOD-10, and MOD-11 are COMPLETE and verified</b>, whereas <b>MOD-12 and MOD-13 are PENDING</b>, as detailed in Table 3.6 and Figure 3.6.",
        styles["AcademicBody"]
    ))

    story.append(get_phase3_architecture_diagram())
    story.append(page_tracker_cls("fig3_6"))
    story.append(Paragraph("<b>Figure 3.6: Phase 3 Architecture: Security, Dual Hashing & WORM Lock (MOD-09 to MOD-13)</b>", styles["FigureCaption"]))

    story.append(page_tracker_cls("tab3_6"))
    story.append(Paragraph("<b>Table 3.6: Phase 3 Core Modules: Cryptographic Integrity & Vault Storage</b>", styles["TableCaption"]))

    p3_data = [
        [Paragraph("<b>Module ID</b>", styles["TableHeader"]), Paragraph("<b>Module Name</b>", styles["TableHeader"]), Paragraph("<b>Core Functional Scope</b>", styles["TableHeader"]), Paragraph("<b>Status</b>", styles["TableHeader"])],
        [Paragraph("<b>MOD-09</b>", styles["TableCellBold"]), Paragraph("Dual Hashing", styles["TableCell"]), Paragraph("Computes SHA-256 and SHA3-512; validates SHA-256 against MOD-08 pre-hash to detect bit-rot", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-10</b>", styles["TableCellBold"]), Paragraph("WORM Object Lock", styles["TableCell"]), Paragraph("Applies legal hold metadata, retention periods, and non-deletable object storage references", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-11</b>", styles["TableCellBold"]), Paragraph("AES-256-GCM", styles["TableCell"]), Paragraph("Encrypts exhibits at rest with case-isolated keys, 96-bit CSPRNG nonces, and AAD metadata", styles["TableCell"]), Paragraph("COMPLETE", styles["TableCellBold"])],
        [Paragraph("<b>MOD-12</b>", styles["TableCellBold"]), Paragraph("TLS 1.3 / mTLS", styles["TableCell"]), Paragraph("Enforces strict mutual TLS authentication and cipher negotiation for inter-service calls", styles["TableCell"]), Paragraph("PENDING (Next)", styles["TableCell"])],
        [Paragraph("<b>MOD-13</b>", styles["TableCellBold"]), Paragraph("Merkle Audit Ledger", styles["TableCell"]), Paragraph("Appends all custodial events to a cryptographic Merkle tree for mathematical non-repudiation", styles["TableCell"]), Paragraph("PENDING", styles["TableCell"])],
    ]
    p3_table = Table(p3_data, colWidths=[65, 110, 205, 71])
    p3_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(p3_table)

    story.append(Spacer(1, 10))

    # 3.14 Security Architecture & Defense-in-Depth
    story.append(page_tracker_cls("sec3_14"))
    story.append(Paragraph("3.14 Security Architecture & Defense-in-Depth", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 3.7 diagrams the sequential 7-stage evidence pipeline implemented across Phase 2 and Phase 3. Every stage functions as a "
        "fail-closed barrier: if any check fails, the transaction is immediately aborted, the file is stripped of read/write permissions, "
        "and a high-priority security alert is logged.",
        styles["AcademicBody"]
    ))

    story.append(get_evidence_security_pipeline_diagram())
    story.append(page_tracker_cls("fig3_7"))
    story.append(Paragraph("<b>Figure 3.7: Evidence Security Pipeline Flowchart (MOD-05 to MOD-11)</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 3.15 Data Flow Modeling
    story.append(page_tracker_cls("sec3_15"))
    story.append(Paragraph("3.15 Data Flow Modeling (Level 0 and Level 1)", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 3.9 illustrates the movement of evidentiary artifacts across system boundaries. The Level 0 context diagram shows external "
        "entities (Investigator, Inquest Magistrate), while the Level 1 DFD decomposes the system into four major processes operating on "
        "three distinct physical data stores: D1 (WORM Read-Only Repository), D2 (Object Lock Vault), and D3 (Case Relational DB).",
        styles["AcademicBody"]
    ))

    story.append(get_dfd_diagram())
    story.append(page_tracker_cls("fig3_9"))
    story.append(Paragraph("<b>Figure 3.9: Data Flow Diagram: Context Level 0 and Detailed Level 1 Decomposition</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 3.16 UML Use Case Model & Formal Specifications
    story.append(page_tracker_cls("sec3_16"))
    story.append(Paragraph("3.16 UML Use Case Model & Formal Specifications", styles["SectionHeading"]))
    story.append(Paragraph(
        "Figure 3.8 models the primary use cases executed by the three system actors across the forensic investigation lifecycle.",
        styles["AcademicBody"]
    ))

    story.append(get_use_case_diagram())
    story.append(page_tracker_cls("fig3_8"))
    story.append(Paragraph("<b>Figure 3.8: UML Use Case Model for Forensic Inquest Lifecycle</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 3.17 UML Structural and Behavioral Models
    story.append(page_tracker_cls("sec3_17"))
    story.append(Paragraph("3.17 UML Structural and Behavioral Models", styles["SectionHeading"]))
    story.append(Paragraph(
        "To provide a complete engineering specification, Figures 3.10 through 3.14 present the UML Class, Sequence, Activity, "
        "Component, and Deployment models governing the platform.",
        styles["AcademicBody"]
    ))

    story.append(get_class_diagram())
    story.append(page_tracker_cls("fig3_10"))
    story.append(Paragraph("<b>Figure 3.10: UML Domain Class Model for SAKSHI Core Entities and Services</b>", styles["FigureCaption"]))
    story.append(Spacer(1, 8))

    story.append(get_sequence_diagram())
    story.append(page_tracker_cls("fig3_11"))
    story.append(Paragraph("<b>Figure 3.11: UML Sequence Diagram: Evidence Ingestion & Cryptographic Gating</b>", styles["FigureCaption"]))
    story.append(Spacer(1, 8))

    story.append(get_activity_diagram())
    story.append(page_tracker_cls("fig3_12"))
    story.append(Paragraph("<b>Figure 3.12: UML Activity Diagram: Evidence Inspection, ClamAV, WORM & Vault</b>", styles["FigureCaption"]))
    story.append(Spacer(1, 8))

    story.append(get_component_diagram())
    story.append(page_tracker_cls("fig3_13"))
    story.append(Paragraph("<b>Figure 3.13: UML Component Diagram: Service Decoupling & Storage Boundaries</b>", styles["FigureCaption"]))
    story.append(Spacer(1, 8))

    story.append(get_deployment_diagram())
    story.append(page_tracker_cls("fig3_14"))
    story.append(Paragraph("<b>Figure 3.14: UML Deployment Diagram: Client Workstation, API Host & Vault Server</b>", styles["FigureCaption"]))

    story.append(Spacer(1, 10))

    # 3.18 Database Architecture and Storage Design
    story.append(page_tracker_cls("sec3_18"))
    story.append(Paragraph("3.18 Database Architecture and Storage Design", styles["SectionHeading"]))
    story.append(Paragraph(
        "The database architecture is designed for dual compatibility with SQLite (in Write-Ahead Logging mode for localized, zero-config "
        "deployment) and enterprise PostgreSQL. Primary keys are modeled as 128-bit Universally Unique Identifiers (UUIDv4) to guarantee "
        "global uniqueness across distributed stations. Foreign key constraints enforce strict referential integrity between `CASES`, "
        "`EVIDENCE`, and `AUDIT_EVENTS` tables, preventing orphaned records.",
        styles["AcademicBody"]
    ))

    # 3.19 Human-in-the-Loop Governance Architecture
    story.append(page_tracker_cls("sec3_19"))
    story.append(Paragraph("3.19 Human-in-the-Loop Governance Architecture", styles["SectionHeading"]))
    story.append(Paragraph(
        "SAKSHI enforces Human-in-the-Loop governance through architectural gatekeepers. All cognitive reasoning modules output "
        "provisional findings accompanied by explicit cryptographic provenance tags. These findings cannot be committed to the official "
        "case chargesheet or presented in judicial dockets without explicit cryptographic approval by the assigned Investigating Officer.",
        styles["AcademicBody"]
    ))

    story.append(PageBreak())
    return story
