l the build # SAKSHI: System Pipeline & Subsystem Architecture
## An Evidence-Gated AI Reasoning Agent for Death Investigation

---

## 1. Architectural Evolution & Foundational Context

### 1.1 The Shift from Legacy Conceptualization to Evidence-Gated Discipline

In early investigative AI frameworks and legacy presentation concepts, investigative pipelines were typically modeled as linear extraction and reconstruction systems:

```
[LEGACY CONCEPTUAL PIPELINE]
Evidence Ingestion ──► Text Extraction ──► Entity Extraction ──► Relationship Mapping ──► MO Reconstruction ──► Suspect Output
```

This legacy paradigm carries fatal forensic vulnerabilities:
- **Heuristic Bias & Profiling:** Attempting to reconstruct "Modus Operandi" (MO) or correlate cases based on behavioral similarities inevitably invites confirmation bias and subjective profiling.
- **Uncontrolled Hallucination:** Unconstrained generative models easily invent narrative bridges and elevate speculative hypotheses into factual assertions.
- **Premature Cognitive Closure:** Prematurely ranking or implicating suspects closes alternative lines of inquiry, risking catastrophic investigative failure.

**SAKSHI fundamentally replaces this paradigm with an Evidence-Gated, Two-Brain Architecture:**

```
[SAKSHI EVIDENCE-GATED ARCHITECTURE]
Evidence ──► Extraction ──► Structured Case Memory ──► Context Retrieval
                                                               │
                                                               ▼
                                                    ┌─────────────────────┐
                                                    │   INTUITION BRAIN   │
                                                    └──────────┬──────────┘
                                                               │ Candidate Insight (Isolated)
                                                               ▼
                                                    ┌─────────────────────┐
                                                    │  DISCIPLINE BRAIN   │
                                                    └──────────┬──────────┘
                                                               │
                                                               ▼
                                                       EVIDENCE GATE
                                                               │
                                       ┌───────────────────────┼───────────────────────┐
                                       ▼                       ▼                       ▼
                                   VERIFIED               UNVERIFIED             CONTRADICTORY
                                       │                       │                       │
                                       └───────────────────────┴───────────────────────┘
                                                               │
                                                               ▼
                                                    INVESTIGATION GAPS
                                                               │
                                                               ▼
                                                  EVIDENCE-BACKED NEXT STEPS
                                                               │
                                                               ▼
                                                      HUMAN INVESTIGATOR
                                                               │
                                                               ▼
                                                         NEW EVIDENCE
                                                               │
                                                               └────────► CASE MEMORY UPDATE
```

### 1.2 The Cardinal Anti-Suspect Rule
> **SAKSHI MUST NEVER:**
> - Name, rank, recommend, implicate, or predict a suspect.
> - Calculate guilt probabilities or assign culpability scores.
> - Conduct behavioral, personality, or psychological profiling.
> - Link cases based on appearance, MO, or narrative likeness.
> 
> **SAKSHI'S SOLE PURPOSE:** Serve as an objective evidentiary clerk and cognitive co-pilot: organizing multi-modal evidence, constructing timeline graphs, checking claim consistency, exposing contradictions, surfacing investigative gaps, and formulating verifiable, evidence-backed next steps for the human investigator.

---

## 2. Master System Pipeline

The master pipeline represents the complete, closed-loop operational flow of Sakshi from case creation to ongoing field evidence integration.

```mermaid
flowchart TD
    subgraph S_INIT["1. Case Initiation"]
        INIT["FIR Intake & Secure Workspace Creation"]
    end

    subgraph S_INGEST["2. Evidence Ingestion"]
        INGEST["Multi-Modal Ingestion:\nPDFs, Scans, Photos, Voice Notes, FSL Lab Reports, Digital CDRs"]
    end

    subgraph S_PRE["3. Preprocessing"]
        PRE["OCR, Whisper Speech-to-Text, Language Detection, Text Normalization, Metadata Extraction"]
    end

    subgraph S_PROC["4. Evidence Processing"]
        PROC["Legal NER, Event Extraction, ISO 8601 Temporal Normalization, Hard-ID Extraction, Entity Linkage"]
    end

    subgraph S_MEM["5. Structured Case Memory"]
        MEM["Case Database (Postgres) | Knowledge Graph (Neo4j)\nTimeline Engine | Verification Status Ledger"]
    end

    subgraph S_RETR["6. Context Retrieval"]
        RETR["Subgraph Context Assembly & Temporal Interval Slicing"]
    end

    subgraph S_TWIN["7. Two-Brain Reasoning Engine"]
        subgraph IB_BOX["Intuition Brain (LLM Sandbox)"]
            IB["Pattern Recognition, Anomaly Spotting,\nHypothesis & Candidate Insight Generation"]
        end
        
        FIREWALL{{"Mandatory Informational Firewall\nDirect UI Access Prohibited"}}
        
        subgraph DB_BOX["Discipline Brain (Auditor)"]
            DB["Atomic Claim Decomposition, Document Hash Verification,\nExact Span Matching, Entailment & Sufficiency Check"]
        end
        
        IB --> FIREWALL --> DB
    end

    subgraph S_GATE["8. Evidence Gate"]
        GATE{"Grounding Ratio == 1.0\n& Forensically Consistent?"}
        V_OK["VERIFIED"]
        V_UN["UNVERIFIED"]
        V_CT["CONTRADICTORY"]
        GATE -- Grounding = 1.0 --> V_OK
        GATE -- Incomplete --> V_UN
        GATE -- Conflict --> V_CT
    end

    subgraph S_GAP["9. Gap & Next Steps Engine"]
        GAP["Investigation Gap Detection:\nMissing Evidence, Missing Procedures, Uncorroborated Alibis"]
        STEPS["Evidence-Backed Next Steps:\nLawful Inquiries, Sec 91 Notices, Forensic Requisitions"]
        GAP --> STEPS
    end

    subgraph S_DASH["10. Investigator Workspace"]
        DASH["Investigator Dashboard:\nTimeline Explorer, Contradiction Matrix, Gap Board, Citation Viewer"]
    end

    subgraph S_HITL["11. Human-in-the-Loop & Feedback"]
        REV["Human Deliberation & Verification"]
        ACT["Human Field Action"]
        NEW_EVD["Collection of New Supplementary Evidence"]
        REV --> ACT --> NEW_EVD
    end

    %% Pipeline Connections
    INIT --> INGEST --> PRE --> PROC --> MEM --> RETR --> IB_BOX
    DB_BOX --> GATE
    V_OK & V_UN & V_CT --> GAP
    STEPS --> DASH
    DASH --> REV
    NEW_EVD -.->|Closed-Loop Feedback| INGEST

    classDef init fill:#1e293b,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef mem fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef brain fill:#311042,stroke:#a21caf,stroke-width:2px,color:#fae8ff;
    classDef gate fill:#064e3b,stroke:#059669,stroke-width:2px,color:#ecfdf5;
    classDef human fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    
    class S_INIT,S_INGEST,S_PRE,S_PROC init;
    class S_MEM,S_RETR mem;
    class IB_BOX brain;
    class DB_BOX,S_GATE,V_OK,V_UN,V_CT gate;
    class S_GAP,S_DASH,S_HITL,REV,ACT,NEW_EVD human;
```

---

## 3. Dedicated Subsystem Pipelines

---

### PIPELINE 1 — Evidence Ingestion Pipeline

The Evidence Ingestion pipeline establishes the statutory chain of custody and prepares multi-modal inputs for deterministic processing.

```mermaid
flowchart TD
    IN1["Raw Evidence Input:\nFIR, Scanned PDF, Panchnama Photo, Voice Note, FSL Report, CDR/SDR"] --> IN2["Input Validation & MIME Magic Byte Inspection"]
    IN2 --> IN3["File Type Classification & Sanitization (ClamAV Scan)"]
    IN3 --> IN4["Dual-Hashing Engine:\nCalculate Streaming SHA-256 and SHA-3-512 Checksums"]
    
    IN4 --> STORE_RAW[("Raw Evidence Store\nMinIO WORM Vault (Object Lock Compliance)")]
    IN4 --> STORE_AUDIT[("Append-Only Audit Store\nCommit File Hash Lineage to Immudb")]
    
    STORE_RAW --> ROUTE{"Media Routing"}
    ROUTE -- Document Scan / Photo --> OCR["Multi-Modal OCR Engine\n(PaddleOCR / Tesseract 5 / LayoutLM)"]
    ROUTE -- Voice / Audio Recording --> ASR["Bilingual Speech-to-Text\n(Fine-Tuned Faster-Whisper: Malayalam + English)"]
    ROUTE -- Structured CSV / XLS / CDR --> TAB["Tabular Data Parser\n(Cell ID, Tower Coordinates, IMSI/MSISDN Mapper)"]
    
    OCR & ASR & TAB --> NORM["Language Detection & Character Normalization\n(Unicode Sanitization, Noise Removal)"]
    NORM --> META["Metadata Extraction:\nEXIF, Device IDs, Timestamps, Ingesting Officer ID"]
    META --> OUT_PROC[("Processed Evidence Store\nNormalized UTF-8 Streams with Bounding Coordinates")]

    classDef store fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef proc fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    class STORE_RAW,STORE_AUDIT,OUT_PROC store;
    class IN1,IN2,IN3,IN4,ROUTE,OCR,ASR,TAB,NORM,META proc;
```

---

### PIPELINE 2 — Information Extraction Pipeline

Converts unstructured and semi-structured text into normalized, typed factual tuples while maintaining strict source attribution.

```mermaid
flowchart TD
    IN_P2["Processed Evidence Stream (UTF-8)"] --> NLP["Legal NLP Preprocessing Pipeline\n(Tokenization, Sentence Segmentation, Lemmatization)"]
    
    NLP --> E_NER["Entity Extraction:\nPersons, Officials, Weapons, Vehicles, Anatomical Sites (Legal-BERT)"]
    NLP --> E_EVT["Event Extraction:\nAtomic Action Tuples: Subject, Predicate, Object"]
    NLP --> E_TEMP["Temporal Extraction & Normalization:\nRelative expressions converted to ISO 8601 intervals (Duckling)"]
    NLP --> E_LOC["Location Extraction:\nScene of Crime, Transit Points, Cell Tower Latitude/Longitude"]
    NLP --> E_OBJ["Object & Physical Property Extraction:\nLigature materials, toxic substances, biological samples"]
    NLP --> E_DIGI["Digital Artifact Extraction:\nCall records, SMS timestamps, CCTV camera IDs, IP addresses"]
    NLP --> E_HARD["Hard Identifier Extraction & Verification:\nMSISDN (E.164), IMEI (Luhn check), Vehicle Plates, Bank Accounts"]
    
    E_NER & E_EVT & E_TEMP & E_LOC & E_OBJ & E_DIGI & E_HARD --> REL["Relationship Extraction & Provenance Attribution:\n(Entity A) -[RELATION {evidence_id, page, line}]-> (Entity B)"]
    REL --> FACTS["Structured Facts Ledger\n(Deterministic JSON-LD Tuples)"]

    classDef ext fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef out fill:#064e3b,stroke:#34d399,stroke-width:1.5px,color:#fff;
    class IN_P2,NLP,E_NER,E_EVT,E_TEMP,E_LOC,E_OBJ,E_DIGI,E_HARD,REL ext;
    class FACTS out;
```

---

### PIPELINE 3 — Structured Case Memory Pipeline

Assembles structured facts into an interconnected, multi-model case memory where every entity and edge carries immutable provenance.

```mermaid
flowchart TD
    FACTS_IN["Structured Facts Ledger"] --> ROUTER["Case Memory Synchronization Router"]
    
    ROUTER --> S_ENT["Entity Store (PostgreSQL 16):\nCanonical Person & Organization Registry"]
    ROUTER --> S_EVT["Event Store (PostgreSQL 16):\nAtomic Actions & Spatio-Temporal Bounds"]
    ROUTER --> S_EVD["Evidence Store (PostgreSQL 16):\nDocument Registry & SHA-256 Checksums"]
    ROUTER --> S_REL["Relationship Store (PostgreSQL 16):\nDirect Links & Verification Status Ledgers"]
    
    ROUTER --> KG["Knowledge Graph (Neo4j Enterprise Edition):\nProperty Graph mapping Persons, Statements, Events, Places, & Items"]
    ROUTER --> TL_ENG["Chronological Timeline Engine:\nContinuous Sequence Mapping & Interval Algebra Solver"]
    
    S_ENT & S_EVT & S_EVD & S_REL & KG & TL_ENG --> MEM_OUT["STRUCTURED CASE MEMORY"]

    subgraph PROVENANCE["Every Fact in Memory Retains"]
        P1["• Evidence ID (UUID)"]
        P2["• Source Document Name & Page/Line Coordinate"]
        P3["• Recording Timestamp & Ingestion Checksum"]
        P4["• Cryptographic Provenance Hash Chain"]
        P5["• Verification Status: VERIFIED | UNVERIFIED | CONTRADICTION"]
    end
    MEM_OUT --- PROVENANCE

    classDef store fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef prov fill:#0f172a,stroke:#34d399,stroke-width:1.5px,color:#fff;
    class S_ENT,S_EVT,S_EVD,S_REL,KG,TL_ENG,MEM_OUT store;
    class PROVENANCE,P1,P2,P3,P4,P5 prov;
```

---

### PIPELINE 4 — Timeline Construction & Contradiction Detection Pipeline

Maps temporal events, verifies spatial transit velocity feasibility, and surfaces factual clashes without automated subjective resolution.

```mermaid
flowchart TD
    EVTS["Extracted Events & Timestamps\n(Witness Statements, Inquest Panchnama, Post-Mortem PMI, CDR Tower Dumps)"] --> TNORM["Temporal Normalization Engine:\nConvert vague references ('after tea') into bounded ISO 8601 intervals"]
    TNORM --> TVAL["Timestamp & Timezone Validation"]
    TVAL --> TORDER["Event Ordering & Interval Logic (Allen's Interval Temporal Logic)"]
    
    TORDER --> SPATIAL["Spatial Feasibility Solver:\nCalculate required transit velocity between consecutive locations"]
    
    SPATIAL --> CONFLICT_SCAN{"Conflict Detected?"}
    
    CONFLICT_SCAN -- Velocity Exceeds Physical Limits --> VEL_CLASH["Flag: Impossible Transit Velocity\n(e.g., 45 km traveled in 5 minutes)"]
    CONFLICT_SCAN -- Incompatible Statements --> STMT_CLASH["Flag: Statement Discrepancy\n(Witness A asserts Presence vs CDR Tower Latch)"]
    CONFLICT_SCAN -- Forensic vs Statement Clash --> MED_CLASH["Flag: Forensic Refutation\n(Witness claims blunt trauma vs PM asphyxia finding)"]
    
    VEL_CLASH & STMT_CLASH & MED_CLASH --> ALERT["CONTRADICTION ALERT GENERATED\n(Displays both conflicting sources with complete provenance)"]
    
    CONFLICT_SCAN -- Clean Sequence --> TL_OUT["Case Chronological Timeline\nT1 ──► T2 ──► T3 ──► T4 ──► T5"]

    subgraph NON_RESOLUTION["Rule of Non-Resolution"]
        NR["SAKSHI NEVER AUTOMATICALLY DECIDES WHICH WITNESS IS TRUTHFUL.\nBoth accounts are preserved side-by-side for human judicial evaluation."]
    end
    ALERT --- NON_RESOLUTION

    classDef proc fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef alert fill:#7f1d1d,stroke:#f87171,stroke-width:1.5px,color:#fff;
    classDef out fill:#064e3b,stroke:#34d399,stroke-width:1.5px,color:#fff;
    class EVTS,TNORM,TVAL,TORDER,SPATIAL,CONFLICT_SCAN proc;
    class VEL_CLASH,STMT_CLASH,MED_CLASH,ALERT alert;
    class TL_OUT,NON_RESOLUTION,NR out;
```

---

### PIPELINE 5 — Intuition Brain (Discovery Layer)

Operates inside an isolated informational sandbox to generate candidate hypotheses without direct access to the investigator.

```mermaid
flowchart TD
    MEM_IN["Structured Case Memory"] --> RETR["Context Retrieval Engine"]
    RETR --> PACKET["Relevant Evidence Subgraph &\nChronological Timeline Slices"]
    
    PACKET --> LLM["Sovereign Air-Gapped LLM\n(Local Llama-3-70B via vLLM)"]
    
    subgraph COGNITIVE_TASKS["Constrained Cognitive Tasks"]
        T1["Pattern Recognition across Statements"]
        T2["Contextual Understanding of Timeline Friction"]
        T3["Missing Information & Procedural Omission Detection"]
        T4["Candidate Contradiction Identification"]
        T5["Candidate Hypothesis Formulation"]
    end
    LLM --- COGNITIVE_TASKS
    
    COGNITIVE_TASKS --> PAYLOAD["CandidateInsightPayload (JSON Structure):\n{insight_id, hypothesis_summary, candidate_claims: [...]}"]
    
    subgraph FIREWALL["MANDATORY INFORMATIONAL FIREWALL"]
        BLOCK["CONTAINMENT ENFORCEMENT:\nCandidate output MUST NOT directly reach the investigator.\nDirect UI routing is physically disabled."]
    end
    PAYLOAD --> BLOCK
    BLOCK --> NEXT_BRAIN["Pass to Discipline Brain for Verification"]

    classDef mem fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef brain fill:#311042,stroke:#a21caf,stroke-width:2px,color:#fae8ff;
    classDef wall fill:#7f1d1d,stroke:#f87171,stroke-width:2px,color:#fff;
    class MEM_IN,RETR,PACKET mem;
    class LLM,COGNITIVE_TASKS,T1,T2,T3,T4,T5,PAYLOAD brain;
    class FIREWALL,BLOCK wall;
```

---

### PIPELINE 6 — Discipline Brain (Verification Engine)

Decomposes candidate insights into atomic propositions and executes rigorous documentary verification.

```mermaid
flowchart TD
    CAND_IN["Candidate Insight Payload Received"] --> DECOMP["Atomic Claim Decomposer:\nBreaks compound assertions into discrete tuples (S, P, O, Context)"]
    
    DECOMP --> RETR_EVD["Evidence Retrieval Engine:\nFetches primary source file referenced in claim"]
    
    RETR_EVD --> CHK_PROV["Evidence Provenance & Hash Check:\nVerify source file SHA-256 against registered ingestion hash"]
    
    CHK_PROV --> CHK_SRC["Source Verification:\nConfirm author identity, official designation, and document category"]
    
    CHK_SRC --> CHK_SPAN["Text Span Matching & NLI Entailment:\nLocate exact OCR sentence span and test logical entailment (DeBERTa-MNLI)"]
    
    CHK_SPAN --> CHK_CONSIST["Forensic Consistency Check:\nVerify that claim does not clash with objective post-mortem ground truth"]
    
    CHK_CONSIST --> CHK_SUFF["Evidence Sufficiency Evaluation:\nCompute Grounding Ratio = (Grounded Claims / Total Claims)"]
    
    CHK_SUFF --> OUT_GATE["Dispatch to Evidence Gate with Full Grounding Dossier"]

    classDef proc fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef gate fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    class CAND_IN,DECOMP,RETR_EVD,CHK_PROV,CHK_SRC,CHK_SPAN,CHK_CONSIST,CHK_SUFF proc;
    class OUT_GATE gate;
```

---

### PIPELINE 7 — Evidence Gate Pipeline

The deterministic decision gate that sorts candidate claims into verified facts, unverified leads, or contradictions.

```mermaid
flowchart TD
    CLAIM["Candidate Atomic Claim Received"] --> Q1{"Is evidence\ntraceable to primary\ndocument hash?"}
    
    Q1 -- NO --> REJ["UNVERIFIED / REJECT\n(Missing or Incompatible Source Citation)"]
    
    Q1 -- YES --> Q2{"Is evidence\nsufficient to prove\nproposition?"}
    
    Q2 -- NO --> UNV["MARK UNVERIFIED\n(Extrapolated Inference or Single Uncorroborated Account)"]
    
    Q2 -- YES --> Q3{"Are there direct\ncontradictions with established\nforensic ground truth?"}
    
    Q3 -- YES --> CONTR["MARK CONTRADICTORY\n(Highlight Clash in Contradiction Matrix)"]
    
    Q3 -- NO --> VER["MARK VERIFIED\n(Grounding Ratio = 1.0)"]

    subgraph PRESENTATION_ROUTING["Investigator Interface Routing"]
        VER --> P_VER["Verified Facts Board\n(Click-to-Source Highlight Enabled)"]
        UNV --> P_UNV["Unverified Leads / Gap Board\n(Prompts Field Corroboration)"]
        CONTR --> P_CONTR["Contradiction Matrix\n(Side-by-Side Resolution Interface)"]
    end

    classDef gate fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef pass fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef warn fill:#78350f,stroke:#fbbf24,stroke-width:2px,color:#fff;
    classDef fail fill:#7f1d1d,stroke:#f87171,stroke-width:2px,color:#fff;
    class Q1,Q2,Q3 gate;
    class VER,P_VER pass;
    class UNV,P_UNV,CONTR,P_CONTR warn;
    class REJ fail;
```

---

### PIPELINE 8 — Investigative Gap Detection Pipeline

Identifies missing evidence, procedural voids, and unverified testimonies, synthesizing lawful next steps without accusing individuals.

```mermaid
flowchart TD
    subgraph INPUTS["Case Memory Inputs"]
        M1["Structured Case Memory"]
        M2["Verified Facts Registry"]
        M3["Unverified Statements"]
        M4["Chronological Timeline"]
        M5["Contradiction Records"]
    end

    INPUTS --> ENGINE["Missing Evidence & Procedural Analysis Engine"]
    
    subgraph SCAN_TYPES["Diagnostic Gap Scanners"]
        S1["Alibi Corroboration Void Scanner"]
        S2["Statutory Forensic Protocol Void Scanner"]
        S3["Timeline Blackout Scanner (> 60 mins unrecorded)"]
        S4["Telecom Corroboration Void Scanner"]
    end
    ENGINE --> SCAN_TYPES
    
    SCAN_TYPES --> GAP_OUT["Identified Investigative Gaps:\n- Gap G1: Victim's 90-minute window prior to PMI unverified\n- Gap G2: Suspect alibi phone lacks Tower CDR corroboration\n- Gap G3: FSL viscera dispatch receipt missing in vault"]
    
    GAP_OUT --> STEPS["Evidence-Backed Next Steps Generator:\n- Requisition Cell Tower CDR via Sec 91 CrPC/BNSS Notice\n- Dispatch requisition for FSL chemical analysis status\n- Summon commercial corridor CCTV for interval 21:00-22:30"]

    subgraph PROHIBITION["Explicit Safety Constraint"]
        WARN["THE SYSTEM MUST NEVER SAY:\n'Person X is lying' OR 'Person X is probably guilty'.\nIt suggests only what evidence/information must be collected."]
    end
    STEPS --- PROHIBITION

    classDef inp fill:#1e293b,stroke:#64748b,stroke-width:1px,color:#fff;
    classDef eng fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef gap fill:#78350f,stroke:#fbbf24,stroke-width:1.5px,color:#fff;
    classDef out fill:#064e3b,stroke:#34d399,stroke-width:1.5px,color:#fff;
    class INPUTS,M1,M2,M3,M4,M5 inp;
    class ENGINE,SCAN_TYPES,S1,S2,S3,S4 eng;
    class GAP_OUT gap;
    class STEPS,PROHIBITION,WARN out;
```

---

### PIPELINE 9 — Cross-Case Hard-Identifier Linkage Pipeline

Restricts cross-case correlations strictly to machine-verifiable tokens, permanently blocking behavioral and profiling attributes.

```mermaid
flowchart TD
    CASE_A["Active Case A Ingestion"] --> EXTRACT_A["Entity & Attribute Extraction"]
    
    subgraph FIREWALL["The Cross-Case Safeguard Firewall"]
        direction TB
        PROHIBIT["STRICTLY PROHIBITED (DROPPED AT KERNEL LEVEL):\n❌ Behavioral Similarity\n❌ Physical Appearance / Likeness\n❌ Personality Traits\n❌ Modus Operandi (MO)\n❌ Demographic / Geographic Profiling\n❌ Narrative / Semantic Similarity"]
        ALLOW["AUTHORIZED MACHINE-VERIFIABLE IDENTIFIERS ONLY:\n✔ Phone Number (E.164 Format)\n✔ Device IMEI (15-Digit Luhn Validated)\n✔ Vehicle Registration Plate (RTO Standardized)\n✔ Bank Account Number + IFSC / UPI VPA"]
    end
    
    EXTRACT_A --> PROHIBIT
    PROHIBIT --> DROP["Purged Permanently: Zero Cross-Case Indexing"]
    
    EXTRACT_A --> ALLOW
    ALLOW --> NORM["Normalization & Salted Hashing"]
    
    NORM --> EXACT_MATCH["Exact-Match Deterministic Index Query"]
    
    CASE_B[("Cross-Case Hard-ID Index\n(Multi-Jurisdiction Database)")] --> EXACT_MATCH
    
    EXACT_MATCH --> RESULT{"Exact Match Found?"}
    RESULT -- No --> NO_HIT["No Hard-Identifier Cross-Case Association"]
    RESULT -- Yes --> HIT["Generate Linkage Record:\n'MACHINE-VERIFIABLE IDENTIFIER MATCH FOUND'\n(Device IMEI 8642010... matched with Case CR-2024-4112)"]
    
    HIT --> AUDIT["Commit Cross-Case Query & Alert to Merkle Audit Trail"]

    subgraph NOMENCLATURE["Strict Nomenclature Constraint"]
        N_RULE["OUTPUT MUST BE: 'MACHINE-VERIFIABLE IDENTIFIER MATCH'\nOUTPUT MUST NEVER BE: 'SUSPECT MATCH'"]
    end
    HIT --- NOMENCLATURE

    classDef danger fill:#7f1d1d,stroke:#f87171,stroke-width:2px,color:#fff;
    classDef safe fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef core fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    class PROHIBIT,DROP danger;
    class ALLOW,NORM,HIT,AUDIT,NOMENCLATURE,N_RULE safe;
    class CASE_A,EXTRACT_A,EXACT_MATCH,CASE_B,RESULT,NO_HIT core;
```

---

### PIPELINE 10 — Legal / Procedural Rule Engine Pipeline

A deterministic, non-LLM subsystem enforcing compliance with statutory criminal procedure codes and forensic preservation deadlines.

```mermaid
flowchart TD
    STATE["Case State Transition / New Artifact Added"] --> ENGINE["Deterministic Rule Engine Core (Python/OPA)"]
    
    subgraph RULE_LIB["Statutory Rule Base (CrPC / BNSS & IEA / BSA)"]
        R1["Rule Inquest-174: Verification of Inquest Panchnama Submission"]
        R2["Rule PM-Requisition: Post-Mortem Medical Report Association"]
        R3["Rule Sec-65B/63: Digital Evidence Seizure Hash Certificate"]
        R4["Rule FSL-Viscera: Chemical Analysis Sample Dispatch within 72h"]
        R5["Rule Remand-24h: Statutory Custody Remand Limits"]
    end
    ENGINE --> RULE_LIB
    
    RULE_LIB --> EVAL{"Evaluate State Against Statutory Deadlines & Rules"}
    
    EVAL -- Mandatory Condition Met --> COMPL["Mark Compliant:\nAttach Proof Evidence ID to Milestone"]
    EVAL -- Active Clock Running --> TRACK["Active Countdown Tracker:\nDisplay Remaining Hours to Deadline"]
    EVAL -- Deadline Expired / Step Missing --> BREACH["PROCEDURAL BREACH ALERT:\nEscalate to Case Dashboard & Supervisory Officer"]
    
    COMPL & TRACK & BREACH --> AUDIT["Commit Rule Evaluation to Append-Only Audit Trail"]

    subgraph NON_LLM["Non-LLM Guarantee"]
        G_RULE["100% DETERMINISTIC EXECUTION:\nThe Generative LLM is physically prohibited from inventing or altering legal requirements."]
    end
    ENGINE --- NON_LLM

    classDef eng fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef pass fill:#064e3b,stroke:#34d399,stroke-width:1.5px,color:#fff;
    classDef warn fill:#78350f,stroke:#fbbf24,stroke-width:1.5px,color:#fff;
    classDef alert fill:#7f1d1d,stroke:#f87171,stroke-width:1.5px,color:#fff;
    class STATE,ENGINE,RULE_LIB,EVAL,NON_LLM,G_RULE eng;
    class COMPL pass;
    class TRACK warn;
    class BREACH alert;
```

---

### PIPELINE 11 — Reasoning & Court Audit Trail Pipeline

Captures an append-only, tamper-evident record of all system operations, model reasoning states, and investigator decisions.

```mermaid
flowchart LR
    subgraph STAGES["Every Pipeline Stage Commits to Audit"]
        S1["Evidence Ingested\n(File Hash & Metadata)"]
        S2["Preprocessing & Extraction\n(OCR/NER Tokens)"]
        S3["AI Operation\n(Prompt, Context, Model Version)"]
        S4["Evidence Gate\n(Evaluation & Grounding Ratio)"]
        S5["Investigator Action\n(Review, Override, Acceptance)"]
    end

    subgraph MERKLE["Append-Only Merkle Ledger Engine"]
        LEAF["Merkle Leaf Computation:\nSHA-256(Event Payload + Previous Leaf Hash + UTC Timestamp)"]
        LEDGER[("Immudb Cryptographic Ledger\n(WORM Storage Array)")]
        LEAF --> LEDGER
    end

    subgraph DELIVERABLES["Court-Admissible Outputs"]
        PROOF["Cryptographic Consistency Proof"]
        CERT["Statutory Section 65B IEA / Section 63 BSA\nElectronic Record Hash Certificate (Signed PDF)"]
    end

    STAGES --> LEAF
    LEDGER --> PROOF
    LEDGER --> CERT

    subgraph METADATA_FIELDS["Audit Record Fields"]
        F1["• Timestamp (UTC)"]
        F2["• User Identity & Role"]
        F3["• Evidence ID & Checksum"]
        F4["• Model / Rule Engine Version"]
        F5["• Claim & Verification Result"]
        F6["• Human Officer Action & Justification"]
    end
    LEDGER --- METADATA_FIELDS

    classDef stage fill:#1e293b,stroke:#64748b,stroke-width:1px,color:#fff;
    classDef merkle fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef out fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    class STAGES,S1,S2,S3,S4,S5 stage;
    class MERKLE,LEAF,LEDGER merkle;
    class DELIVERABLES,PROOF,CERT,METADATA_FIELDS,F1,F2,F3,F4,F5,F6 out;
```

---

### PIPELINE 12 — Human-in-the-Loop Architecture Pipeline

Ensures the Investigating Officer remains the ultimate statutory decision-maker, using Sakshi strictly for evidence organization and reasoning support.

```mermaid
flowchart TD
    AI["AI Reasoning & Verification Engine"] --> GATE["Evidence Gate"]
    GATE --> DASH["Investigator Workspace Dashboard"]
    
    subgraph HUMAN_COGNITION["Human Investigator Prerogative"]
        DASH --> REV_FACTS["Inspect Verified Facts & Source PDF Spans"]
        DASH --> REV_CONTR["Analyze Factual Contradictions in Matrix"]
        DASH --> REV_GAPS["Evaluate Missing Evidence & Suggested Steps"]
        
        REV_FACTS & REV_CONTR & REV_GAPS --> DECIDE{"IO Deliberation & Decision"}
        
        DECIDE -- Accept Step --> ACT_ACC["Adopt Suggested Next Step"]
        DECIDE -- Defer Step --> ACT_DEF["Defer / Reject Step\n(Mandatory Statutory Justification Recorded)"]
        DECIDE -- Formulate Custom --> ACT_CUST["Define Custom Field Inquiry"]
    end

    subgraph FIELD["Statutory Field Operations"]
        ACT_ACC & ACT_CUST --> EXEC["Execute Field Investigation:\n- Issue Sec 91 CrPC/BNSS Notices\n- Re-interrogate Witnesses on Contradictions\n- Seize Supplementary CCTV / Forensic Items"]
        EXEC --> NEW_DATA["Collection of New Primary Evidence"]
    end

    NEW_DATA -.->|Upload to Ingestion Vault| INGEST["Evidence Ingestion Pipeline"]
    INGEST -.->|Trigger Dynamic Re-computation| MEM_UPD["Case Memory & Graph Update"]
    ACT_DEF -.->|Commit Reason to Ledger| AUDIT[("Append-Only Audit Ledger")]

    classDef ai fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef human fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef field fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    class AI,GATE ai;
    class HUMAN_COGNITION,DASH,REV_FACTS,REV_CONTR,REV_GAPS,DECIDE,ACT_ACC,ACT_DEF,ACT_CUST human;
    class FIELD,EXEC,NEW_DATA,INGEST,MEM_UPD,AUDIT field;
```

---

## 4. Cross-Cutting Security Overlay

Security is not an endpoint or perimeter wrapper; it spans the **entire depth** of the Sakshi architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CROSS-CUTTING SECURITY ARCHITECTURE                  │
├────────────────────────────────────────────────────────────────────────┤
│ 1. ACCESS & IDENTITY GOVERNANCE                                        │
│    - Multi-Factor Authentication: FIDO2 Hardware Key + Biometric OTP   │
│    - Role-Based (RBAC) & Attribute-Based (ABAC) Access Control         │
│    - Principle of Least Privilege: Access scoped strictly by Case ID   │
├────────────────────────────────────────────────────────────────────────┤
│ 2. CRYPTOGRAPHIC DATA INTEGRITY & ENCRYPTION                           │
│    - Ingestion Dual-Hashing: SHA-256 + SHA-3-512 streaming checksums   │
│    - Storage at Rest: AES-256-GCM Envelope Encryption (KMS Key/Case)   │
│    - Data in Flight: TLS 1.3 with Perfect Forward Secrecy & mTLS       │
│    - WORM Storage: S3 Compliance Mode Object Lock (Zero Alteration)    │
├────────────────────────────────────────────────────────────────────────┤
│ 3. COGNITIVE ENGINE & MODEL CONTAINMENT                                │
│    - Air-Gapped Sovereign Deployment: No external internet egress      │
│    - Local Open-Source Models: vLLM (Llama-3-70B) & Faster-Whisper     │
│    - Stateless Model Inference: Zero prompt caching / memory leak      │
│    - Informational Firewall: LLM output blocked from direct UI exposure │
├────────────────────────────────────────────────────────────────────────┤
│ 4. STATUTORY AUDITABILITY & DISASTER RECOVERY                          │
│    - Append-Only Merkle Tree Ledger: Immudb tamper-evident storage     │
│    - Section 65B IEA / Section 63 BSA Automated Hash Certification     │
│    - Multi-Site Encrypted Backups & Disaster Recovery Snapshots        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Storage Overlay

Sakshi distributes case intelligence across seven distinct datastores, establishing clear boundaries between authoritative records and acceleration layers:

```
[RAW EVIDENCE BINARIES]
          │
          ▼
┌───────────────────────────────────────────────┐
│ DS-1: RAW EVIDENCE OBJECT STORE               │
│ MinIO S3 Vault (WORM Compliance Object Lock)  │
└───────────────────────┬───────────────────────┘
                        │ OCR & Audio Processing
                        ▼
┌───────────────────────────────────────────────┐
│ DS-2: PROCESSED EVIDENCE STORE                │
│ Normalized UTF-8 text, tables, bounding spans │
└───────────────────────┬───────────────────────┘
                        │ Information Extraction
                        ▼
┌───────────────────────────────────────────────┐
│ DS-3: STRUCTURED CASE DATABASE (PostgreSQL 16)│
│ Canonical entities, events, stages, milestones│
└───────────────────────┬───────────────────────┘
                        │ Graph Synchronization
                        ▼
┌───────────────────────────────────────────────┐
│ DS-4: CASE KNOWLEDGE GRAPH (Neo4j Enterprise) │
│ Entity-relationship property graph + citations │
└───────────────────────┬───────────────────────┘
                        │ Timeline Reconciliation
                        ▼
┌───────────────────────────────────────────────┐
│ DS-5: TIMELINE STORE (PostgreSQL Intervals)   │
│ ISO 8601 Allen interval temporal sequences    │
└───────────────────────┬───────────────────────┘
                        │ Two-Brain Evidence Gating
                        ▼
┌───────────────────────────────────────────────┐
│ DS-6: EVIDENCE-CLAIM MAPPING STORE            │
│ Verified / unverified claim grounding links   │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ DS-7: APPEND-ONLY AUDIT & REASONING STORE     │
│ Immudb Merkle Tree Ledger (Court-admissible)  │
└───────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ ACCELERATION RETRIEVAL LAYER (CRITICAL PRINCIPLE):            │
│ Case Data ──► Vector Embeddings ──► Qdrant Vector Store       │
│ ⚠️ VECTOR RETRIEVAL STORE IS STRICTLY NOT THE SOURCE OF TRUTH.│
│ The original evidence and structured records remain           │
│ authoritative; vector similarity is used solely for search.   │
└───────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Phase Roadmap

The 22 engineering implementation phases are structured sequentially across five major technical milestones:

```mermaid
flowchart TD
    subgraph M1["Milestone 1: Governance & Storage Foundation"]
        P1["Phase 1: Requirements & Policy Engineering"]
        P2["Phase 2: Database & Storage System Design"]
        P3["Phase 3: Secure Case Management Layer"]
        P4["Phase 4: Multi-Modal Evidence Ingestion"]
        P1 --> P2 --> P3 --> P4
    end

    subgraph M2["Milestone 2: Extraction & Knowledge Representation"]
        P5["Phase 5: OCR & Speech Processing (Whisper)"]
        P6["Phase 6: Legal NLP & Information Extraction"]
        P7["Phase 7: Structured Case Memory Assembly"]
        P8["Phase 8: Case Knowledge Graph (Neo4j)"]
        P9["Phase 9: Timeline & Contradiction Engine"]
        P4 --> P5 --> P6 --> P7 --> P8 --> P9
    end

    subgraph M3["Milestone 3: Cognitive Two-Brain Reasoning & Gating"]
        P10["Phase 10: Intuition Brain (LLM Sandbox)"]
        P11["Phase 11: Discipline Brain (Verification)"]
        P12["Phase 12: The Evidence Gatekeeper"]
        P13["Phase 13: Legal / Procedural Rule Engine"]
        P14["Phase 14: Investigative Gap Engine"]
        P15["Phase 15: Cross-Case Hard-ID Linker"]
        P9 --> P10 --> P11 --> P12
        P3 --> P13
        P12 & P13 --> P14
        P6 --> P15
    end

    subgraph M4["Milestone 4: User Experience & Integration"]
        P16["Phase 16: Append-Only Merkle Audit Trail"]
        P17["Phase 17: Investigator Dashboard Suite"]
        P18["Phase 18: Bilingual Voice Assistant Module"]
        P19["Phase 19: Case Diary & Report Generator"]
        P20["Phase 20: Forensic Lab (FSL) Gateway"]
        P12 & P14 & P15 --> P17
        P5 & P12 --> P18
        P12 & P14 --> P19
        P4 & P7 --> P20
    end

    subgraph M5["Milestone 5: Hardening & Commissioning"]
        P21["Phase 21: Adversarial Red-Teaming & Testing"]
        P22["Phase 22: On-Premise Air-Gapped Deployment"]
        P16 & P17 & P18 & P19 & P20 --> P21 --> P22
    end

    classDef m1 fill:#0f172a,stroke:#38bdf8,stroke-width:1.5px,color:#fff;
    classDef m2 fill:#1e1b4b,stroke:#818cf8,stroke-width:1.5px,color:#fff;
    classDef m3 fill:#311042,stroke:#a21caf,stroke-width:1.5px,color:#fff;
    classDef m4 fill:#064e3b,stroke:#34d399,stroke-width:1.5px,color:#fff;
    classDef m5 fill:#18181b,stroke:#e4e4e7,stroke-width:1.5px,color:#fff;

    class M1,P1,P2,P3,P4 m1;
    class M2,P5,P6,P7,P8,P9 m2;
    class M3,P10,P11,P12,P13,P14,P15 m3;
    class M4,P16,P17,P18,P19,P20 m4;
    class M5,P21,P22 m5;
```

---

## 7. Technology Mapping

Every architectural tier is mapped to a production-grade, technically implementable technology:

| Module / Tier | Selected Technology | Technical Suitability & Justification |
| :--- | :--- | :--- |
| **Frontend UI** | **Next.js 14 / React / Tailwind CSS / D3.js** | Server-side rendering ensures zero client-side credential exposure; D3.js provides high-performance rendering for interactive timelines and citation graphs. |
| **Backend Framework** | **Python FastAPI (Asyncio)** | High concurrency; native compatibility with PyTorch, vLLM, and HuggingFace ecosystems; auto-generated OpenAPI documentation. |
| **Relational Case DB** | **PostgreSQL 16 (JSONB & ACID)** | Enterprise ACID reliability; rich support for semi-structured legal documents via JSONB; native row-level security for multi-tenant case isolation. |
| **Knowledge Graph** | **Neo4j Enterprise Edition** | Native Property Graph model; optimized Cypher traversal for multi-hop entity relationships and evidentiary provenance tracking. |
| **Vector Search (Secondary)** | **Qdrant / pgvector** | Isolated vector embedding indexing; used strictly for semantic retrieval acceleration, completely subordinate to primary structured evidence. |
| **Object Vault (WORM)** | **MinIO Enterprise (Object Lock)** | S3-compatible, high-throughput on-premise storage; certified Object Lock Compliance Mode guarantees immutable WORM legal compliance. |
| **Audit Ledger** | **Immudb (Cryptographic Ledger)** | High-speed, tamper-evident append-only ledger based on cryptographic Merkle trees; mathematical proof of immutability for Section 65B/63 certificates. |
| **OCR Engine** | **PaddleOCR + Tesseract 5** | Multi-engine layout-aware OCR; specialized in regional Indian scripts (Malayalam) as well as English typed police panchnamas. |
| **Speech-to-Text (ASR)** | **Faster-Whisper (On-Premise)** | Locally deployed, fine-tuned transformer ASR capable of accurate transcription of code-switched Malayalam-English voice recordings. |
| **NLP & Entity Extractor** | **spaCy + Legal-BERT + Duckling** | Legal token classification; Duckling handles deterministic extraction and resolution of fuzzy temporal expressions into ISO 8601 intervals. |
| **LLM Inference Core** | **vLLM / Llama-3-70B-Instruct** | State-of-the-art open-source LLM; deployed on sovereign air-gapped GPU servers with PagedAttention for low-latency synthesis. |
| **Identity & Access (IAM)** | **Keycloak (OAuth2.0 / OIDC / FIDO2)** | Open-source enterprise IAM supporting hardware smart cards, biometric OTPs, and granular Attribute-Based Access Control (ABAC). |
| **Deployment Infrastructure** | **Docker / Kubernetes / Air-Gapped Linux** | Isolated on-premise deployment; zero internet egress ensures complete national data sovereignty and security of police records. |

---

## 8. Summary of Pipeline Integrity Verification

1. **Closed-Loop Feedback:** Field inquiries generated from detected gaps continuously update the case memory, ensuring an iterative, living investigation file.
2. **Deterministic Gating:** Generative AI output is intercepted by the Discipline Brain and Evidence Gate; no unverified hallucination can reach the investigator.
3. **Hard-ID Integrity:** Cross-case discovery is firewalled against subjective MO or behavioral matching, operating solely on verified machine tokens.
4. **Court Admissibility:** The append-only Merkle ledger produces Section 65B IEA / Section 63 BSA electronic evidence certificates that withstand judicial scrutiny.
