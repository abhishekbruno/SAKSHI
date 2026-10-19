"""
Chapter 6: Security, Limitations and Future Work for SAKSHI Academic Project Report.
Target length: 4–5 pages.
Covers 8 detailed sections:
6.1 Architectural Security Principles
6.2 Evidence Integrity & Non-Repudiation
6.3 Identity, RBAC & ABAC Governance
6.4 Physical and Logical Case Isolation
6.5 Cryptographic Protection of Evidence at Rest
6.6 Human-in-the-Loop Operational Boundaries
6.7 Current System Limitations (Table 6.1)
6.8 Future Research & Architectural Enhancements (Table 6.2)
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27


def get_chapter6(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ch6"))
    story.append(Paragraph("CHAPTER 6", styles["ChapterHeading"]))
    story.append(Paragraph("SECURITY, LIMITATIONS AND FUTURE WORK", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # 6.1 Architectural Security Principles
    story.append(page_tracker_cls("sec6_1"))
    story.append(Paragraph("6.1 Architectural Security Principles", styles["SectionHeading"]))
    story.append(Paragraph(
        "The security architecture of SAKSHI is engineered upon the military and aerospace principle of <b>Defense-in-Depth</b> and "
        "the cryptographic tenet of <b>Zero Trust</b>. In digital forensic systems handling homicide inquests, digital evidence is "
        "presumed hostile until proven benign, and every component boundary enforces active verification. The platform rejects single "
        "points of security failure: a file must successfully pass through seven distinct, sequential security checkpoints—MIME sniffing, "
        "ClamAV malware scanning, immutable POSIX WORM commit, SHA-256 pre-hash verification, independent SHA3-512 dual hashing, "
        "application-layer WORM Object Locking, and AES-256-GCM envelope encryption—before it is admitted into case memory.",
        styles["AcademicBody"]
    ))

    # 6.2 Evidence Integrity & Non-Repudiation
    story.append(page_tracker_cls("sec6_2"))
    story.append(Paragraph("6.2 Evidence Integrity & Non-Repudiation", styles["SectionHeading"]))
    story.append(Paragraph(
        "Evidentiary non-repudiation is achieved through dual-algorithm cryptographic binding. SAKSHI couples SHA-256 (a Merkle-Damgård "
        "construction standard) with SHA3-512 (a Keccak sponge permutation standard). This multi-family hash binding guarantees that even "
        "if an unexpected mathematical weakness or quantum collision attack is discovered against one hashing family, the alternative "
        "digest preserves the mathematical integrity proof of the original exhibit. Furthermore, because SHA-256 is verified against the "
        "MOD-08 pre-hash before dual hashing proceeds, any storage medium degradation (bit-rot) is instantly flagged.",
        styles["AcademicBody"]
    ))

    # 6.3 Identity, RBAC & ABAC Governance
    story.append(page_tracker_cls("sec6_3"))
    story.append(Paragraph("6.3 Identity, RBAC & ABAC Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "Identity governance combines cryptographic token validation with fine-grained contextual authorization. OpenID Connect "
        "federation ensures that the identity provider manages officer credentials and multi-factor authentication, issuing RS256-signed "
        "JWTs. Authorization evaluates both the officer's static role (Investigating Officer, Supervisory Officer, Administrator) and dynamic "
        "case attributes: an IO can only read or write evidence for cases registered within their specific police station jurisdiction to "
        "which they have been formally assigned by administrative order.",
        styles["AcademicBody"]
    ))

    # 6.4 Physical and Logical Case Isolation
    story.append(page_tracker_cls("sec6_4"))
    story.append(Paragraph("6.4 Physical and Logical Case Isolation", styles["SectionHeading"]))
    story.append(Paragraph(
        "Case data is strictly segregated at both the logical database layer and the physical filesystem tier. Every registered case is "
        "assigned a randomly generated UUIDv4, creating an isolated filesystem directory tree. File access utilities strictly resolve "
        "canonical paths to prevent path traversal escapes. At the database layer, all queries enforce mandatory `case_id` predicate "
        "filters, guaranteeing complete multi-tenant case isolation across police stations.",
        styles["AcademicBody"]
    ))

    # 6.5 Cryptographic Protection of Evidence at Rest
    story.append(page_tracker_cls("sec6_5"))
    story.append(Paragraph("6.5 Cryptographic Protection of Evidence at Rest", styles["SectionHeading"]))
    story.append(Paragraph(
        "Evidence stored within the forensic vault is encrypted using the Advanced Encryption Standard in Galois/Counter Mode (AES-256-GCM), "
        "meeting NIST Special Publication 800-38D specifications. Each case derives an isolated 256-bit symmetric encryption key. Every "
        "encryption operation generates a unique 96-bit nonce from the operating system CSPRNG (`os.urandom`). The case ID, evidence ID, "
        "and dual cryptographic hashes are bound into the 128-bit Galois authentication tag as Additional Authenticated Data (AAD). "
        "This prevents ciphertext transplantation attacks: an encrypted block cannot be moved from Case A to Case B without triggering "
        "an authentication tag verification failure upon decryption.",
        styles["AcademicBody"]
    ))

    # 6.6 Human-in-the-Loop Operational Boundaries
    story.append(page_tracker_cls("sec6_6"))
    story.append(Paragraph("6.6 Human-in-the-Loop Operational Boundaries", styles["SectionHeading"]))
    story.append(Paragraph(
        "SAKSHI enforces rigid architectural boundaries to preserve human primacy. The platform is hardcoded to prevent autonomous "
        "operational actions: it cannot issue legal notices, modify statutory charges, declare an individual a suspect, or close an inquest. "
        "Every computational output is presented as an explainable, cited briefing. The human Investigating Officer retains absolute, "
        "unmitigated legal authority and responsibility for all investigative decisions.",
        styles["AcademicBody"]
    ))

    # 6.7 Current System Limitations
    story.append(page_tracker_cls("sec6_7"))
    story.append(Paragraph("6.7 Current System Limitations", styles["SectionHeading"]))
    story.append(Paragraph(
        "In strict adherence to academic honesty and engineering integrity, Table 6.1 documents the operational boundaries and current "
        "limitations of the SAKSHI platform implementation.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab6_1"))
    story.append(Paragraph("<b>Table 6.1: Current System Limitations & Production Deployment Boundaries</b>", styles["TableCaption"]))

    lim_data = [
        [Paragraph("<b>Limitation Area</b>", styles["TableHeader"]), Paragraph("<b>Current Implementation Boundary</b>", styles["TableHeader"]), Paragraph("<b>Engineering Impact & Risk</b>", styles["TableHeader"]), Paragraph("<b>Mitigation & Planned Resolution</b>", styles["TableHeader"])],
        [Paragraph("<b>TLS 1.3 / mTLS</b>", styles["TableCellBold"]), Paragraph("MOD-12 is currently PENDING; local deployment relies on host-level TLS termination", styles["TableCell"]), Paragraph("Inter-service calls on local network rely on perimeter firewalling", styles["TableCell"]), Paragraph("Scheduled next in Phase 3; will enforce mutual client cert auth", styles["TableCell"])],
        [Paragraph("<b>Merkle Audit Ledger</b>", styles["TableCellBold"]), Paragraph("MOD-13 is PENDING; audit events are stored in relational `AUDIT_EVENTS` table", styles["TableCell"]), Paragraph("Audit trail relies on database transaction isolation rather than cryptographic Merkle proofs", styles["TableCell"]), Paragraph("Scheduled for Phase 3 completion; will implement tamper-evident hash tree", styles["TableCell"])],
        [Paragraph("<b>Hardware HSM / KMS</b>", styles["TableCellBold"]), Paragraph("AES-256-GCM keys are derived locally using PBKDF2/HKDF; no hardware HSM integration", styles["TableCell"]), Paragraph("Key material resides in application process memory during active encryption", styles["TableCell"]), Paragraph("Architectural boundary established; pluggable interface for PKCS#11 HSMs", styles["TableCell"])],
        [Paragraph("<b>Object Lock Infrastructure</b>", styles["TableCellBold"]), Paragraph("MOD-10 implements local filesystem Object Locking via JSON manifests and POSIX permissions", styles["TableCell"]), Paragraph("Lacks cloud-native AWS S3 Object Lock API compliance in local dev", styles["TableCell"]), Paragraph("Designed with pluggable `IObjectLockBackend` interface for S3 compliance", styles["TableCell"])],
        [Paragraph("<b>Downstream AI Modules</b>", styles["TableCellBold"]), Paragraph("Phases 4 through 17 (Multimodal, NLP, Graph, Timeline, EC-MORE) are architectural roadmaps", styles["TableCell"]), Paragraph("Platform currently performs evidence ingestion and cryptographic security", styles["TableCell"]), Paragraph("Phased research roadmap formulated for subsequent academic milestones", styles["TableCell"])],
    ]

    lim_table = Table(lim_data, colWidths=[90, 115, 115, 131])
    lim_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(lim_table)

    story.append(Spacer(1, 10))

    # 6.8 Future Research & Architectural Enhancements
    story.append(page_tracker_cls("sec6_8"))
    story.append(Paragraph("6.8 Future Research & Architectural Enhancements", styles["SectionHeading"]))
    story.append(Paragraph(
        "Table 6.2 outlines the research roadmap for the subsequent development phases of SAKSHI, building directly upon the verified "
        "cryptographic ingestion layer established in Phases 1–3.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab6_2"))
    story.append(Paragraph("<b>Table 6.2: Future Research Roadmap Across Phases 4 to 17</b>", styles["TableCaption"]))

    enh_data = [
        [Paragraph("<b>Development Stage</b>", styles["TableHeader"]), Paragraph("<b>Target Phases</b>", styles["TableHeader"]), Paragraph("<b>Core Technical Milestones & Deliverables</b>", styles["TableHeader"]), Paragraph("<b>Target Research Timeline</b>", styles["TableHeader"])],
        [Paragraph("<b>Phase 3 Completion</b>", styles["TableCellBold"]), Paragraph("MOD-12, MOD-13", styles["TableCell"]), Paragraph("Implement TLS 1.3/mTLS mutual authentication; deploy Merkle-tree cryptographic audit ledger", styles["TableCell"]), Paragraph("Immediate Milestone", styles["TableCellBold"])],
        [Paragraph("<b>Multimodal Processing</b>", styles["TableCellBold"]), Paragraph("Phase 4", styles["TableCell"]), Paragraph("Deploy specialized OCR engines for handwritten case diaries; audio diarization for depositions", styles["TableCell"]), Paragraph("Next Development Cycle", styles["TableCell"])],
        [Paragraph("<b>Legal NLP & Case Memory</b>", styles["TableCellBold"]), Paragraph("Phases 5 & 6", styles["TableCell"]), Paragraph("Fine-tune LEGAL-BERT on Indian penal statutes; construct Structured Case Memory (SCM)", styles["TableCell"]), Paragraph("Mid-term Research", styles["TableCell"])],
        [Paragraph("<b>Knowledge Graph & Timeline</b>", styles["TableCellBold"]), Paragraph("Phases 7, 8, 9", styles["TableCell"]), Paragraph("Build Neo4j forensic graph; develop temporal event calculus; implement contradiction detection", styles["TableCell"]), Paragraph("Mid-term Research", styles["TableCell"])],
        [Paragraph("<b>EC-MORE Dual Brains</b>", styles["TableCellBold"]), Paragraph("Phases 10–14", styles["TableCell"]), Paragraph("Deploy Intuition and Discipline Brains separated by Information Firewall; enforce Evidence Gate", styles["TableCell"]), Paragraph("Advanced Research Milestone", styles["TableCell"])],
        [Paragraph("<b>Statutory Gap Engine</b>", styles["TableCellBold"]), Paragraph("Phases 15–17", styles["TableCell"]), Paragraph("Implement BNSS procedural compliance engine; automated forensic gap discovery; explainable UI", styles["TableCell"]), Paragraph("Final Deployment Milestone", styles["TableCell"])],
    ]

    enh_table = Table(enh_data, colWidths=[95, 75, 185, 96])
    enh_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(enh_table)

    story.append(PageBreak())
    return story
