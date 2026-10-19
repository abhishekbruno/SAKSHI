"""
Chapter 2: Literature Survey for SAKSHI Academic Project Report.
Target length: 7–8 pages.
Covers:
2.1 Overview of Research Landscape
2.2 Comprehensive Literature Review (10 Foundational Studies)
2.3 Comparative Literature Analysis (Table 2.1)
2.4 System Capability Comparison (Table 2.2)
2.5 Research Gap Analysis
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27


def get_chapter2(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ch2"))
    story.append(Paragraph("CHAPTER 2", styles["ChapterHeading"]))
    story.append(Paragraph("LITERATURE SURVEY", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # 2.1 Overview of Research Landscape
    story.append(page_tracker_cls("sec2_1"))
    story.append(Paragraph("2.1 Overview of Research Landscape", styles["SectionHeading"]))
    story.append(Paragraph(
        "The engineering formulation of an intelligent investigation companion for unnatural death inquiries sits at the complex "
        "convergence of multiple distinct scientific and computational disciplines: digital forensic science, cryptographic data integrity, "
        "domain-specific natural language processing, semantic knowledge graphs, automated temporal reasoning, and explainable artificial "
        "intelligence (XAI). Historically, each of these domains has evolved within its own specialized academic silos without unified "
        "cross-disciplinary architectural integration.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "In digital forensics, research has overwhelmingly concentrated on low-level bit-stream disk imaging, raw memory dump analysis, "
        "file carving, and static chain of custody documentation. In computer science and artificial intelligence, recent research has "
        "focused heavily on the generative and contextual power of deep transformer architectures and large language models, frequently "
        "neglecting the strict legal requirements of verifiable provenance, cryptographic non-repudiation, and procedural due process. "
        "To establish a rigorous theoretical and empirical foundation for SAKSHI, this chapter conducts an exhaustive survey of ten "
        "pivotal research contributions spanning these foundational areas.",
        styles["AcademicBody"]
    ))

    # 2.2 Comprehensive Literature Review
    story.append(page_tracker_cls("sec2_2"))
    story.append(Paragraph("2.2 Comprehensive Literature Review", styles["SectionHeading"]))

    papers = [
        ("1. Doshi-Velez and Kim (2017) — Towards a Rigorous Science of Interpretable Machine Learning",
         "Explainable Artificial Intelligence (XAI) and High-Stakes Decision Support",
         "The opacity and lack of interpretability in modern complex machine learning systems operating in high-stakes domains such as healthcare, criminal justice, and judicial sentencing.",
         "Formulated a formal taxonomy of interpretability evaluation based on three distinct paradigms: application-grounded evaluation (involving domain experts performing domain-specific tasks), human-grounded evaluation (involving lay humans evaluating simplified explanation quality), and functionally-grounded evaluation (using formal proxy metrics without human intervention).",
         "Rigourously proved that in safety-critical and forensic environments, empirical statistical accuracy alone is fundamentally insufficient. Demonstrated that models must be capable of providing human-understandable, inspectable, and falsifiable explanations to prevent biased, unlawful, or dangerous algorithmic outcomes.",
         "The paper provided theoretical evaluation definitions but did not implement operational architectures for multimodal digital forensic evidence ingestion, nor did it address cryptographic chain of custody preservation.",
         "Directly establishes the foundational explainability requirement of SAKSHI: every analytical deduction, temporal contradiction, and investigative gap presented to the Investigating Officer must be accompanied by explicit, inspectable evidentiary citations rather than black-box probability scores."),

        ("2. Casey (2011) — Digital Evidence and Computer Crime: Forensic Science and the Internet",
         "Digital Forensics, Evidentiary Admissibility, and Forensic Science Protocols",
         "The absence of rigorous scientific methodologies and standardized handling protocols for digital artifacts, leading to compromised forensic integrity and evidentiary rejection during courtroom trials.",
         "Formulated a comprehensive forensic process model based on physical forensic principles: evidence identification, bit-stream forensic acquisition, cryptographic integrity hashing, systematic analysis, and courtroom presentation under statutory rules of evidence.",
         "Formalized the principle of forensic non-repudiation: digital exhibits must remain mathematically identical to their seized state throughout processing. Established that any transformation, filtering, or analysis must be recorded in an immutable, auditable chain of custody log.",
         "Focused entirely on manual digital forensic investigations conducted using standalone imaging tools. Did not envision automated cross-modal correlation, AI-assisted contradiction discovery, or intelligent case memory.",
         "Forms the direct architectural basis for SAKSHI's Phase 2 and Phase 3 boundaries: file signature sniffing, fail-closed antivirus scanning, WORM storage commitment, and pre-hash integrity checks prior to analytical processing."),

        ("3. Haber and Stornetta (1991) — How to Time-Stamp a Digital Document",
         "Cryptographic Integrity, Temporal Provenance, and Immutable Ledgers",
         "The extreme vulnerability of digital documents to undetectable temporal alteration, back-dating, or post-hoc modification on electronic storage media.",
         "Designed recursive cryptographic protocols utilizing one-way cryptographic hash functions and linked hash chains to create tamper-evident, verifiable certificates of a document's exact state of existence at a specific chronological point.",
         "Provided the foundational theoretical mathematics for modern distributed ledgers, Merkle trees, and immutable digital audit trails. Demonstrated that an unbroken sequence of cryptographic hashes provides mathematical non-repudiation without relying entirely on trusted centralized authorities.",
         "Purely a mathematical and cryptographic primitive. Did not address application-layer access controls, multi-tenant case isolation, or the ingestion of rich forensic media.",
         "Inspires SAKSHI's dual-hashing architecture (binding SHA-256 with SHA3-512) and provides the theoretical foundation for the planned MOD-13 Merkle-tree cryptographic audit ledger."),

        ("4. Buchholz and Spafford (2004) — On the Role of File System Metadata in Digital Forensics",
         "Forensic Timeline Reconstruction and Temporal Event Modeling",
         "The overwhelming difficulty investigators face in reconstructing chronological event sequences from disparate, uncoordinated filesystem timestamps (Modified, Accessed, Created, Born - MACB).",
         "Formalized a comprehensive mathematical and conceptual model of digital forensic events, defining an event as an action performed by an actor upon an object at a specific timestamp, aggregating heterogeneous filesystem logs into unified temporal event graphs.",
         "Demonstrated that automated chronological event aggregation significantly reduces the cognitive burden on human forensic analysts and reveals anomalous temporal clusters that indicate system intrusion or physical tampering.",
         "Relied exclusively on structured filesystem timestamps. Incapable of understanding, parsing, or extracting unstructured narrative timelines embedded within witness statements, inquest diaries, or medical-legal autopsy reports.",
         "Directly guides the design of SAKSHI's downstream Phase 8 (Timeline Reconstruction Engine), extending Buchholz and Spafford's event model from filesystem metadata to multimodal textual and sensor evidence."),

        ("5. Chalkidis et al. (2020) — LEGAL-BERT: The Muppets Straight Out of Law School",
         "Legal Natural Language Processing and Domain-Specific Transformers",
         "The poor performance and semantic misunderstanding exhibited by general-purpose language models (such as BERT and RoBERTa) when applied to complex statutory terminology, legal procedure, and judicial contracts.",
         "Pre-trained transformer-based language models on an extensive, specialized legal corpus exceeding 12 gigabytes of statutory legislation, court decisions, and European legal contracts, fine-tuning them across diverse legal NLP tasks.",
         "Achieved state-of-the-art performance in legal text classification, statutory violation identification, and named entity recognition within judicial documents, demonstrating that domain-specific contextual embeddings are essential for legal text understanding.",
         "The model operates as an unconstrained transformer; it is vulnerable to probabilistic hallucinations if applied outside strict evidence boundaries and possesses zero awareness of physical forensic integrity.",
         "Establishes the candidate architectural model for SAKSHI's downstream Phase 5 (NLP and Information Extraction), which will adapt specialized legal embeddings within the strict containment of the Evidence Gate."),

        ("6. Chau et al. (2002) — Extracting Spider Networks from Criminal Data",
         "Criminal Intelligence Knowledge Graphs and Entity Resolution",
         "The fragmentation of criminal intelligence across massive databases of incident narratives, making it nearly impossible for detectives to discover hidden associations between co-conspirators, locations, and vehicles.",
         "Developed automated heuristic algorithms combining semantic co-occurrence analysis, entity extraction, and graph theory to extract criminal associative networks ('spider networks') from unstructured police crime narrative reports.",
         "Demonstrated that graph-based representations of criminal entities and their semantic linkages dramatically accelerate cross-case intelligence discovery and expose covert organizational networks.",
         "Suffered from significant false-positive linkage rates due to unverified name co-occurrences. Lacked temporal contradiction detection, evidentiary confidence weighting, and cryptographic evidence verification.",
         "Informs the design of SAKSHI's downstream Phase 7 (Knowledge Graph) and Phase 6 (Structured Case Memory), incorporating Chau's entity-linking principles while enforcing strict evidence-grounded verification."),

        ("7. Quick and Choo (2014) — Data Reduction and Data Mining Framework for Digital Forensic Evidence",
         "Write-Once-Read-Many (WORM) Storage and Big Forensic Data Preservation",
         "The exponential growth of digital forensic exhibit sizes (terabytes per case), which overwhelms police storage infrastructure and threatens chain of custody preservation.",
         "Formulated a rigorous data reduction, selective preservation, and WORM storage governance framework designed to handle large-scale forensic datasets while ensuring legal compliance and evidentiary permanence.",
         "Established that forensic storage architectures must implement non-rewritable, non-erasable storage abstractions (WORM) coupled with cryptographic indexing to withstand rigorous legal cross-examination regarding evidence preservation.",
         "Focused primarily on bulk storage hardware management without integrating modern application-layer authenticated encryption (AES-256-GCM) or containerized microservice architectures.",
         "Directly justifies SAKSHI's two-tier immutable storage design: the local POSIX WORM abstraction implemented in MOD-08 and the application-layer WORM Object Lock governance implemented in MOD-10."),

        ("8. Amershi et al. (2019) / Binns et al. (2018) — Guidelines for Human-AI Interaction & Justice Perceptions",
         "Human-in-the-Loop AI Governance, Cognitive Trust, and Algorithmic Due Process",
         "The dangerous disconnect between autonomous machine learning capabilities and human user oversight in high-stakes public sector decision-making.",
         "Synthesized and empirically validated 18 fundamental human-AI interaction guidelines evaluating how AI systems convey capability boundaries, communicate uncertainty, mitigate user errors, and preserve human operational control.",
         "Demonstrated that in civic and legal contexts, user trust and perceived justice plummet when algorithmic systems attempt to automate moral, legal, or investigative judgments. Showed that AI must function strictly as an augmentative cognitive partner.",
         "Constituted general human-computer interaction guidelines; did not address the statutory procedural codes of police inquests or criminal procedural law.",
         "Provides the theoretical and ethical foundation for SAKSHI's Human-in-the-Loop governance: SAKSHI is architected strictly as an investigative companion, leaving all legal discretion and final case determinations exclusively with the human IO."),

        ("9. National Institute of Standards and Technology (NIST SP 800-38D, 2007) — Recommendation for Block Cipher Modes: GCM",
         "Authenticated Symmetric Encryption, Galois Counter Mode, and Data Confidentiality at Rest",
         "The catastrophic security vulnerability of encrypting sensitive data using traditional unauthenticated cipher modes (such as CBC or ECB), which protect confidentiality but remain completely vulnerable to ciphertext bit-flipping attacks.",
         "Formalized the mathematical specification for Galois/Counter Mode (GCM), combining counter-mode symmetric encryption with universal hashing over a binary Galois field (GF(2^128)) to produce an integrated 128-bit authentication tag.",
         "Standardized an authenticated encryption algorithm that provides both high-throughput confidentiality and cryptographic assurance of data authenticity and integrity, including the binding of unencrypted Additional Authenticated Data (AAD).",
         "NIST SP 800-38D is an algorithmic cryptographic specification; it does not address application-layer forensic file management, key isolation per investigation case, or WORM retention locks.",
         "Serves as the precise algorithmic foundation for SAKSHI's MOD-11 (AES-256-GCM authenticated encryption at rest), ensuring that all evidence stored in the repository is authenticated and tied to case metadata."),

        ("10. Carrier and Spafford (2003) — Getting Physical with the Digital Investigation Process",
         "Formal Digital Forensic Process Models and Physical-Digital Synthesis",
         "The lack of formal scientific foundations in digital investigations compared to established physical forensic disciplines (such as ballistics, fingerprint analysis, and bloodstain pattern analysis).",
         "Developed the Integrated Digital Investigation Process (IDIP), conceptualizing a digital computer as a physical crime scene and mapping physical investigative phases (preservation, survey, search, documentation) onto electronic data environments.",
         "Demonstrated that digital evidence must be treated with the exact same physical rigor as physical forensic exhibits, establishing the principle that digital environments require strict physical and logical scene isolation.",
         "The IDIP model was strictly manual and procedural; it lacked automated software architectures for processing streaming evidence, running antivirus pipelines, or performing automated contradiction detection.",
         "Directly validates SAKSHI's core philosophy of treating digital evidence as physical exhibits requiring strict quarantine, physical/logical case isolation, and immutable custody receipts.")
    ]

    for title, domain, prob, meth, cont, lim, rel in papers:
        story.append(Paragraph(f"<b>{title}</b>", styles["SubSectionHeading"]))
        story.append(Paragraph(f"• <b>Research Domain:</b> {domain}", styles["BulletText"]))
        story.append(Paragraph(f"• <b>Problem Addressed:</b> {prob}", styles["BulletText"]))
        story.append(Paragraph(f"• <b>Methodology:</b> {meth}", styles["BulletText"]))
        story.append(Paragraph(f"• <b>Major Contribution:</b> {cont}", styles["BulletText"]))
        story.append(Paragraph(f"• <b>Limitations:</b> {lim}", styles["BulletText"]))
        story.append(Paragraph(f"• <b>Relevance to SAKSHI:</b> {rel}", styles["BulletText"]))
        story.append(Spacer(1, 4))

    # 2.3 Comparative Literature Analysis
    story.append(page_tracker_cls("sec2_3"))
    story.append(Paragraph("2.3 Comparative Literature Analysis", styles["SectionHeading"]))
    story.append(Paragraph(
        "To synthesize the surveyed academic literature, Table 2.1 presents a structured comparative matrix evaluating each study's "
        "methodological approach, key strengths, critical limitations, and direct relevance to the SAKSHI platform.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab2_1"))
    story.append(Paragraph("<b>Table 2.1: Comparative Literature Survey Matrix Across Digital Forensics & AI</b>", styles["TableCaption"]))

    lit_comp_data = [
        [Paragraph("<b>Study / Authors</b>", styles["TableHeader"]), Paragraph("<b>Research Domain</b>", styles["TableHeader"]), Paragraph("<b>Methodology / Approach</b>", styles["TableHeader"]), Paragraph("<b>Key Contribution</b>", styles["TableHeader"]), Paragraph("<b>Critical Limitation</b>", styles["TableHeader"]), Paragraph("<b>Relevance to SAKSHI</b>", styles["TableHeader"])],
        [Paragraph("Doshi-Velez & Kim (2017)", styles["TableCellBold"]), Paragraph("XAI & High-Stakes ML", styles["TableCell"]), Paragraph("Evaluation taxonomy in judicial contexts", styles["TableCell"]), Paragraph("Proved accuracy insufficient without interpretability", styles["TableCell"]), Paragraph("No forensic ingestion or cryptographic custody", styles["TableCell"]), Paragraph("Mandates explainable evidence citations", styles["TableCell"])],
        [Paragraph("Casey (2011)", styles["TableCellBold"]), Paragraph("Digital Forensics", styles["TableCell"]), Paragraph("Standardized scientific protocols for evidence", styles["TableCell"]), Paragraph("Formalized non-repudiation and chain of custody", styles["TableCell"]), Paragraph("Manual workflows; no AI correlation support", styles["TableCell"]), Paragraph("Direct basis for Phase 2/3 ingestion gates", styles["TableCell"])],
        [Paragraph("Haber & Stornetta (1991)", styles["TableCellBold"]), Paragraph("Cryptographic Integrity", styles["TableCell"]), Paragraph("Linked one-way cryptographic hash chains", styles["TableCell"]), Paragraph("Foundational mathematical basis for immutable ledgers", styles["TableCell"]), Paragraph("Lacks application-layer access and object locking", styles["TableCell"]), Paragraph("Foundational for MOD-09 hashing & MOD-13 audit", styles["TableCell"])],
        [Paragraph("Buchholz & Spafford (2004)", styles["TableCellBold"]), Paragraph("Forensic Timeline", styles["TableCell"]), Paragraph("Formal event model from filesystem timestamps", styles["TableCell"]), Paragraph("Automated temporal aggregation reduces cognitive load", styles["TableCell"]), Paragraph("Cannot parse unstructured forensic narrative text", styles["TableCell"]), Paragraph("Informs Phase 8 timeline reconstruction", styles["TableCell"])],
        [Paragraph("Chalkidis et al. (2020)", styles["TableCellBold"]), Paragraph("Legal NLP", styles["TableCell"]), Paragraph("Domain pre-training of BERT on legal corpora", styles["TableCell"]), Paragraph("State-of-the-art legal entity and concept extraction", styles["TableCell"]), Paragraph("Ungrounded probabilistic hallucination danger", styles["TableCell"]), Paragraph("Candidate NLP engine for Phase 5 extraction", styles["TableCell"])],
        [Paragraph("Chau et al. (2002)", styles["TableCellBold"]), Paragraph("Crime Knowledge Graphs", styles["TableCell"]), Paragraph("Semantic networks & co-occurrence graph theory", styles["TableCell"]), Paragraph("Visualized hidden linkages across police narratives", styles["TableCell"]), Paragraph("High false positives; no contradiction engine", styles["TableCell"]), Paragraph("Informs Phase 7 Knowledge Graph architecture", styles["TableCell"])],
        [Paragraph("Quick & Choo (2014)", styles["TableCellBold"]), Paragraph("WORM Forensic Storage", styles["TableCell"]), Paragraph("WORM storage controls for big forensic data", styles["TableCell"]), Paragraph("Ensured non-rewritable evidentiary permanence", styles["TableCell"]), Paragraph("Lacked authenticated encryption & dual hashing", styles["TableCell"]), Paragraph("Justifies MOD-08 & MOD-10 WORM Object Lock", styles["TableCell"])],
        [Paragraph("Amershi et al. (2019)", styles["TableCellBold"]), Paragraph("Human-AI Interaction", styles["TableCell"]), Paragraph("18 design guidelines for user-AI collaboration", styles["TableCell"]), Paragraph("Formulated imperative for human operational control", styles["TableCell"]), Paragraph("Generic guidelines; lacks statutory legal mapping", styles["TableCell"]), Paragraph("Enforces IO supremacy & human review gate", styles["TableCell"])],
        [Paragraph("NIST SP 800-38D (2007)", styles["TableCellBold"]), Paragraph("Cryptography (GCM)", styles["TableCell"]), Paragraph("Symmetric counter mode + Galois field auth", styles["TableCell"]), Paragraph("Standardized authenticated encryption with AAD", styles["TableCell"]), Paragraph("Cryptographic primitive; lacks case management", styles["TableCell"]), Paragraph("Direct basis for MOD-11 AES-256-GCM cipher", styles["TableCell"])],
        [Paragraph("Carrier & Spafford (2003)", styles["TableCellBold"]), Paragraph("Investigation Models", styles["TableCell"]), Paragraph("Integrated Digital Investigation Process (IDIP)", styles["TableCell"]), Paragraph("Mapped physical crime-scene rigor onto digital data", styles["TableCell"]), Paragraph("Purely procedural; lacked automated software", styles["TableCell"]), Paragraph("Directly validates case isolation & quarantine", styles["TableCell"])],
    ]

    lit_comp_table = Table(lit_comp_data, colWidths=[75, 65, 80, 80, 75, 76])
    lit_comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(lit_comp_table)

    story.append(Spacer(1, 10))

    # 2.4 System Capability Comparison
    story.append(page_tracker_cls("sec2_4"))
    story.append(Paragraph("2.4 System Capability Comparison", styles["SectionHeading"]))
    story.append(Paragraph(
        "To explicitly demonstrate the architectural superiority and technical novelty of SAKSHI, Table 2.2 contrasts the capabilities "
        "of existing forensic tools and commercial AI frameworks against the unified approach implemented in SAKSHI.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab2_2"))
    story.append(Paragraph("<b>Table 2.2: System Capability Comparison: Existing Research vs SAKSHI Platform</b>", styles["TableCaption"]))

    cap_data = [
        [Paragraph("<b>Investigation Capability</b>", styles["TableHeader"]), Paragraph("<b>Existing Forensic Tools (EnCase, FTK, Autopsy)</b>", styles["TableHeader"]), Paragraph("<b>Commercial Generative AI (LLMs / Agents)</b>", styles["TableHeader"]), Paragraph("<b>SAKSHI Platform (EC-MORE Paradigm)</b>", styles["TableHeader"])],
        [Paragraph("<b>Evidence Ingestion & Validation</b>", styles["TableCellBold"]), Paragraph("Manual bit-stream acquisition; file-level hex carving", styles["TableCell"]), Paragraph("Unverified text prompt ingestion; no binary validation", styles["TableCell"]), Paragraph("Multi-modal intake with binary magic-byte sniffing & fail-closed ClamAV (MOD-05 to MOD-07)", styles["TableCell"])],
        [Paragraph("<b>Cryptographic Evidence Integrity</b>", styles["TableCellBold"]), Paragraph("Single MD5/SHA-1/SHA-256 pre-hash; no at-rest cipher", styles["TableCell"]), Paragraph("None; data transferred to third-party cloud servers", styles["TableCell"]), Paragraph("Pre-hash verification + Dual Hashing (SHA-256 + SHA3-512) + AES-256-GCM with AAD (MOD-08 to MOD-11)", styles["TableCell"])],
        [Paragraph("<b>Immutable Storage Governance</b>", styles["TableCellBold"]), Paragraph("Read-only hardware write-blockers during acquisition", styles["TableCell"]), Paragraph("Ephemeral memory; no immutable storage guarantees", styles["TableCell"]), Paragraph("Two-tier immutable storage: POSIX WORM commit + Application-layer WORM Object Lock with retention (MOD-08, MOD-10)", styles["TableCell"])],
        [Paragraph("<b>Access Control & Case Isolation</b>", styles["TableCellBold"]), Paragraph("Local operating system user permissions only", styles["TableCell"]), Paragraph("Account-level API keys; no inquest-level case isolation", styles["TableCell"]), Paragraph("Cryptographic JWT/OIDC authentication with hybrid RBAC/ABAC and strict per-case filesystem isolation (MOD-01 to MOD-03)", styles["TableCell"])],
        [Paragraph("<b>Cognitive Reasoning & Hallucination</b>", styles["TableCellBold"]), Paragraph("No cognitive reasoning; purely passive indexing", styles["TableCell"]), Paragraph("High risk of ungrounded hallucinations & fabricated facts", styles["TableCell"]), Paragraph("Evidence-Constrained Modus Operandi Reconstruction (EC-MORE) with strict Evidence Gate preventing unverified inferences", styles["TableCell"])],
        [Paragraph("<b>Timeline & Contradiction Detection</b>", styles["TableCellBold"]), Paragraph("Basic MACB timestamp sorting across files", styles["TableCell"]), Paragraph("Probabilistic narrative synthesis without provenance", styles["TableCell"]), Paragraph("Formal multimodal temporal event aggregation with cross-modal contradiction detection (Phases 8–9 Roadmap)", styles["TableCell"])],
        [Paragraph("<b>Investigative Gap Discovery</b>", styles["TableCellBold"]), Paragraph("None; investigator must manually spot missing leads", styles["TableCell"]), Paragraph("Ad-hoc text suggestions lacking legal procedure mapping", styles["TableCell"]), Paragraph("Systematic statutory gap engine identifying missing forensic reports, phone records, and witness interviews (Phase 16 Roadmap)", styles["TableCell"])],
        [Paragraph("<b>Judicial Decision Primacy</b>", styles["TableCellBold"]), Paragraph("Investigator performs all manual correlation", styles["TableCell"]), Paragraph("Dangerous autonomous overreach; attempts predictive guilt", styles["TableCell"]), Paragraph("Strict Human-in-the-Loop governance; AI acts purely as companion; IO retains 100% judicial authority", styles["TableCell"])],
    ]

    cap_table = Table(cap_data, colWidths=[95, 115, 115, 126])
    cap_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(cap_table)

    story.append(Spacer(1, 10))

    # 2.5 Research Gap Analysis
    story.append(page_tracker_cls("sec2_5"))
    story.append(Paragraph("2.5 Research Gap Analysis", styles["SectionHeading"]))
    story.append(Paragraph(
        "A rigorous synthesis of the existing literature reveals a profound structural and methodological gap at the intersection of "
        "digital forensic engineering and artificial intelligence. The literature demonstrates four fundamental disconnects:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "1. <b>The Disconnect Between Forensic Preservation and Cognitive Reasoning:</b> Established digital forensic suites (e.g., "
        "EnCase, FTK, Autopsy, Magnet AXIOM) focus almost exclusively on bit-stream acquisition, hex inspection, keyword searching, and "
        "file carving. Once exhibits are imaged and indexed, these tools offer zero cognitive assistance. The human detective must "
        "manually synthesize thousands of chat messages, dissect toxicological reports, cross-reference phone call records against cell "
        "towers, and mentally reconcile temporal narratives. Conversely, modern generative AI tools focus purely on reasoning over text "
        "but operate on unverified, unauthenticated input data with zero chain of custody guarantees.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "2. <b>The Fatal Risk of AI Hallucination in Judicial Inquests:</b> General-purpose Large Language Models (LLMs) operate on "
        "probabilistic next-token prediction. In a criminal inquest concerning an unnatural death, an unconstrained AI model can effortlessly "
        "hallucinate non-existent phone calls, fabricate timestamps, invent conflicting alibis, or misinterpret post-mortem lividity as "
        "antemortem traumatic contusions. Existing literature completely lacks an operational <b>Evidence Gate</b> mechanism that "
        "mathematically restricts analytical reasoning exclusively to cryptographically provenanced exhibits.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "3. <b>Absence of Integrated Defense-in-Depth Cryptographic Storage:</b> Traditional forensic repositories rely almost exclusively "
        "on legacy, single-algorithm SHA-256 pre-hashes calculated during initial disk imaging. They fail to enforce defense-in-depth: "
        "they lack real-time binary magic-byte spoofing detection, fail-closed antivirus scanning, immutable WORM commitment, multi-algorithm "
        "dual hashing (SHA-256 combined with SHA3-512 to prevent quantum and algorithmic compromise), application-layer Object Locking with "
        "legal hold governance, and per-case isolated AES-256-GCM authenticated encryption at rest.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "4. <b>Autonomous AI Overreach vs Human Investigator Primacy:</b> Emerging commercial 'AI policing' tools frequently attempt to "
        "deliver autonomous 'verdicts', predict recidivism, or assign automated guilt scores. These systems violate constitutional "
        "due-process principles and create grave risks of bias and miscarriages of justice. There is an acute absence in the academic "
        "literature of an architecture designed explicitly as an <b>investigative companion</b>—a system that organizes case memory, "
        "highlights temporal contradictions, and surfaces investigative omissions while leaving all operational and judicial discretion "
        "strictly in human hands.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "<b>How SAKSHI Resolves the Research Gap:</b> SAKSHI resolves these systemic disconnects by unifying multi-tier cryptographic data "
        "integrity with the <b>Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)</b> paradigm. By construction, SAKSHI prevents "
        "unverified, unauthenticated files from entering case memory, binds all inferences to immutable exhibit hashes, subjects exploratory "
        "hypotheses to strict evidential falsification, and enforces human-in-the-loop oversight throughout every stage of the inquest.",
        styles["AcademicBody"]
    ))

    story.append(PageBreak())
    return story
