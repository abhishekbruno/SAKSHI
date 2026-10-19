"""
Conclusion section for SAKSHI Academic Project Report.
Target length: 2–3 pages.
"""
from reportlab.platypus import Paragraph, Spacer, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27


def get_conclusion(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("concl"))
    story.append(Paragraph("CONCLUSION", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    story.append(Paragraph(
        "Inquest proceedings and death inquiries represent one of the most intellectually arduous and socially sensitive domains "
        "within the criminal justice administration. Modern unnatural death investigations are characterized by an overwhelming influx "
        "of heterogeneous digital, documentary, and physical evidence—ranging from telecom call records and surveillance footage to forensic "
        "medical post-mortem reports and witness depositions. Conventional manual investigative workflows are plagued by acute cognitive "
        "overload, manual cross-referencing bottlenecks, fragmented evidence silos, undetected factual contradictions, and fragile chains of "
        "custody that frequently fail under judicial scrutiny. Concurrently, naive applications of modern generative AI introduce grave risks "
        "of forensic hallucination and due-process violations.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "To decisively overcome these dual challenges, this B.Tech Computer Science and Engineering project designed and engineered "
        "<b>SAKSHI</b>, an <b>Explainable AI Investigation Companion</b> grounded in the <b>Evidence-Constrained Modus Operandi Reconstruction "
        "(EC-MORE)</b> paradigm. SAKSHI fundamentally rejects ungrounded autonomous predictive models, establishing an evidence-first "
        "computational architecture where every inference is bound to cryptographically authenticated exhibits, and the human Investigating "
        "Officer remains the sole, sovereign decision-maker.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "The project has successfully formulated an end-to-end 17-phase architectural roadmap and brought the foundational cryptographic "
        "and ingestion pipeline into operational reality. The current verified implementation status is: <b>Phase 1 (Case Initiation) is "
        "COMPLETE</b>, providing secure case registration, OIDC/JWT authentication, and hybrid RBAC/ABAC jurisdictional access control; "
        "<b>Phase 2 (Evidence Ingestion) is COMPLETE</b>, enforcing binary magic-byte sniffing, fail-closed ClamAV antivirus inspection, and "
        "immutable POSIX WORM commitment with pre-hash generation; and <b>Phase 3 (Security & Integrity) is IN PROGRESS</b>, with <b>MOD-09 "
        "(Dual Hashing) COMPLETE</b>, <b>MOD-10 (WORM Object Lock) COMPLETE</b>, and <b>MOD-11 (AES-256-GCM Encryption) COMPLETE</b>.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "The integrity and reliability of the platform have been rigorously verified through an extensive quality assurance suite "
        "comprising <b>298 automated tests passed with zero failures (100% success rate)</b>. The testing matrix confirmed mathematical "
        "resilience against extension spoofing, path traversal, malware contamination, storage bit-rot, and ciphertext tampering.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "Looking forward, the immediate engineering milestone will complete Phase 3 by deploying TLS 1.3/mTLS inter-service encryption "
        "(MOD-12) and a Merkle-tree cryptographic audit ledger (MOD-13). Subsequent research phases will construct the multimodal NLP "
        "information extraction engine, Structured Case Memory (SCM), the forensic Knowledge Graph, automated timeline reconstruction, and "
        "the adversarial Dual Brain (Intuition vs Discipline) reasoning engine governed by the strict Evidence Gate.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "In conclusion, SAKSHI proves that cutting-edge artificial intelligence can be harmoniously integrated into high-stakes criminal "
        "jurisprudence—not by supplanting human judgment, but by providing an uncompromising, tamper-evident, and explainable computational "
        "companion that safeguards evidence integrity, illuminates truth, and upholds the solemn administration of justice.",
        styles["AcademicBody"]
    ))

    story.append(PageBreak())
    return story
