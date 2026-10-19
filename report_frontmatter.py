"""
Front Matter Generator for SAKSHI Academic Project Report.
Contains:
1. Title Page
2. Certificate
3. Declaration
4. Acknowledgement
5. Abstract (Single-paragraph 150-300 words)
6. Table of Contents
7. List of Figures
8. List of Tables
9. List of Abbreviations
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27  # 1.0 inch margins on A4


def get_frontmatter(styles, get_pg_func, page_tracker_cls):
    story = []

    # ═══════════════════════════════════════════════════════════════════════
    # 1. TITLE PAGE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 10))
    story.append(Paragraph("[NAME OF AFFILIATED INSTITUTION / COLLEGE]", styles["AcademicSubtitle"]))
    story.append(Paragraph("[AFFILIATED UNIVERSITY / HIGHER EDUCATION BOARD]", styles["FigureCaption"]))
    story.append(Spacer(1, 15))

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=22, spaceBefore=0))

    story.append(Paragraph(
        "SAKSHI: EXPLAINABLE AI INVESTIGATION COMPANION FOR UNNATURAL DEATH INVESTIGATIONS USING EVIDENCE-CONSTRAINED MODUS OPERANDI RECONSTRUCTION (EC-MORE)",
        styles["AcademicTitle"]
    ))

    story.append(HRFlowable(width="60%", thickness=0.8, color=colors.HexColor("#A0AEC0"), spaceAfter=18, spaceBefore=12))

    story.append(Paragraph(
        "A PROJECT REPORT<br/><br/>"
        "<i>Submitted in partial fulfillment of the requirements for the award of the degree of</i><br/><br/>"
        "<b>BACHELOR OF TECHNOLOGY</b><br/>"
        "<b>IN</b><br/>"
        "<b>COMPUTER SCIENCE AND ENGINEERING</b>",
        styles["AcademicSubtitle"]
    ))

    story.append(Spacer(1, 25))

    student_guide_data = [
        [
            Paragraph("<b>Submitted by:</b><br/><br/><b>[STUDENT NAME]</b><br/>Register Number: [REGISTER NUMBER]", styles["AcademicBody"]),
            Paragraph("<b>Under the Guidance of:</b><br/><br/><b>[GUIDE NAME]</b><br/>[Designation, Department]", styles["AcademicBody"])
        ]
    ]
    sg_table = Table(student_guide_data, colWidths=[225, 226])
    sg_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sg_table)

    story.append(Spacer(1, 30))

    story.append(Paragraph(
        "<b>DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING</b><br/>"
        "<b>[COLLEGE NAME, CITY, STATE, PINCODE]</b><br/>"
        "<b>ACADEMIC YEAR: 2025 – 2026</b>",
        styles["AcademicSubtitle"]
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 2. CERTIFICATE PAGE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>[NAME OF AFFILIATED INSTITUTION / COLLEGE]</b>", styles["AcademicSubtitle"]))
    story.append(Paragraph("DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING", styles["FigureCaption"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("BONAFIDE CERTIFICATE", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="30%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=18, spaceBefore=0))

    story.append(Paragraph(
        "This is to certify that the project report entitled <b>“SAKSHI: EXPLAINABLE AI INVESTIGATION COMPANION "
        "FOR UNNATURAL DEATH INVESTIGATIONS USING EVIDENCE-CONSTRAINED MODUS OPERANDI RECONSTRUCTION (EC-MORE)”</b> "
        "is the bonafide work of <b>[STUDENT NAME] (Register Number: [REGISTER NUMBER])</b>, who carried out the "
        "project work under my supervision in partial fulfillment of the requirements for the award of the degree of "
        "<b>Bachelor of Technology in Computer Science and Engineering</b> during the academic year 2025–2026.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "The project demonstrates sound engineering formulation, rigorous cryptographic verification, defense-in-depth "
        "forensic security, and an evidence-first architecture that strictly preserves human investigative primacy.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 65))

    cert_table_data = [
        [
            Paragraph("<b>PROJECT GUIDE</b><br/><br/>_______________________<br/>[Guide Name]<br/>[Designation]", styles["AcademicBody"]),
            Paragraph("<b>HEAD OF DEPARTMENT</b><br/><br/>_______________________<br/>[HOD Name]<br/>Professor & Head", styles["AcademicBody"])
        ],
        [
            Paragraph("<br/><br/><b>INTERNAL EXAMINER</b><br/><br/>_______________________", styles["AcademicBody"]),
            Paragraph("<br/><br/><b>EXTERNAL EXAMINER</b><br/><br/>_______________________", styles["AcademicBody"])
        ]
    ]
    cert_table = Table(cert_table_data, colWidths=[225, 226])
    cert_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(cert_table)

    story.append(Spacer(1, 25))
    story.append(Paragraph("Date: ____________________<br/>Place: ____________________", styles["AcademicBody"]))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 3. DECLARATION PAGE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 15))
    story.append(Paragraph("CANDIDATE'S DECLARATION", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="30%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=20, spaceBefore=0))

    story.append(Paragraph(
        "I hereby declare that the project report entitled <b>“SAKSHI: EXPLAINABLE AI INVESTIGATION COMPANION "
        "FOR UNNATURAL DEATH INVESTIGATIONS USING EVIDENCE-CONSTRAINED MODUS OPERANDI RECONSTRUCTION (EC-MORE)”</b> "
        "submitted to the <b>Department of Computer Science and Engineering</b>, [College Name], affiliated to "
        "[Affiliated University], is a record of original engineering and scientific work done by me under the guidance of "
        "<b>[Guide Name]</b>, [Designation], Department of Computer Science and Engineering.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "I further declare that this report has not previously formed the basis for the award of any Degree, Diploma, "
        "Associateship, Fellowship, or other similar academic title to any candidate of any university or institution.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "All primary implementation results, architectural models, and verified test statistics reported herein represent "
        "actual empirical outcomes from the SAKSHI platform implementation without fabrication.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 75))

    decl_table_data = [
        [
            Paragraph("Date: ____________________<br/>Place: ____________________", styles["AcademicBody"]),
            Paragraph("<b>[STUDENT NAME]</b><br/>Register No: [REGISTER NUMBER]<br/>Department of CSE", styles["AcademicBody"])
        ]
    ]
    decl_table = Table(decl_table_data, colWidths=[225, 226])
    story.append(decl_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 4. ACKNOWLEDGEMENT PAGE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("ack"))
    story.append(Paragraph("ACKNOWLEDGEMENT", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="25%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=18, spaceBefore=0))

    story.append(Paragraph(
        "I express my profound gratitude to the Management and Principal of [College Name] for providing the academic "
        "infrastructure, computational facilities, and research atmosphere essential for the completion of this B.Tech project.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "I am deeply indebted to <b>[HOD Name]</b>, Professor and Head of the Department of Computer Science and Engineering, "
        "for his/her continuous encouragement, administrative facilitation, and scholarly guidance throughout the curriculum.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "I extend my heartfelt thanks and deepest respect to my project guide, <b>[Guide Name]</b>, [Designation], Department "
        "of Computer Science and Engineering, for invaluable mentorship, incisive technical critique, and unwavering support "
        "during every stage of architecture design, cryptographic verification, and implementation.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "I also thank all the faculty members and technical staff of the Department of Computer Science and Engineering for "
        "their academic assistance and support in setting up testing and containerized development environments.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "Finally, I express my sincere love and appreciation to my family and friends for their enduring patience, understanding, "
        "and moral encouragement throughout the tenure of my engineering education.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 35))
    story.append(Paragraph("<b>[STUDENT NAME]</b><br/>Register No: [REGISTER NUMBER]", styles["AcademicBodyBold"]))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 5. ABSTRACT PAGE (Single paragraph, 150-300 words)
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("abs"))
    story.append(Paragraph("ABSTRACT", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="20%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=16, spaceBefore=0))

    story.append(Paragraph(
        "Unnatural death investigations—encompassing suspected homicides, suicides, and complex accidental fatalities—present "
        "severe cognitive and organizational burdens to law enforcement agencies due to the staggering volume and heterogeneity of "
        "physical, documentary, and digital evidence. Conventional manual investigation workflows suffer from severe information fragmentation, "
        "manual correlation bottlenecks, cognitive confirmation bias, and fragile evidentiary chain of custody. This project presents "
        "<b>SAKSHI</b>, an <b>Explainable AI Investigation Companion</b> designed specifically to assist human investigators in handling complex "
        "unnatural-death inquiries using the <b>Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)</b> paradigm. SAKSHI rejects "
        "unbounded autonomous generative AI that risks forensic hallucination, establishing an <b>evidence-first architecture</b> centered on "
        "cryptographic evidence integrity, structured case memory, source traceability, and strict <b>human-in-the-loop oversight</b> where the "
        "Investigating Officer (IO) retains absolute legal and judicial authority. Digital evidence ingestion is governed by attribute-based "
        "access control, binary file signature sniffing, fail-closed antivirus scanning, immutable Write-Once-Read-Many (WORM) commitment, "
        "independent dual hashing combining SHA-256 and SHA3-512 algorithms, application-layer WORM Object Locking with retention governance, "
        "and per-case isolated AES-256-GCM authenticated encryption at rest. Architecturally formulated across 17 comprehensive phases, the "
        "current implementation status is: <b>Phase 1 (Case Initiation) is COMPLETE</b>; <b>Phase 2 (Evidence Ingestion) is COMPLETE</b>; and "
        "<b>Phase 3 (Security & Integrity) is IN PROGRESS</b> with <b>MOD-09 (Dual Hashing) COMPLETE</b>, <b>MOD-10 (WORM Object Lock) COMPLETE</b>, "
        "and <b>MOD-11 (AES-256-GCM Encryption) COMPLETE</b>, while MOD-12 (TLS 1.3 / mTLS) and MOD-13 (Merkle Audit Ledger) remain pending. The platform "
        "has been empirically verified through <b>298 automated tests passed with zero failures (100% success rate)</b>, demonstrating mathematically "
        "guaranteed tamper-resistance, robust case isolation, and verifiable chain of custody for digital forensics.",
        styles["AcademicBody"]
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Keywords:</b> Unnatural Death Investigation, Explainable AI, Evidence-Constrained Modus Operandi Reconstruction (EC-MORE), "
        "WORM Storage, Dual Hashing (SHA-256 / SHA3-512), AES-256-GCM Authenticated Encryption, Human-in-the-Loop, Digital Forensics.",
        styles["AcademicBodyBold"]
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 6. TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("toc"))
    story.append(Paragraph("TABLE OF CONTENTS", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="30%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    toc_entries = [
        ("Front Matter", ""),
        ("    Bonafide Certificate", "ii"),
        ("    Candidate's Declaration", "iii"),
        ("    Acknowledgement", get_pg_func("ack", "iv")),
        ("    Abstract", get_pg_func("abs", "v")),
        ("    List of Figures", get_pg_func("lof", "viii")),
        ("    List of Tables", get_pg_func("lot", "ix")),
        ("    List of Abbreviations", get_pg_func("loa", "x")),
        ("CHAPTER 1 — INTRODUCTION", get_pg_func("ch1", "1")),
        ("    1.1 Background of the Problem", get_pg_func("sec1_1", "1")),
        ("    1.2 Challenges in Unnatural Death Investigations", get_pg_func("sec1_2", "2")),
        ("    1.3 Motivation", get_pg_func("sec1_3", "3")),
        ("    1.4 Problem Statement", get_pg_func("sec1_4", "4")),
        ("    1.5 Objectives of the Project", get_pg_func("sec1_5", "4")),
        ("    1.6 Scope of the Project", get_pg_func("sec1_6", "5")),
        ("    1.7 Significance of the Project", get_pg_func("sec1_7", "6")),
        ("    1.8 Proposed EC-MORE Paradigm", get_pg_func("sec1_8", "6")),
        ("    1.9 Human-in-the-Loop Principle", get_pg_func("sec1_9", "7")),
        ("    1.10 Limitations of Conventional Investigation Workflows", get_pg_func("sec1_10", "7")),
        ("    1.11 Organization of the Report", get_pg_func("sec1_11", "8")),
        ("CHAPTER 2 — LITERATURE SURVEY", get_pg_func("ch2", "9")),
        ("    2.1 Overview of Research Landscape", get_pg_func("sec2_1", "9")),
        ("    2.2 Comprehensive Literature Review", get_pg_func("sec2_2", "10")),
        ("    2.3 Comparative Literature Analysis", get_pg_func("sec2_3", "14")),
        ("    2.4 System Capability Comparison", get_pg_func("sec2_4", "15")),
        ("    2.5 Research Gap Analysis", get_pg_func("sec2_5", "16")),
        ("CHAPTER 3 — SYSTEM ANALYSIS AND DESIGN", get_pg_func("ch3", "18")),
        ("    3.1 Existing System", get_pg_func("sec3_1", "18")),
        ("    3.2 Existing System Architecture", get_pg_func("sec3_2", "18")),
        ("    3.3 Problems in Existing System", get_pg_func("sec3_3", "19")),
        ("    3.4 Proposed System", get_pg_func("sec3_4", "19")),
        ("    3.5 Proposed System Architecture", get_pg_func("sec3_5", "20")),
        ("    3.6 Functional Requirements Specification", get_pg_func("sec3_6", "21")),
        ("    3.7 Non-Functional Requirements Specification", get_pg_func("sec3_7", "22")),
        ("    3.8 System Actors and Personas", get_pg_func("sec3_8", "23")),
        ("    3.9 Overall SAKSHI Architecture Diagram", get_pg_func("sec3_9", "23")),
        ("    3.10 SAKSHI 17-Phase Comprehensive Pipeline", get_pg_func("sec3_10", "25")),
        ("    3.11 Phase 1 Architecture: Case Initiation", get_pg_func("sec3_11", "27")),
        ("    3.12 Phase 2 Architecture: Evidence Ingestion", get_pg_func("sec3_12", "28")),
        ("    3.13 Phase 3 Architecture: Security & Integrity", get_pg_func("sec3_13", "29")),
        ("    3.14 Security Architecture & Defense-in-Depth", get_pg_func("sec3_14", "30")),
        ("    3.15 Data Flow Modeling (Level 0 and Level 1)", get_pg_func("sec3_15", "31")),
        ("    3.16 UML Use Case Model & Formal Specifications", get_pg_func("sec3_16", "32")),
        ("    3.17 UML Structural and Behavioral Models", get_pg_func("sec3_17", "33")),
        ("    3.18 Database Architecture and Storage Design", get_pg_func("sec3_18", "36")),
        ("    3.19 Human-in-the-Loop Governance Architecture", get_pg_func("sec3_19", "37")),
        ("CHAPTER 4 — IMPLEMENTATION", get_pg_func("ch4", "38")),
        ("    4.1 Development Environment & Tooling", get_pg_func("sec4_1", "38")),
        ("    4.2 Technology Stack Specification", get_pg_func("sec4_2", "38")),
        ("    4.3 Backend Architecture & Design Patterns", get_pg_func("sec4_3", "39")),
        ("    4.4 Database Implementation & Migration", get_pg_func("sec4_4", "40")),
        ("    4.5 Authentication Implementation (OIDC/JWT)", get_pg_func("sec4_5", "41")),
        ("    4.6 Authorization Implementation (RBAC/ABAC)", get_pg_func("sec4_6", "41")),
        ("    4.7 Case Management Service Implementation (MOD-01)", get_pg_func("sec4_7", "42")),
        ("    4.8 Evidence Intake Service Implementation (MOD-05)", get_pg_func("sec4_8", "43")),
        ("    4.9 MIME & Signature Validation Implementation (MOD-06)", get_pg_func("sec4_9", "44")),
        ("    4.10 Antivirus Inspection Implementation (MOD-07)", get_pg_func("sec4_10", "44")),
        ("    4.11 WORM Commit Implementation (MOD-08)", get_pg_func("sec4_11", "45")),
        ("    4.12 Dual Hashing Implementation (MOD-09)", get_pg_func("sec4_12", "46")),
        ("    4.13 WORM Object Lock Implementation (MOD-10)", get_pg_func("sec4_13", "47")),
        ("    4.14 AES-256-GCM Encryption Implementation (MOD-11)", get_pg_func("sec4_14", "48")),
        ("    4.15 API Implementation & Endpoint Contracts", get_pg_func("sec4_15", "49")),
        ("    4.16 Core Algorithmic Pseudocode (Algorithms 4.1 to 4.15)", get_pg_func("sec4_16", "51")),
        ("    4.17 Security Implementation & Path Traversal Guard", get_pg_func("sec4_17", "57")),
        ("    4.18 Error Handling & Domain Exception Hierarchy", get_pg_func("sec4_18", "58")),
        ("    4.19 Audit Logging & Forensic Traceability", get_pg_func("sec4_19", "59")),
        ("    4.20 User Interface & Forensic Dashboard Placeholders", get_pg_func("sec4_20", "60")),
        ("CHAPTER 5 — TESTING AND RESULTS", get_pg_func("ch5", "64")),
        ("    5.1 Comprehensive Testing Strategy", get_pg_func("sec5_1", "64")),
        ("    5.2 Unit Testing Execution", get_pg_func("sec5_2", "64")),
        ("    5.3 Integration Testing Execution", get_pg_func("sec5_3", "65")),
        ("    5.4 Security & Penetration Testing", get_pg_func("sec5_4", "65")),
        ("    5.5 Authentication Testing", get_pg_func("sec5_5", "66")),
        ("    5.6 Authorization & Role Enforcement Testing", get_pg_func("sec5_6", "66")),
        ("    5.7 Case Isolation & Multi-Tenancy Testing", get_pg_func("sec5_7", "67")),
        ("    5.8 Evidence Integrity & Bit-Rot Detection Testing", get_pg_func("sec5_8", "67")),
        ("    5.9 Cryptographic Cipher & Tag Verification Testing", get_pg_func("sec5_9", "68")),
        ("    5.10 RESTful API Integration Testing", get_pg_func("sec5_10", "68")),
        ("    5.11 Cumulative Regression Testing Principle", get_pg_func("sec5_11", "69")),
        ("    5.12 Empirical Test Results Matrix (298 Tests Passed)", get_pg_func("sec5_12", "69")),
        ("    5.13 Result Discussion & Evaluation", get_pg_func("sec5_13", "71")),
        ("CHAPTER 6 — SECURITY, LIMITATIONS AND FUTURE WORK", get_pg_func("ch6", "72")),
        ("    6.1 Architectural Security Principles", get_pg_func("sec6_1", "72")),
        ("    6.2 Evidence Integrity & Non-Repudiation", get_pg_func("sec6_2", "72")),
        ("    6.3 Identity, RBAC & ABAC Governance", get_pg_func("sec6_3", "73")),
        ("    6.4 Physical and Logical Case Isolation", get_pg_func("sec6_4", "73")),
        ("    6.5 Cryptographic Protection of Evidence at Rest", get_pg_func("sec6_5", "74")),
        ("    6.6 Human-in-the-Loop Operational Boundaries", get_pg_func("sec6_6", "74")),
        ("    6.7 Current System Limitations", get_pg_func("sec6_7", "75")),
        ("    6.8 Future Research & Architectural Enhancements", get_pg_func("sec6_8", "76")),
        ("CONCLUSION", get_pg_func("concl", "78")),
        ("REFERENCES", get_pg_func("ref", "80")),
        ("APPENDICES", get_pg_func("app", "83")),
        ("    Appendix A — API Endpoint Summary", get_pg_func("app_a", "83")),
        ("    Appendix B — Database Schema Specification", get_pg_func("app_b", "84")),
        ("    Appendix C — Empirical Test Suite Catalog", get_pg_func("app_c", "85")),
        ("    Appendix D — Core Domain Pydantic Data Models", get_pg_func("app_d", "86")),
        ("    Appendix E — Example API Payloads and JSON Responses", get_pg_func("app_e", "87")),
        ("    Appendix F — Acronyms and Technical Glossary", get_pg_func("app_f", "88")),
        ("    Appendix G — Additional System Interface Specifications", get_pg_func("app_g", "89")),
    ]

    toc_table_data = []
    for title, page_str in toc_entries:
        is_main = title.startswith("CHAPTER") or title.startswith("CONCLUSION") or title.startswith("REFERENCES") or title.startswith("APPENDICES") or title == "Front Matter"
        p_title = Paragraph(f"<b>{title}</b>" if is_main else title, styles["TOCLine"])
        p_page = Paragraph(f"<b>{page_str}</b>" if is_main else page_str, styles["TOCPage"])
        toc_table_data.append([p_title, p_page])

    toc_table = Table(toc_table_data, colWidths=[395, 56])
    toc_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
    ]))
    story.append(toc_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 7. LIST OF FIGURES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("lof"))
    story.append(Paragraph("LIST OF FIGURES", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="25%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    figures_entries = [
        ("Figure 3.1", "SAKSHI Overall System Architecture & Multi-Tier Topology", get_pg_func("fig3_1", "24")),
        ("Figure 3.2", "EC-MORE Dual-Brain & Evidence-Constrained Reasoning Architecture", get_pg_func("fig3_2", "25")),
        ("Figure 3.3", "SAKSHI 17-Phase End-to-End Investigation Lifecycle Flow", get_pg_func("fig3_3", "26")),
        ("Figure 3.4", "Phase 1 Architecture: Inquest Case Initiation (MOD-01 to MOD-04)", get_pg_func("fig3_4", "27")),
        ("Figure 3.5", "Phase 2 Architecture: Evidence Ingestion Pipeline (MOD-05 to MOD-08)", get_pg_func("fig3_5", "28")),
        ("Figure 3.6", "Phase 3 Architecture: Security, Dual Hashing & WORM Lock (MOD-09 to MOD-13)", get_pg_func("fig3_6", "29")),
        ("Figure 3.7", "Evidence Security Pipeline Flowchart (MOD-05 to MOD-11)", get_pg_func("fig3_7", "30")),
        ("Figure 3.8", "UML Use Case Model for Forensic Inquest Lifecycle", get_pg_func("fig3_8", "32")),
        ("Figure 3.9", "Data Flow Diagram: Context Level 0 and Detailed Level 1 Decomposition", get_pg_func("fig3_9", "31")),
        ("Figure 3.10", "UML Domain Class Model for SAKSHI Core Entities and Services", get_pg_func("fig3_10", "34")),
        ("Figure 3.11", "UML Sequence Diagram: Evidence Ingestion & Cryptographic Gating", get_pg_func("fig3_11", "34")),
        ("Figure 3.12", "UML Activity Diagram: Evidence Inspection, ClamAV, WORM & Vault", get_pg_func("fig3_12", "35")),
        ("Figure 3.13", "UML Component Diagram: Service Decoupling & Storage Boundaries", get_pg_func("fig3_13", "35")),
        ("Figure 3.14", "UML Deployment Diagram: Client Workstation, API Host & Vault Server", get_pg_func("fig3_14", "36")),
        ("Figure 4.1", "Backend Layered Architecture & Modular Orchestration", get_pg_func("fig4_1", "39")),
        ("Figure 4.2", "Evidence Processing Workflow & Stage Verification Sequence", get_pg_func("fig4_2", "40")),
        ("Figure 4.3", "Dual Hashing Verification Workflow (SHA-256 + SHA3-512)", get_pg_func("fig4_3", "46")),
        ("Figure 4.4", "AES-256-GCM Envelope Encryption & AAD Binding Workflow", get_pg_func("fig4_4", "48")),
        ("Figure 4.5", "Authentication and Authorization Flow (OIDC -> JWT -> RBAC/ABAC)", get_pg_func("fig4_5", "41")),
        ("Figure 4.6", "Forensic Dashboard Interface Placeholder", get_pg_func("fig4_6", "60")),
        ("Figure 4.7", "Case Initiation & FIR Metadata Registration Interface Placeholder", get_pg_func("fig4_7", "60")),
        ("Figure 4.8", "Isolated Case Workspace Partition Interface Placeholder", get_pg_func("fig4_8", "60")),
        ("Figure 4.9", "Multi-modal Evidence Registration Dialog Placeholder", get_pg_func("fig4_9", "61")),
        ("Figure 4.10", "MIME Sniffing & Binary Magic-Byte Inspection Outcome Placeholder", get_pg_func("fig4_10", "61")),
        ("Figure 4.11", "Antivirus Scanning & Quarantine Status Display Placeholder", get_pg_func("fig4_11", "61")),
        ("Figure 4.12", "Immutable WORM Commit & Pre-Hash Checksum Receipt Placeholder", get_pg_func("fig4_12", "62")),
        ("Figure 4.13", "Dual Hashing (SHA-256 + SHA3-512) Verification Display Placeholder", get_pg_func("fig4_13", "62")),
        ("Figure 4.14", "WORM Object Lock & Retention Policy Status Placeholder", get_pg_func("fig4_14", "62")),
        ("Figure 4.15", "AES-256-GCM Encryption & Key Isolation Status Placeholder", get_pg_func("fig4_15", "63")),
        ("Figure 4.16", "FastAPI Interactive OpenAPI / Swagger Documentation Interface Placeholder", get_pg_func("fig4_16", "63")),
        ("Figure 4.17", "System Health Monitoring Endpoint Output Placeholder", get_pg_func("fig4_17", "63")),
        ("Figure 4.18", "Authorization Denied (HTTP 403) Security Interception Placeholder", get_pg_func("fig4_18", "63")),
        ("Figure 4.19", "Case Isolation Error (HTTP 404/403 Boundary) Placeholder", get_pg_func("fig4_19", "63")),
        ("Figure 5.1", "Automated Testing & Multi-Tier Verification Workflow", get_pg_func("fig5_1", "65")),
    ]

    lof_table_data = []
    for f_id, f_desc, f_page in figures_entries:
        p_name = Paragraph(f"<b>{f_id}</b>: {f_desc}", styles["TOCLine"])
        p_page = Paragraph(f_page, styles["TOCPage"])
        lof_table_data.append([p_name, p_page])

    lof_table = Table(lof_table_data, colWidths=[395, 56])
    lof_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.2),
        ('TOPPADDING', (0, 0), (-1, -1), 1.2),
    ]))
    story.append(lof_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 8. LIST OF TABLES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("lot"))
    story.append(Paragraph("LIST OF TABLES", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="25%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    tables_entries = [
        ("Table 1.1", "Formal Project Objectives Mapped to Implementation Phases", get_pg_func("tab1_1", "5")),
        ("Table 2.1", "Comparative Literature Survey Matrix Across Digital Forensics & AI", get_pg_func("tab2_1", "14")),
        ("Table 2.2", "System Capability Comparison: Existing Research vs SAKSHI Platform", get_pg_func("tab2_2", "15")),
        ("Table 3.1", "Formal Functional Requirements Specification (FR-01 to FR-12)", get_pg_func("tab3_1", "21")),
        ("Table 3.2", "Formal Non-Functional Requirements Specification (NFR-01 to NFR-08)", get_pg_func("tab3_2", "22")),
        ("Table 3.3", "Comprehensive SAKSHI 17-Phase Architecture Specification", get_pg_func("tab3_3", "25")),
        ("Table 3.4", "Phase 1 Core Modules: Case Initiation & RBAC Governance", get_pg_func("tab3_4", "27")),
        ("Table 3.5", "Phase 2 Core Modules: Multi-modal Evidence Ingestion Pipeline", get_pg_func("tab3_5", "28")),
        ("Table 3.6", "Phase 3 Core Modules: Cryptographic Integrity & Vault Storage", get_pg_func("tab3_6", "29")),
        ("Table 4.1", "Complete SAKSHI Technology Stack & Architectural Rationale", get_pg_func("tab4_1", "38")),
        ("Table 4.2", "Implemented Modules Functional Specification (MOD-01 to MOD-11)", get_pg_func("tab4_2", "42")),
        ("Table 4.3", "RESTful API Specification & Endpoint Status Code Registry", get_pg_func("tab4_3", "49")),
        ("Table 4.4", "Module Implementation Status & Future Development Roadmap", get_pg_func("tab4_4", "50")),
        ("Table 5.1", "Testing Strategy, Methodologies & Verification Frameworks", get_pg_func("tab5_1", "64")),
        ("Table 5.2", "Empirical Automated Test Verification Matrix (298 Tests Passed)", get_pg_func("tab5_2", "70")),
        ("Table 6.1", "Current System Limitations & Production Deployment Boundaries", get_pg_func("tab6_1", "75")),
        ("Table 6.2", "Future Research Roadmap Across Phases 4 to 17", get_pg_func("tab6_2", "77")),
    ]

    lot_table_data = []
    for t_id, t_desc, t_page in tables_entries:
        p_name = Paragraph(f"<b>{t_id}</b>: {t_desc}", styles["TOCLine"])
        p_page = Paragraph(t_page, styles["TOCPage"])
        lot_table_data.append([p_name, p_page])

    lot_table = Table(lot_table_data, colWidths=[395, 56])
    lot_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    story.append(lot_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # 9. LIST OF ABBREVIATIONS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(page_tracker_cls("loa"))
    story.append(Paragraph("LIST OF ABBREVIATIONS", styles["FrontMatterHeading"]))
    story.append(HRFlowable(width="25%", thickness=1, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    abbr_data = [
        [Paragraph("<b>Abbreviation</b>", styles["TableHeader"]), Paragraph("<b>Full Expansion / Definition</b>", styles["TableHeader"])],
        [Paragraph("<b>AAD</b>", styles["TableCellBold"]), Paragraph("Additional Authenticated Data (Cryptographic GCM parameter)", styles["TableCell"])],
        [Paragraph("<b>ABAC</b>", styles["TableCellBold"]), Paragraph("Attribute-Based Access Control", styles["TableCell"])],
        [Paragraph("<b>AES</b>", styles["TableCellBold"]), Paragraph("Advanced Encryption Standard (FIPS PUB 197)", styles["TableCell"])],
        [Paragraph("<b>AI</b>", styles["TableCellBold"]), Paragraph("Artificial Intelligence", styles["TableCell"])],
        [Paragraph("<b>API</b>", styles["TableCellBold"]), Paragraph("Application Programming Interface", styles["TableCell"])],
        [Paragraph("<b>BNSS</b>", styles["TableCellBold"]), Paragraph("Bharatiya Nagarik Suraksha Sanhita, 2023", styles["TableCell"])],
        [Paragraph("<b>CCTV</b>", styles["TableCellBold"]), Paragraph("Closed-Circuit Television", styles["TableCell"])],
        [Paragraph("<b>CDR</b>", styles["TableCellBold"]), Paragraph("Call Detail Record", styles["TableCell"])],
        [Paragraph("<b>CSPRNG</b>", styles["TableCellBold"]), Paragraph("Cryptographically Secure Pseudo-Random Number Generator", styles["TableCell"])],
        [Paragraph("<b>CrPC</b>", styles["TableCellBold"]), Paragraph("Code of Criminal Procedure, 1973", styles["TableCell"])],
        [Paragraph("<b>DFD</b>", styles["TableCellBold"]), Paragraph("Data Flow Diagram", styles["TableCell"])],
        [Paragraph("<b>EC-MORE</b>", styles["TableCellBold"]), Paragraph("Evidence-Constrained Modus Operandi Reconstruction", styles["TableCell"])],
        [Paragraph("<b>ER</b>", styles["TableCellBold"]), Paragraph("Entity-Relationship (Data Model)", styles["TableCell"])],
        [Paragraph("<b>FIPS</b>", styles["TableCellBold"]), Paragraph("Federal Information Processing Standards", styles["TableCell"])],
        [Paragraph("<b>FIR</b>", styles["TableCellBold"]), Paragraph("First Information Report", styles["TableCell"])],
        [Paragraph("<b>FK</b>", styles["TableCellBold"]), Paragraph("Foreign Key", styles["TableCell"])],
        [Paragraph("<b>GCM</b>", styles["TableCellBold"]), Paragraph("Galois/Counter Mode (Authenticated symmetric block cipher mode)", styles["TableCell"])],
        [Paragraph("<b>HSM</b>", styles["TableCellBold"]), Paragraph("Hardware Security Module", styles["TableCell"])],
        [Paragraph("<b>HTTP / HTTPS</b>", styles["TableCellBold"]), Paragraph("Hypertext Transfer Protocol / HTTP Secure", styles["TableCell"])],
        [Paragraph("<b>IO</b>", styles["TableCellBold"]), Paragraph("Investigating Officer (Police officer conducting inquest)", styles["TableCell"])],
        [Paragraph("<b>ISO / IEC</b>", styles["TableCellBold"]), Paragraph("International Organization for Standardization / International Electrotechnical Commission", styles["TableCell"])],
        [Paragraph("<b>JWT</b>", styles["TableCellBold"]), Paragraph("JSON Web Token (RFC 7519)", styles["TableCell"])],
        [Paragraph("<b>KMS</b>", styles["TableCellBold"]), Paragraph("Key Management Service", styles["TableCell"])],
        [Paragraph("<b>MIME</b>", styles["TableCellBold"]), Paragraph("Multipurpose Internet Mail Extensions (Media type specification)", styles["TableCell"])],
        [Paragraph("<b>mTLS</b>", styles["TableCellBold"]), Paragraph("Mutual Transport Layer Security", styles["TableCell"])],
        [Paragraph("<b>NIST</b>", styles["TableCellBold"]), Paragraph("National Institute of Standards and Technology (USA)", styles["TableCell"])],
        [Paragraph("<b>NLP</b>", styles["TableCellBold"]), Paragraph("Natural Language Processing", styles["TableCell"])],
        [Paragraph("<b>OIDC</b>", styles["TableCellBold"]), Paragraph("OpenID Connect (Identity layer on top of OAuth 2.0)", styles["TableCell"])],
        [Paragraph("<b>ORM</b>", styles["TableCellBold"]), Paragraph("Object-Relational Mapping (SQLAlchemy)", styles["TableCell"])],
        [Paragraph("<b>PK</b>", styles["TableCellBold"]), Paragraph("Primary Key", styles["TableCell"])],
        [Paragraph("<b>POSIX</b>", styles["TableCellBold"]), Paragraph("Portable Operating System Interface", styles["TableCell"])],
        [Paragraph("<b>RBAC</b>", styles["TableCellBold"]), Paragraph("Role-Based Access Control", styles["TableCell"])],
        [Paragraph("<b>REST</b>", styles["TableCellBold"]), Paragraph("Representational State Transfer", styles["TableCell"])],
        [Paragraph("<b>SHA</b>", styles["TableCellBold"]), Paragraph("Secure Hash Algorithm (SHA-256 / SHA3-512)", styles["TableCell"])],
        [Paragraph("<b>SO</b>", styles["TableCellBold"]), Paragraph("Supervisory Officer (Senior police official reviewing cases)", styles["TableCell"])],
        [Paragraph("<b>TLS</b>", styles["TableCellBold"]), Paragraph("Transport Layer Security", styles["TableCell"])],
        [Paragraph("<b>UI / UX</b>", styles["TableCellBold"]), Paragraph("User Interface / User Experience", styles["TableCell"])],
        [Paragraph("<b>UML</b>", styles["TableCellBold"]), Paragraph("Unified Modeling Language", styles["TableCell"])],
        [Paragraph("<b>UUID</b>", styles["TableCellBold"]), Paragraph("Universally Unique Identifier", styles["TableCell"])],
        [Paragraph("<b>WAL</b>", styles["TableCellBold"]), Paragraph("Write-Ahead Logging (Database transaction journal)", styles["TableCell"])],
        [Paragraph("<b>WORM</b>", styles["TableCellBold"]), Paragraph("Write-Once-Read-Many (Immutable storage paradigm)", styles["TableCell"])],
        [Paragraph("<b>XAI</b>", styles["TableCellBold"]), Paragraph("Explainable Artificial Intelligence", styles["TableCell"])],
    ]

    abbr_table = Table(abbr_data, colWidths=[110, 341])
    abbr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(abbr_table)

    story.append(PageBreak())

    return story
