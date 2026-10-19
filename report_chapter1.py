"""
Chapter 1: Introduction for SAKSHI Academic Project Report.
Target length: 6–7 pages.
Covers 11 comprehensive sections:
1.1 Background of the Problem
1.2 Challenges in Unnatural Death Investigations
1.3 Motivation
1.4 Problem Statement
1.5 Objectives (with Table 1.1)
1.6 Scope of the Project
1.7 Significance of the Project
1.8 Proposed EC-MORE Paradigm
1.9 Human-in-the-Loop Principle
1.10 Limitations of Conventional Investigation Workflows
1.11 Organization of the Report
"""
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib import colors

W_CONTENT = 451.27


def get_chapter1(styles, page_tracker_cls):
    story = []

    story.append(page_tracker_cls("ch1"))
    story.append(Paragraph("CHAPTER 1", styles["ChapterHeading"]))
    story.append(Paragraph("INTRODUCTION", styles["ChapterHeading"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F294A"), spaceAfter=14, spaceBefore=0))

    # 1.1 Background of the Problem
    story.append(page_tracker_cls("sec1_1"))
    story.append(Paragraph("1.1 Background of the Problem", styles["SectionHeading"]))
    story.append(Paragraph(
        "The investigation of unnatural deaths—encompassing suspected homicides, suicides, custodial deaths, unexplained accidental "
        "fatalities, and deaths occurring under suspicious circumstances—constitutes one of the most critical and intellectually "
        "demanding responsibilities within the criminal justice ecosystem. Under statutory procedural codes, such as Section 194 of the "
        "<i>Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023</i> (and its historical predecessor, Section 174 of the <i>Code of Criminal "
        "Procedure, 1973</i>), law enforcement authorities are legally obligated to conduct a thorough, objective, and expeditious "
        "inquest. The central legal mandate of an inquest is not merely to establish the anatomical cause of death, but to ascertain the "
        "surrounding circumstances, reconstruct the temporal chain of events, discover the <i>modus operandi</i>, identify any underlying "
        "criminal agency, and preserve all relevant physical and digital evidence with unimpeachable integrity.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "Historically, inquest proceedings and death inquiries relied primarily on physical crime-scene examinations, immediate eyewitness "
        "depositions, and the post-mortem findings issued by forensic medical examiners. However, in the modern socio-technological era, "
        "human activity is inextricably interwoven with digital devices and telecommunications networks. Consequently, every modern death "
        "investigation generates a massive, heterogeneous trail of digital and physical data. Investigating Officers (IOs) are routinely "
        "inundated with hundreds of evidentiary artifacts, ranging from handwritten inquest diaries and statutory First Information Reports "
        "(FIRs) to multi-gigabyte mobile extraction dumps, high-definition Closed-Circuit Television (CCTV) footage, telecom Call Detail "
        "Records (CDRs), tower dump spreadsheets, bank account statements, encrypted instant-messaging archives, and digital toxicological "
        "spectroscopy reports. The cognitive burden of manually assimilating, cross-referencing, verifying, and preserving this vast "
        "multimodal corpus has outpaced traditional police investigative methodologies.",
        styles["AcademicBody"]
    ))

    # 1.2 Challenges in Unnatural Death Investigations
    story.append(page_tracker_cls("sec1_2"))
    story.append(Paragraph("1.2 Challenges in Unnatural Death Investigations", styles["SectionHeading"]))
    story.append(Paragraph(
        "Inquiries into unnatural deaths face severe operational, cognitive, and technical bottlenecks that impede the administration of "
        "justice. A rigorous analysis of police procedures and judicial inquiries reveals four fundamental challenges:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "1. <b>Extreme Evidence Heterogeneity and Multimodal Complexity:</b> Unlike standard property crimes or financial infractions "
        "where evidence is predominantly documentary or transactional, an unnatural death investigation involves radically diverse "
        "modalities. These include unstructured natural language documents (witness statements under BNSS Section 180, suicide notes, "
        "panchnamas), structured relational tables (CDR logs, IP Detail Records, banking ledger CSVs), binary visual media (crime scene "
        "photographs, video inquest recordings, optical CCTV footage), and specialized medical-legal reports (autopsy gross findings, "
        "histopathology results, viscera chemical examination reports). Each modality adheres to different syntactic formats, storage "
        "standards, and temporal granularities, creating massive data silos that defy unified manual indexing.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "2. <b>Severe Information Fragmentation and Disconnected Data Silos:</b> In conventional police administration, exhibits are "
        "processed by disparate agencies and forensic sub-laboratories operating in isolation. Mobile devices are submitted to Cyber "
        "Forensic Laboratories; biological viscera samples are dispatched to State Forensic Science Laboratories (FSL); CDR files are "
        "obtained from cellular service providers and inspected on standalone spreadsheets; while witness depositions remain bound in "
        "physical case dockets (Case Diaries). Because these evidentiary streams are never ingested into a unified, cryptographically "
        "governed platform, critical correlations—such as a suspect's cellular geolocation aligning with a CCTV timestamp or an "
        "inconsistency between a stated time of death and post-mortem lividity—are frequently overlooked.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "3. <b>Temporal Timeline Discrepancies and Contradiction Detection:</b> Establishing an accurate, second-by-second chronological "
        "timeline is essential for confirming or disproving alibis. However, manual chronological reconciliation across multiple witness "
        "narratives, cellular tower pings, digital device system clocks, and physiological estimates of time since death is notoriously "
        "error-prone. Human investigators, working under intense investigative stress and public pressure, often struggle to synthesize "
        "subtle factual contradictions across dozens of depositions transcribed over weeks or months.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "4. <b>Vulnerability of Digital Chain of Custody and Tamper Risks:</b> Digital evidence is inherently volatile, susceptible to "
        "accidental alteration, bit-rot, metadata stripping, malicious tampering, or unauthorized deletion during handling. In many "
        "jurisdictions, digital files are stored on unauthenticated network file shares or optical media without continuous cryptographic "
        "integrity proofs. Under rigorous judicial scrutiny (such as Section 63 of the <i>Bharatiya Sakshya Adhiniyam, 2023</i> or Section "
        "65B of the Indian Evidence Act), failure to demonstrate an unbroken, mathematically tamper-evident chain of custody leads to the "
        "exclusion of pivotal evidence during criminal trial proceedings.",
        styles["BulletText"]
    ))

    # 1.3 Motivation
    story.append(page_tracker_cls("sec1_3"))
    story.append(Paragraph("1.3 Motivation", styles["SectionHeading"]))
    story.append(Paragraph(
        "The motivation behind developing <b>SAKSHI</b> arises from the urgent societal and institutional imperative to modernize "
        "unnatural death investigations without succumbing to the dangerous pitfalls of unconstrained autonomous artificial intelligence. "
        "Recent advances in Natural Language Processing, Large Language Models (LLMs), and knowledge graphs have demonstrated exceptional "
        "capabilities in information extraction and relational pattern recognition. However, directly applying off-the-shelf generative AI "
        "models to criminal investigations introduces unacceptable forensic hazards. Commercial LLMs operate as probabilistic 'black "
        "boxes' prone to hallucinations—fabricating non-existent facts, inventing fictitious cellular records, or drawing speculative "
        "causal links devoid of evidentiary support.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "In a judicial inquiry concerning human life and criminal liability, an algorithmic hallucination can result in devastating "
        "consequences, including the wrongful incrimination of innocent citizens or the irreversible collapse of a prosecution. Therefore, "
        "the engineering motivation of this project is to construct a computational architecture where artificial intelligence is "
        "mathematically constrained by immutable, cryptographically verified evidence. Rather than replacing the human investigator, the "
        "system is motivated to serve as a tireless, mathematically grounded <b>investigation companion</b> that organizes chaotic multi-modal "
        "evidence, enforces tamper-evident custody, illuminates factual contradictions, and exposes critical investigative gaps, while "
        "ensuring that the human Investigating Officer remains the sole, sovereign decision-maker.",
        styles["AcademicBody"]
    ))

    # 1.4 Problem Statement
    story.append(page_tracker_cls("sec1_4"))
    story.append(Paragraph("1.4 Problem Statement", styles["SectionHeading"]))
    story.append(Paragraph(
        "Conventional unnatural death investigation workflows rely on manual, fragmented, and vulnerable procedures for handling "
        "heterogeneous evidence, resulting in severe cognitive overload, undetected factual contradictions, unindexed evidentiary gaps, "
        "and fragile digital chains of custody that fail judicial admissibility standards. Concurrently, emerging attempts to apply "
        "generative AI models to forensic investigations risk severe judicial harm due to algorithmic hallucinations, absence of source "
        "traceability, lack of cryptographic data integrity, and unauthorized predictive overreach that infringes upon statutory police "
        "prerogatives.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "To resolve this dual failure mode, there is an acute engineering necessity to design and implement an <b>evidence-first, "
        "cryptographically governed, and explainable computational companion</b>. This platform must ingest multimodal forensic evidence, "
        "enforce strict binary validation, fail-closed antivirus scanning, Write-Once-Read-Many (WORM) storage, multi-algorithm dual hashing, "
        "application-layer Object Locking, and authenticated encryption at rest, while providing an evidence-constrained reasoning "
        "framework that surfaces timelines, contradictions, and missing investigative steps with absolute source provenance and full "
        "human-in-the-loop oversight.",
        styles["AcademicBody"]
    ))

    # 1.5 Objectives of the Project
    story.append(page_tracker_cls("sec1_5"))
    story.append(Paragraph("1.5 Objectives of the Project", styles["SectionHeading"]))
    story.append(Paragraph(
        "The project is structured around clear engineering and scientific objectives designed to establish a robust, production-grade "
        "forensic foundation before enabling higher-level cognitive reasoning. These objectives are classified into currently completed "
        "modules, in-progress components, and future architectural roadmap stages, as summarized in Table 1.1.",
        styles["AcademicBody"]
    ))

    story.append(page_tracker_cls("tab1_1"))
    story.append(Paragraph("<b>Table 1.1: Formal Project Objectives Mapped to Implementation Phases</b>", styles["TableCaption"]))

    obj_table_data = [
        [Paragraph("<b>Objective ID</b>", styles["TableHeader"]), Paragraph("<b>Formal Engineering Objective</b>", styles["TableHeader"]), Paragraph("<b>Target Module / Phase</b>", styles["TableHeader"]), Paragraph("<b>Implementation Status</b>", styles["TableHeader"])],
        [Paragraph("<b>OBJ-01</b>", styles["TableCellBold"]), Paragraph("Develop secure case initiation, FIR metadata registration, and case workspace isolation", styles["TableCell"]), Paragraph("MOD-01 (Phase 1)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-02</b>", styles["TableCellBold"]), Paragraph("Implement OpenID Connect (OIDC) identity authentication and JWT cryptographic verification", styles["TableCell"]), Paragraph("MOD-02 (Phase 1)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-03</b>", styles["TableCellBold"]), Paragraph("Engineer hybrid Role-Based and Attribute-Based Access Control (RBAC/ABAC) governance", styles["TableCell"]), Paragraph("MOD-03 (Phase 1)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-04</b>", styles["TableCellBold"]), Paragraph("Enforce statutory investigation lifecycle stage transitions with formal approval gates", styles["TableCell"]), Paragraph("MOD-04 (Phase 1)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-05</b>", styles["TableCellBold"]), Paragraph("Construct multi-modal evidence intake pipeline supporting streaming uploads and chunking", styles["TableCell"]), Paragraph("MOD-05 (Phase 2)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-06</b>", styles["TableCellBold"]), Paragraph("Implement binary magic-byte inspection and MIME type sniffing to prevent extension spoofing", styles["TableCell"]), Paragraph("MOD-06 (Phase 2)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-07</b>", styles["TableCellBold"]), Paragraph("Integrate fail-closed ClamAV antivirus inspection with automated malware quarantine isolation", styles["TableCell"]), Paragraph("MOD-07 (Phase 2)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-08</b>", styles["TableCellBold"]), Paragraph("Engineer immutable POSIX-level WORM commit abstraction with pre-hash SHA-256 generation", styles["TableCell"]), Paragraph("MOD-08 (Phase 2)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-09</b>", styles["TableCellBold"]), Paragraph("Implement dual cryptographic hashing binding independent SHA-256 and SHA3-512 algorithms", styles["TableCell"]), Paragraph("MOD-09 (Phase 3)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-10</b>", styles["TableCellBold"]), Paragraph("Design application-layer WORM Object Locking with legal hold governance and retention", styles["TableCell"]), Paragraph("MOD-10 (Phase 3)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-11</b>", styles["TableCellBold"]), Paragraph("Engineer authenticated AES-256-GCM envelope encryption at rest with case-isolated keys", styles["TableCell"]), Paragraph("MOD-11 (Phase 3)", styles["TableCell"]), Paragraph("COMPLETE (Verified)", styles["TableCellBold"])],
        [Paragraph("<b>OBJ-12</b>", styles["TableCellBold"]), Paragraph("Enforce TLS 1.3 in-transit encryption and mutual authentication (mTLS) across services", styles["TableCell"]), Paragraph("MOD-12 (Phase 3)", styles["TableCell"]), Paragraph("PENDING (Next in Phase 3)", styles["TableCell"])],
        [Paragraph("<b>OBJ-13</b>", styles["TableCellBold"]), Paragraph("Implement Merkle-tree cryptographic audit ledger for mathematical non-repudiation", styles["TableCell"]), Paragraph("MOD-13 (Phase 3)", styles["TableCell"]), Paragraph("PENDING (Phase 3 Completion)", styles["TableCell"])],
        [Paragraph("<b>OBJ-14</b>", styles["TableCellBold"]), Paragraph("Architect downstream multimodal processing, OCR, entity extraction, and structured case memory", styles["TableCell"]), Paragraph("Phases 4–6", styles["TableCell"]), Paragraph("ROADMAP (Future Work)", styles["TableCell"])],
        [Paragraph("<b>OBJ-15</b>", styles["TableCellBold"]), Paragraph("Construct Knowledge Graph, Timeline Reconstruction, and Contradiction Detection engines", styles["TableCell"]), Paragraph("Phases 7–9", styles["TableCell"]), Paragraph("ROADMAP (Future Work)", styles["TableCell"])],
        [Paragraph("<b>OBJ-16</b>", styles["TableCellBold"]), Paragraph("Implement Evidence-Constrained Dual Brain reasoning (Intuition vs Discipline) with Evidence Gate", styles["TableCell"]), Paragraph("Phases 10–14", styles["TableCell"]), Paragraph("ROADMAP (Future Work)", styles["TableCell"])],
        [Paragraph("<b>OBJ-17</b>", styles["TableCellBold"]), Paragraph("Deploy Investigative Gap Discovery Engine, explainable reporting, and human review apex", styles["TableCell"]), Paragraph("Phases 15–17", styles["TableCell"]), Paragraph("ROADMAP (Future Work)", styles["TableCell"])],
    ]

    obj_table = Table(obj_table_data, colWidths=[55, 185, 105, 106])
    obj_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F294A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(obj_table)

    story.append(Spacer(1, 10))

    # 1.6 Scope of the Project
    story.append(page_tracker_cls("sec1_6"))
    story.append(Paragraph("1.6 Scope of the Project", styles["SectionHeading"]))
    story.append(Paragraph(
        "The operational scope of the SAKSHI project encompasses both production-implemented core subsystems and comprehensive "
        "architectural specifications for future analytical phases:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "• <b>In-Scope (Current Implementation):</b> The functional boundary of the current implementation encompasses the entire case "
        "initiation lifecycle, identity federation, cryptographic token validation, fine-grained access control, streaming evidence "
        "intake, binary magic-byte sniffing for all primary document/media formats (PDF, JPEG, PNG, MP4, CSV, ZIP), fail-closed ClamAV "
        "daemon socket scanning, immutable WORM commitment on the local filesystem, multi-algorithm dual hashing (SHA-256 + SHA3-512) "
        "with bit-rot detection, pluggable application-layer WORM Object Locking with retention metadata, and authenticated AES-256-GCM "
        "envelope encryption at rest with case-isolated keys and Additional Authenticated Data (AAD) binding. All in-scope modules are "
        "verified through an extensive suite of 298 automated tests.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>In-Scope (Architectural Specification & Roadmap):</b> The architectural specification defines the comprehensive 17-phase "
        "investigation pipeline, including multi-modal OCR ingestion, domain-specific legal NLP entity extraction, Structured Case Memory "
        "(SCM), forensic Knowledge Graph schemas, temporal timeline aggregation algorithms, cross-modal contradiction detection rules, the "
        "Dual Brain reasoning topology (Intuition Brain vs Discipline Brain separated by an Information Firewall), the strict Evidence "
        "Gate, statutory procedural compliance rules, and the Investigative Gap Discovery Engine.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Explicitly Out-of-Scope (Prohibited System Functions):</b> SAKSHI is strictly engineered as an investigative companion. It is "
        "explicitly out-of-scope for the system to: (1) render autonomous judicial verdicts or legal conclusions; (2) assign criminal "
        "guilt or culpability; (3) recommend the arrest or detention of any individual; (4) replace the sworn Investigating Officer; or (5) "
        "execute ungrounded predictive policing. The system serves exclusively to assist, illuminate, verify, and document.",
        styles["BulletText"]
    ))

    # 1.7 Significance of the Project
    story.append(page_tracker_cls("sec1_7"))
    story.append(Paragraph("1.7 Significance of the Project", styles["SectionHeading"]))
    story.append(Paragraph(
        "The engineering and forensic significance of SAKSHI is multidimensional. From a legal standpoint, it introduces unprecedented "
        "custodial integrity to digital evidence handling. By combining pre-hash validation, dual cryptographic hashing, WORM Object "
        "Locking, and authenticated encryption before any computational reasoning occurs, SAKSHI ensures that digital evidence presented "
        "in judicial proceedings is mathematically resilient against allegations of tampering, fabrication, or post-seizure contamination.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "From an operational policing standpoint, SAKSHI dramatically mitigates cognitive tunnel vision. In high-profile death inquiries, "
        "investigators frequently develop early subjective hypotheses (e.g., presuming suicide due to hanging), inadvertently disregarding "
        "subtle contrary indicators (such as defensive fingernail marks noted in the post-mortem report or missing financial transactions). "
        "By systematically cross-referencing all admitted exhibits against an immutable case memory, SAKSHI surfaces factual discrepancies "
        "and exposes uninvestigated leads without human cognitive bias.",
        styles["AcademicBody"]
    ))

    # 1.8 Proposed EC-MORE Paradigm
    story.append(page_tracker_cls("sec1_8"))
    story.append(Paragraph("1.8 Proposed EC-MORE Paradigm", styles["SectionHeading"]))
    story.append(Paragraph(
        "To reconcile the generative power of artificial intelligence with the uncompromising evidentiary rigor of forensic science, "
        "this project proposes the <b>Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)</b> paradigm. The foundational principle "
        "of EC-MORE is that <i>no inference, relation, or timeline event may exist within the analytical case state unless it is directly, "
        "cryptographically grounded in a verified evidence exhibit</i>.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "Under the EC-MORE paradigm, the reasoning engine is architected as an adversarial dual-cognitive topology: an <b>Intuition "
        "Brain</b> and a <b>Discipline Brain</b>. The Intuition Brain possesses high associative freedom, generating diverse exploratory "
        "hypotheses regarding possible death mechanisms (e.g., asphyxia due to ligature hanging vs manual strangulation). However, between "
        "the Intuition Brain and the case state stands an impenetrable <b>Information Firewall</b> and <b>Evidence Gate</b>. The Discipline "
        "Brain rigorously evaluates every hypothesis using formal falsification logic, checking each premise against cryptographically "
        "authenticated WORM exhibits. Hypotheses lacking evidentiary support are strictly pruned, while corroborated findings are linked "
        "directly to immutable exhibit hashes.",
        styles["AcademicBody"]
    ))

    # 1.9 Human-in-the-Loop Principle
    story.append(page_tracker_cls("sec1_9"))
    story.append(Paragraph("1.9 Human-in-the-Loop Principle", styles["SectionHeading"]))
    story.append(Paragraph(
        "A non-negotiable architectural invariant of SAKSHI is the <b>Human-in-the-Loop (HITL)</b> principle. In constitutional "
        "jurisprudence, criminal investigation and the deprivation of liberty are solemn sovereign functions vested exclusively in sworn "
        "law enforcement officers and judicial magistrates. Delegating final decision-making power to an algorithmic model is legally "
        "untenable, ethically unacceptable, and procedurally defective.",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "Within SAKSHI, artificial intelligence never executes an operational action independently. The system cannot close a case, "
        "reclassify an unnatural death inquiry into a murder charge, issue summons, or dismiss a suspect's alibi. Instead, all outputs "
        "are structured as <b>explainable evidentiary briefings</b> presented to the Investigating Officer. Every assertion displays "
        "its cryptographic source exhibit, exact paragraph citation, hash digest, and confidence interval. The human IO retains sole "
        "discretion to accept, modify, investigate further, or reject any computational suggestion.",
        styles["AcademicBody"]
    ))

    # 1.10 Limitations of Conventional Investigation Workflows
    story.append(page_tracker_cls("sec1_10"))
    story.append(Paragraph("1.10 Limitations of Conventional Investigation Workflows", styles["SectionHeading"]))
    story.append(Paragraph(
        "To clearly appreciate the transformative contribution of SAKSHI, it is essential to outline the profound limitations of existing "
        "police investigation workflows:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "1. <b>Manual Transcription and Cross-Referencing:</b> Police officers manually read hundreds of pages of case diaries and "
        "transcripts. Identifying temporal inconsistencies across multiple witness depositions requires days of tedious cross-checking, "
        "inevitably leading to human oversight.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "2. <b>Unstructured Digital Storage:</b> Digital files (CCTV videos, CDR spreadsheets, forensic reports) are stored in ad-hoc "
        "operating system folders without tamper-detection, cryptographic checksums, or unified indexing.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "3. <b>Absence of Automated Gap Detection:</b> Conventional systems possess no semantic understanding of inquest procedures. If an "
        "IO forgets to collect viscera chemical reports or neglects to obtain call records for a key contact, standard filing systems "
        "remain silent until an omission is pointed out during cross-examination in court months or years later.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "4. <b>Lack of Source Traceability:</b> Summaries prepared by investigators in police charge-sheets frequently synthesize facts "
        "without providing machine-verifiable citations to the original exhibits, making subsequent appellate review difficult.",
        styles["BulletText"]
    ))

    # 1.11 Organization of the Report
    story.append(page_tracker_cls("sec1_11"))
    story.append(Paragraph("1.11 Organization of the Report", styles["SectionHeading"]))
    story.append(Paragraph(
        "The remainder of this B.Tech academic project report is organized into the following chapters:",
        styles["AcademicBody"]
    ))

    story.append(Paragraph(
        "• <b>Chapter 2 — Literature Survey:</b> Conducts an exhaustive academic review of 8 foundational peer-reviewed studies across "
        "explainable AI, digital forensic integrity, knowledge graphs, timeline reconstruction, and human-AI governance, concluding with "
        "comparative matrices and an in-depth research gap analysis.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Chapter 3 — System Analysis and Design:</b> Details the complete system requirements (12 functional, 8 non-functional), "
        "system actors, the overall multi-tier architecture diagram, the 17-phase pipeline, Phase 1–3 module architectures, defense-in-depth "
        "security, and comprehensive UML models (Use Case, DFD Levels 0/1, Class, Sequence, Activity, Component, and Deployment).",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Chapter 4 — Implementation:</b> Provides exhaustive implementation documentation for all 11 completed modules (MOD-01 to "
        "MOD-11), technology stacks, database schemas, 15 complete algorithmic pseudocode specifications with security considerations, "
        "pipeline flowcharts, REST API contracts, and forensic interface placeholders.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Chapter 5 — Testing and Results:</b> Explains the multi-tier testing methodology, unit, integration, security, and regression "
        "testing frameworks, presenting the empirical test result matrix confirming 298 automated tests passed with zero failures.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Chapter 6 — Security, Limitations and Future Work:</b> Analyzes the cryptographic defense-in-depth architecture, documents "
        "current system limitations, and outlines the phased research roadmap for future multimodal and cognitive AI modules.",
        styles["BulletText"]
    ))

    story.append(Paragraph(
        "• <b>Conclusion & References:</b> Summarizes project accomplishments, followed by formal academic references and comprehensive "
        "technical appendices (API catalogs, database schemas, test matrices, data models, and abbreviations).",
        styles["BulletText"]
    ))

    story.append(PageBreak())
    return story
