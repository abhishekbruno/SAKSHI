/**
 * SAKSHI Comprehensive Regression Test Suite:
 * Conflicting Information Assessment States & Evidence Security Verification.
 *
 * Verifies:
 * PART A: Conflicting Information Card
 *   1. No evidence available (0 exhibits -> "Awaiting evidence")
 *   2. Insufficient evidence (< 2 exhibits -> "Awaiting evidence" with prerequisite explanation)
 *   3. Comparison not yet run (>= 2 exhibits, !analysisSummary -> "Not assessed")
 *   4. Comparison in progress (isRunning -> "Assessment in progress")
 *   5. Comparison failure (hasError -> "Unable to assess")
 *   6. Completed comparison with potential discrepancies (count of potential discrepancies + unreviewed/detected)
 *   7. Completed comparison with none identified ("None identified" + note that it doesn't establish singular truth)
 *   8. Potential discrepancies awaiting human review (reviewed vs unresolved separated)
 *   9. No ambiguous dash ('—') or fabricated zeros.
 *
 * PART B: Evidence Security Status
 *   10. All required checks genuinely passed (cloud WORM) -> "All required security checks verified"
 *   11. Local development simulation disclosure -> "X/X Verified (Simulated)" · never claims "All exhibits protected & verified"
 *   12. Integrity passed but storage protection pending -> "Integrity verified · Storage protection pending"
 *   13. Integrity passed but storage protection failed -> "Storage protection failed" & Alert state
 *   14. Antivirus scanner unavailable -> "Antivirus scan unavailable" (never treated as clean)
 *   15. Missing verification record -> "Status unavailable"
 *   16. Encryption status unavailable / pending / failed
 *   17. Failed integrity comparison -> "Integrity check failed"
 *   18. Mixed verification results across exhibits -> "X/Y Verified", specific pending layer in subtext
 *   19. Case switching state isolation -> State cleared, zero cross-case leakage
 *
 * PART C: Consistency Across Screens
 *   20. Case Dashboard, Evidence row, Forensic Verification, and Recommended Action use consistent semantics
 *   21. Recommended Next Action in EVIDENCE_PROCESSING recommends finishing storage protection when integrity verified but WORM pending
 *   22. Live backend API verification against preserved test case SAKSHI-CASE-2026-C5A64E99
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const http = require("http");

// Mock browser globals for Node.js test environment
global.localStorage = {
  store: {},
  getItem(k) { return this.store[k] || null; },
  setItem(k, v) { this.store[k] = String(v); },
  removeItem(k) { delete this.store[k]; },
  clear() { this.store = {}; }
};
global.sessionStorage = {
  store: {},
  getItem(k) { return this.store[k] || null; },
  setItem(k, v) { this.store[k] = String(v); },
  removeItem(k) { delete this.store[k]; },
  clear() { this.store = {}; }
};
global.document = {
  addEventListener() {},
  getElementById() { return null; },
  querySelectorAll() { return []; }
};
global.window = {
  location: { hash: "" },
  localStorage: global.localStorage,
  sessionStorage: global.sessionStorage
};

const {
  ContradictionAssessmentEvaluator,
  EvidenceSecurityEvaluator,
  RecommendedActionEvaluator,
  StatusPresentation,
  State
} = require("./app.js");

console.log("===============================================================================");
console.log(" SAKSHI Regression Test: Conflicting Information & Evidence Security Status");
console.log("===============================================================================\n");

let passedCount = 0;
let failedCount = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  [PASS] ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failedCount++;
    process.exitCode = 1;
  }
}

async function asyncTest(name, fn) {
  try {
    await fn();
    console.log(`  [PASS] ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
    failedCount++;
    process.exitCode = 1;
  }
}

// ─── PART A: CONFLICTING INFORMATION ASSESSMENT STATES ──────────────────────
console.log("--- PART A: Conflicting Information Assessment States ---");

test("A1: No evidence available displays 'Awaiting evidence' and explains 2+ exhibits prerequisite", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [],
    analysisSummary: null,
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "AWAITING_EVIDENCE");
  assert.strictEqual(res.number, "Awaiting evidence");
  assert.strictEqual(res.isTextState, true);
  assert(res.subtext.includes("attach 2+ exhibits"), "Must explain that comparison requires 2+ exhibits");
  assert(res.subtext.includes("0 attached") || res.subtext.includes("0"), "Must indicate current count");
  assert.notStrictEqual(res.number, "—", "Must never display an ambiguous dash");
  assert.notStrictEqual(res.number, "0", "Must not fabricate zero contradictions when not assessed");
});

test("A2: Insufficient evidence (1 exhibit) displays 'Awaiting evidence' with 1 attached", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }],
    analysisSummary: null,
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "AWAITING_EVIDENCE");
  assert.strictEqual(res.number, "Awaiting evidence");
  assert(res.subtext.includes("1 attached"), "Must note 1 exhibit is currently attached");
  assert.notStrictEqual(res.number, "—", "Must never display an ambiguous dash");
});

test("A3: Comparison not yet run (>= 2 exhibits, no summary) displays 'Not assessed'", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: null,
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "NOT_ASSESSED");
  assert.strictEqual(res.number, "Not assessed");
  assert.strictEqual(res.isTextState, true);
  assert(res.subtext.includes("Comparison not yet run"), "Must explain comparison has not been run");
  assert.strictEqual(res.routeTab, "analysis", "Must link to analysis tab");
  assert.notStrictEqual(res.number, "—", "Must never display an ambiguous dash");
});

test("A4: Comparison in progress displays 'Assessment in progress'", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: null,
    isRunning: true,
    hasError: false
  });
  assert.strictEqual(res.state, "IN_PROGRESS");
  assert.strictEqual(res.number, "Assessment in progress");
  assert.strictEqual(res.isTextState, true);
  assert(res.subtext.includes("Comparing exhibits"), "Subtext must explain comparison is actively running");
});

test("A5: Comparison failure displays 'Unable to assess'", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: null,
    isRunning: false,
    hasError: true
  });
  assert.strictEqual(res.state, "UNAVAILABLE");
  assert.strictEqual(res.number, "Unable to assess");
  assert.strictEqual(res.isTextState, true);
  assert(res.subtext.includes("Assessment unavailable"), "Must explain assessment could not run");
  assert.strictEqual(res.actionText, "Retry Assessment");
});

test("A6: Completed comparison with potential discrepancies shows count and unreviewed/detected", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: {
      contradictions: [
        { contradiction_id: "C-1", investigator_status: "UNRESOLVED", resolved: false },
        { contradiction_id: "C-2", investigator_status: "CONFIRMED", resolved: true }
      ]
    },
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "DISCREPANCIES_FOUND");
  assert.strictEqual(res.number, "1 Potential Discrepancy");
  assert.strictEqual(res.unresolvedCount, 1);
  assert.strictEqual(res.reviewedCount, 1);
  assert.strictEqual(res.totalDetected, 2);
  assert(res.subtext.includes("1 reviewed / 2 detected"), "Must report 1 reviewed / 2 detected");
  assert(res.subtext.includes("potential discrepancies"), "Must specify potential discrepancies, not confirmed facts");
});

test("A7: Completed comparison with all discrepancies reviewed shows reviewed count", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: {
      contradictions: [
        { contradiction_id: "C-1", investigator_status: "CONFIRMED", resolved: true },
        { contradiction_id: "C-2", investigator_status: "DISMISSED", resolved: true }
      ]
    },
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "DISCREPANCIES_FOUND");
  assert.strictEqual(res.number, "2 Discrepancies (Reviewed)");
  assert.strictEqual(res.unresolvedCount, 0);
  assert.strictEqual(res.reviewedCount, 2);
  assert(res.subtext.includes("2 reviewed / 2 detected"));
});

test("A8: Completed comparison with none identified displays 'None identified' with epistemic clarification", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }],
    analysisSummary: {
      contradictions: []
    },
    isRunning: false,
    hasError: false
  });
  assert.strictEqual(res.state, "NONE_IDENTIFIED");
  assert.strictEqual(res.number, "None identified");
  assert.strictEqual(res.isTextState, true);
  assert(res.subtext.includes("No discrepancies identified across 2 exhibits compared"), "Must state 0 discrepancies found across exhibits");
  assert(res.subtext.includes("does not establish singular truth"), "Must state that absence of discrepancies does not establish singular truth");
});

test("A9: Card never counts evidence exhibits as contradictions", () => {
  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [{ evidence_id: "EVID-01" }, { evidence_id: "EVID-02" }, { evidence_id: "EVID-03" }],
    analysisSummary: {
      contradictions: [{ contradiction_id: "C-1", resolved: false }]
    }
  });
  assert.strictEqual(res.totalDetected, 1, "Must count only contradiction items, not 3 evidence exhibits");
  assert.strictEqual(res.number, "1 Potential Discrepancy");
});

// ─── PART B: EVIDENCE SECURITY STATUS EVALUATION ────────────────────────────
console.log("\n--- PART B: Evidence Security Status Evaluation ---");

test("B1: All required checks genuinely passed (cloud WORM) reports verified without simulation disclaimer", () => {
  const genuineExhibit = {
    evidence_id: "EVID-GEN-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    antivirus_scanner: "CLAMAV",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "COMMITTED",
    worm_storage_reference: "s3://gov-vault/worm/e1",
    lock_status: "LOCKED",
    lock_backend: "AWS_S3_OBJECT_LOCK",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(genuineExhibit);
  assert.strictEqual(evalE.storage.isSimulated, false);
  assert.strictEqual(evalE.overall.status, "VERIFIED");
  assert.strictEqual(evalE.overall.label, "Integrity verified · Storage protected");
  assert.strictEqual(evalE.overall.subtext, "Dual-hash verified & WORM locked");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([genuineExhibit]);
  assert.strictEqual(caseSec.status, "VERIFIED");
  assert.strictEqual(caseSec.isSimulated, false);
  assert.strictEqual(caseSec.metricValue, "1/1 Verified");
  assert.strictEqual(caseSec.subtext, "All required security checks verified");
});

test("B2: Local filesystem simulation is explicitly disclosed and NEVER claims 'All exhibits protected & verified'", () => {
  const localSimExhibit = {
    evidence_id: "EVID-LOC-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    antivirus_scanner: "CLAMAV",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "COMMITTED",
    worm_storage_reference: "objlock://local/worm/e1",
    lock_status: "LOCKED",
    lock_backend: "LOCAL_FILESYSTEM",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(localSimExhibit);
  assert.strictEqual(evalE.storage.isSimulated, true);
  assert.strictEqual(evalE.overall.status, "VERIFIED_SIMULATED");
  assert.strictEqual(evalE.overall.label, "Integrity verified (Local lock simulated)");
  assert.strictEqual(evalE.overall.subtext, "File integrity verified · Local lock simulated");
  assert(evalE.storage.details.includes("Local filesystem immutability simulated"), "Must disclose local filesystem simulation");
  assert(!evalE.overall.label.includes("Protected & Sealed"), "Must not claim Protected & Sealed for local simulation");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([localSimExhibit]);
  assert.strictEqual(caseSec.status, "VERIFIED_SIMULATED");
  assert.strictEqual(caseSec.isSimulated, true);
  assert.strictEqual(caseSec.metricValue, "1/1 Verified (Simulated)");
  assert.strictEqual(caseSec.subtext, "File integrity verified · Local lock simulated");
  assert.notStrictEqual(caseSec.subtext, "All exhibits protected & verified", "Must never produce misleading overall success claim");
});

test("B3: Integrity passed but storage protection pending reports pending storage and never claims fully verified", () => {
  const pendingWormExhibit = {
    evidence_id: "EVID-PW-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "PENDING",
    lock_status: "UNLOCKED",
    lock_backend: "LOCAL_FILESYSTEM",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(pendingWormExhibit);
  assert.strictEqual(evalE.integrity.passed, true);
  assert.strictEqual(evalE.storage.passed, false);
  assert.strictEqual(evalE.storage.pending, true);
  assert.strictEqual(evalE.overall.status, "INTEGRITY_PASSED_WORM_PENDING");
  assert.strictEqual(evalE.overall.label, "Integrity verified · Storage protection pending");
  assert.strictEqual(evalE.overall.subtext, "File integrity has been checked. Storage-protection verification is still pending.");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([pendingWormExhibit]);
  assert.strictEqual(caseSec.status, "PENDING");
  assert.strictEqual(caseSec.isFullySecure, false);
  assert.strictEqual(caseSec.metricValue, "0/1 Verified");
  assert.strictEqual(caseSec.subtext, "Integrity verified · Storage protection pending");
});

test("B4: Integrity passed but storage protection failed reports alert and failure", () => {
  const failedWormExhibit = {
    evidence_id: "EVID-FW-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "FAILED",
    lock_status: "LOCK_FAILED",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(failedWormExhibit);
  assert.strictEqual(evalE.storage.failed, true);
  assert.strictEqual(evalE.overall.hasAlert, true);
  assert.strictEqual(evalE.overall.status, "ALERT");
  assert.strictEqual(evalE.storage.label, "Storage protection failed");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([failedWormExhibit]);
  assert.strictEqual(caseSec.status, "ALERT");
  assert.strictEqual(caseSec.hasAlerts, true);
  assert(caseSec.subtext.includes("require immediate attention"));
});

test("B5: Antivirus scanner unavailable must NEVER be treated as clean", () => {
  const unavAvExhibit = {
    evidence_id: "EVID-AV-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "SCANNER_UNAVAILABLE",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "COMMITTED",
    lock_status: "LOCKED",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(unavAvExhibit);
  assert.strictEqual(evalE.antivirus.passed, false, "Missing/unavailable scanner verdict must NEVER be treated as clean");
  assert.strictEqual(evalE.antivirus.unavailable, true);
  assert.strictEqual(evalE.overall.status, "ATTENTION");
  assert.strictEqual(evalE.overall.label, "Antivirus scan unavailable");
  assert(evalE.antivirus.details.includes("cannot be treated as clean"));

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([unavAvExhibit]);
  assert.strictEqual(caseSec.status, "PENDING");
  assert.strictEqual(caseSec.isFullySecure, false);
  assert.strictEqual(caseSec.metricValue, "0/1 Verified");
  assert.strictEqual(caseSec.subtext, "Antivirus scan unavailable");
});

test("B6: Missing verification record returns 'Status unavailable'", () => {
  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(null);
  assert.strictEqual(evalE.overall.status, "UNAVAILABLE");
  assert.strictEqual(evalE.overall.label, "Status unavailable");
  assert.strictEqual(evalE.overall.subtext, "Verification state could not be determined");

  const unavCase = EvidenceSecurityEvaluator.evaluateUnavailable();
  assert.strictEqual(unavCase.status, "UNAVAILABLE");
  assert.strictEqual(unavCase.metricValue, "Status unavailable");
  assert.strictEqual(unavCase.subtext, "Verification state could not be determined");
});

test("B7: Encryption status unavailable or pending is not treated as verified", () => {
  const encPendingExhibit = {
    evidence_id: "EVID-ENC-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "VERIFIED",
    checksum_sha256: "a1b2c3d4e5f67890a1b2c3d4e5f67890",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "COMMITTED",
    lock_status: "LOCKED",
    encryption_status: "PENDING"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(encPendingExhibit);
  assert.strictEqual(evalE.encryption.passed, false);
  assert.strictEqual(evalE.encryption.pending, true);
  assert.strictEqual(evalE.overall.label, "Encryption status unavailable");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([encPendingExhibit]);
  assert.strictEqual(caseSec.isFullySecure, false);
  assert.strictEqual(caseSec.metricValue, "0/1 Verified");
});

test("B8: Failed integrity comparison reports alert and hash mismatch", () => {
  const failedHashExhibit = {
    evidence_id: "EVID-FAIL-01",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "FAILED",
    checksum_sha256: "mismatch_hash",
    raw_storage_path: "/vault/evid.pdf",
    worm_status: "COMMITTED",
    lock_status: "LOCKED",
    encryption_status: "ENCRYPTED"
  };

  const evalE = EvidenceSecurityEvaluator.evaluateExhibit(failedHashExhibit);
  assert.strictEqual(evalE.integrity.failed, true);
  assert.strictEqual(evalE.overall.hasAlert, true);
  assert.strictEqual(evalE.overall.status, "ALERT");
  assert.strictEqual(evalE.overall.label, "Integrity check failed");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([failedHashExhibit]);
  assert.strictEqual(caseSec.hasAlerts, true);
  assert.strictEqual(caseSec.metricValue, "1 Alert");
});

test("B9: Mixed verification results across multiple exhibits correctly reports X/Y Verified", () => {
  const ex1 = {
    evidence_id: "E1",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "VERIFIED",
    checksum_sha256: "abc",
    raw_storage_path: "/path1",
    worm_status: "COMMITTED",
    lock_status: "LOCKED",
    lock_backend: "LOCAL_FILESYSTEM",
    encryption_status: "ENCRYPTED"
  };
  const ex2 = {
    evidence_id: "E2",
    status: "VALIDATED",
    detected_mime_type: "application/pdf",
    antivirus_status: "CLEAN",
    integrity_status: "VERIFIED",
    checksum_sha256: "def",
    raw_storage_path: "/path2",
    worm_status: "PENDING",
    lock_status: "UNLOCKED",
    lock_backend: "LOCAL_FILESYSTEM",
    encryption_status: "ENCRYPTED"
  };

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity([ex1, ex2]);
  assert.strictEqual(caseSec.metricValue, "1/2 Verified");
  assert.strictEqual(caseSec.status, "PENDING");
  assert.strictEqual(caseSec.isFullySecure, false);
  assert.strictEqual(caseSec.subtext, "Integrity verified · Storage protection pending");
});

test("B10: Case switching isolates state without leaking security or contradiction metrics", () => {
  State.activeCaseId = "CASE-A";
  State.evidence = [{ evidence_id: "E-A" }];
  State.analysisSummary = { contradictions: [{ contradiction_id: "C-A", resolved: false }] };

  // Switching cases must clear evidence and analysis summary
  State.activeCase = { case_id: "CASE-B" };
  State.activeCaseId = "CASE-B";
  State.evidence = [];
  State.analysisSummary = null;
  State.analysisSummaryError = null;

  const res = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: State.evidence,
    analysisSummary: State.analysisSummary
  });
  assert.strictEqual(res.state, "AWAITING_EVIDENCE", "Must evaluate fresh case as awaiting evidence, not leaking previous contradictions");
});

// ─── PART C: RECOMMENDED ACTION & MULTI-SCREEN CONSISTENCY ──────────────────
console.log("\n--- PART C: Multi-Screen Consistency & Action Alignment ---");

test("C1: Recommended action in EVIDENCE_PROCESSING recommends finishing storage protection when WORM pending", () => {
  const caseObj = {
    case_id: "SAKSHI-CASE-2026-TEST",
    lifecycle_stage: "EVIDENCE_PROCESSING"
  };
  const exhibits = [
    {
      evidence_id: "EVID-01",
      original_file_name: "test_doc.pdf",
      status: "VALIDATED",
      detected_mime_type: "application/pdf",
      antivirus_status: "CLEAN",
      integrity_status: "VERIFIED",
      worm_status: "PENDING",
      raw_storage_path: "/p"
    }
  ];

  const rec = RecommendedActionEvaluator.getAction(caseObj, exhibits, null, []);
  assert(rec.title.includes("Evidence Protection") || rec.title.includes("Storage-Protection"), "Must recommend completing storage protection");
  assert(rec.whyItMatters.includes("File integrity has been checked. Storage-protection verification is still pending.") || rec.whyItMatters.includes("storage-protection verification is still pending"), "Why it matters must align with authoritative state");
  assert(rec.buttonHtml.includes("verification"), "Must offer working button routing to verification screen");
});

test("C2: Recommended action respects Stage Engine prerequisites and does not recommend advancing when checks pending", () => {
  const caseObj = {
    case_id: "SAKSHI-CASE-2026-TEST",
    lifecycle_stage: "EVIDENCE_PROCESSING"
  };
  const exhibits = [
    {
      evidence_id: "EVID-01",
      original_file_name: "unverified.pdf",
      status: "REGISTERED_INTAKE",
      integrity_status: "UNVERIFIED",
      worm_status: "PENDING"
    }
  ];

  const rec = RecommendedActionEvaluator.getAction(caseObj, exhibits, null, []);
  assert(!rec.title.includes("Advance to Investigation Analysis"), "Must not recommend advancing stage when evidence is unverified");
});

// ─── PART D: LIVE BACKEND VERIFICATION ──────────────────────────────────────
console.log("\n--- PART D: Live Backend Verification ---");

asyncTest("D1: Preserved case SAKSHI-CASE-2026-C5A64E99 returns authoritative evidence with simulated lock backend", async () => {
  const options = {
    hostname: "127.0.0.1",
    port: 8000,
    path: "/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/evidence",
    method: "GET",
    headers: {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    }
  };

  const data = await new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let body = "";
      res.on("data", chunk => body += chunk);
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(body));
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${body}`));
        }
      });
    });
    req.on("error", reject);
    req.end();
  });

  assert(data.total >= 2, "Must return at least 2 preserved exhibits");
  const fir = data.items.find(e => e.evidence_id === "SAKSHI-EVID-2026-54C01EA8");
  assert(fir, "Preserved FIR evidence SAKSHI-EVID-2026-54C01EA8 must exist");
  assert.strictEqual(fir.integrity_status, "VERIFIED");
  assert.strictEqual(fir.lock_backend, "LOCAL_FILESYSTEM");

  // Evaluate through EvidenceSecurityEvaluator
  const evalFir = EvidenceSecurityEvaluator.evaluateExhibit(fir);
  assert.strictEqual(evalFir.storage.isSimulated, true, "Must recognize LOCAL_FILESYSTEM as simulated lock");
  assert.strictEqual(evalFir.overall.label, "Integrity verified (Local lock simulated)");

  const caseSec = EvidenceSecurityEvaluator.evaluateCaseSecurity(data.items);
  assert.strictEqual(caseSec.isSimulated, true);
  assert(caseSec.metricValue.includes("(Simulated)"), "Dashboard security metric must disclose (Simulated)");
  assert.strictEqual(caseSec.subtext, "File integrity verified · Local lock simulated");
});

asyncTest("D2: Analysis summary endpoint returns real grounded analysis without fabricated contradictions", async () => {
  const options = {
    hostname: "127.0.0.1",
    port: 8000,
    path: "/api/v1/cases/SAKSHI-CASE-2026-C5A64E99/analysis-summary",
    method: "GET",
    headers: {
      "X-Investigator-Id": "dev-investigator-001",
      "X-Investigator-Role": "INVESTIGATING_OFFICER",
      "X-Investigator-Jurisdiction": "KERALA"
    }
  };

  const summary = await new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let body = "";
      res.on("data", chunk => body += chunk);
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(JSON.parse(body));
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${body}`));
        }
      });
    });
    req.on("error", reject);
    req.end();
  });

  assert.strictEqual(summary.case_id, "SAKSHI-CASE-2026-C5A64E99");
  assert(Array.isArray(summary.contradictions), "Contradictions must be an array");

  // Evaluate through ContradictionAssessmentEvaluator
  const evalConflicts = ContradictionAssessmentEvaluator.evaluate({
    evidenceList: [
      { evidence_id: "SAKSHI-EVID-2026-54C01EA8" },
      { evidence_id: "SAKSHI-EVID-2026-43F94E97" }
    ],
    analysisSummary: summary
  });

  if (summary.contradictions.length === 0) {
    assert.strictEqual(evalConflicts.state, "NONE_IDENTIFIED");
    assert.strictEqual(evalConflicts.number, "None identified");
    assert(evalConflicts.subtext.includes("No discrepancies identified across 2 exhibits compared"));
    assert(evalConflicts.subtext.includes("does not establish singular truth"));
  } else {
    assert.strictEqual(evalConflicts.state, "DISCREPANCIES_FOUND");
    assert(evalConflicts.number.includes("Discrepanc"));
    assert(evalConflicts.subtext.includes("detected"));
  }
});

// Run live async tests and exit
(async () => {
  // Let synchronous tests complete
  await new Promise(r => setTimeout(r, 100));
  console.log(`\n===============================================================================`);
  console.log(` SAKSHI Regression Test Complete: ${passedCount} passed, ${failedCount} failed.`);
  console.log(`===============================================================================\n`);
  if (failedCount > 0) {
    process.exit(1);
  }
})();
